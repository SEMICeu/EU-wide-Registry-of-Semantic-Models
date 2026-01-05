from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
from .tasks.extract.make_batches import make_batches
from .tasks.extract.query_voc_and_ap_list import query_voc_and_ap_list
from .tasks.load.fetch_jsonld import fetch_jsonld
from .tasks.load.initialize_graphdb_repo import initialize_graphdb_repo
from .tasks.load.load_data_to_graphdb import load_data_to_graphdb
from .tasks.transform.construct_item import construct_item
from .tasks.transform.validate import validate_data_graph
from .tasks.transform.transform_item import transform_item
from config import load_config
from ...provenance.tracker import ProvenanceTracker
from ...provenance.model import JobStatus, TaskType


@flow(name="Parallel Processing Pipeline", task_runner=ConcurrentTaskRunner(max_workers=5))
def parallel_processing_flow():
    """
    Main flow that orchestrates all tasks with parallel processing
    """

    config = load_config()
    logger = get_run_logger()
    logger.info("Starting parallel processing flow...")

# Initialize provenance tracker
    tracker = ProvenanceTracker()
    tracker.start_activity()

    # Task 1: Extract JSON-LD from a Vlaanderen standards page.
    jsonld = fetch_jsonld(config["web_source_url"])

    # Task 2: Create a new repository in GraphDB. (Overwrite if repo exists)
    tracker.update_activity_task(TaskType.extract)
    endpoint_source = initialize_graphdb_repo(
        config["graphDB_source_repo_name"],
        config["graphDB_config_file_path"],
        config["graphDB_host"]
    )
    tracker.publish()

    # Task 3: Load JSON-LD into GraphDB as RDF triples.
    tracker.update_activity_task(TaskType.load_input)
    load_data_to_graphdb(jsonld, endpoint_source)
    tracker.publish()

    # Task 4: Extract the Vocabularium and Application Profiles.
    list_result = query_voc_and_ap_list(endpoint_source, config["extract_query"])
    tracker.publish()

    # Task 5: Create batches
    batches = make_batches(list_result)
    tracker.publish()
    
    # Task 6: Process batches in parallel
    tracker.update_activity_task(TaskType.transform)
    batch_futures = [
    construct_item.submit(batch, endpoint_source, config["construct_query"])
        for batch in batches
    ]

    constructed_results = [future.result() for future in batch_futures]
    logger.info(f"Completed constructing {len(constructed_results)} batches")

    transformed_futures = [
    transform_item.submit(constructed_batch)
        for constructed_batch in constructed_results
    ]

    transformed_results = [future.result() for future in transformed_futures]
    logger.info(f"Completed transformation {len(transformed_results)} batches")
    tracker.publish()

    # Task 7: Validate each entry
    tracker.update_activity_task(TaskType.validate)
    validated_futures = [
        validate_data_graph.submit(
            transformed_item, 
            config["validator"]["url"],
            config["validator"]["payload"],
            config["validator"]["headers"]
        )
        for transformed_item in transformed_results
    ]

    # Collect validation results, handling failures gracefully
    validated_results = []
    for i, future in enumerate(validated_futures):
        try:
            result = future.result()
            validated_results.append(result)
        except Exception as e:
            logger.error(f"Validation failed for entry {i}: {e}")
    
    logger.info(f"Successfully validated {len(validated_results)} out of {len(validated_futures)} entries")
    tracker.publish()

    # Task 8: Load validated entries in GraphDB (only if we have valid results)
    tracker.update_activity_task(TaskType.load_output)
    if validated_results:
        endpoint_target = initialize_graphdb_repo(
            config["graphDB_target_repo_name"],
            config["graphDB_config_file_path"],
            config["graphDB_host"]
        )

        loaded_results = [
            load_data_to_graphdb.submit(
                validated_result["contentToValidate"], 
                endpoint_target,
                format="turtle"  
            )
            for validated_result in validated_results
        ]
        
        load_status = [future.result() for future in loaded_results]
        logger.info(f"Loaded {sum(load_status)} out of {len(load_status)} entries successfully")
        tracker.update_status(JobStatus.completed)

        tracker.publish()

    else:
        logger.warning("No validated entries to load into GraphDB")


 
if __name__ == "__main__":

    result = parallel_processing_flow()
    # result = provenance_flow()
    print(f"\nFinal Result: {result}")
 