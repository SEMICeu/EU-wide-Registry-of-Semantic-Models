from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
from tasks.extract.make_batches import make_batches
from tasks.extract.query_voc_and_ap_list import query_voc_and_ap_list
from tasks.load.fetch_jsonld import fetch_jsonld
from tasks.load.initialize_graphdb_repo import initialize_graphdb_repo
from tasks.load.load_data_to_graphdb import load_data_to_graphdb
from tasks.transform.construct_item import construct_item
from tasks.transform.validate import validate_data_graph
from config import load_config
from concurrent.futures import as_completed


@flow(name="Parallel Processing Pipeline", task_runner=ConcurrentTaskRunner(max_workers=5))
def parallel_processing_flow():
    """
    Main flow that orchestrates all tasks with parallel processing
    """
    config = load_config()
    logger = get_run_logger()
    logger.info("Starting parallel processing flow...")

    # Task 1: Extract JSON-LD from a Vlaanderen standards page.
    jsonld = fetch_jsonld(config["web_source_url"])

    # Task 2: Create a new repository in GraphDB. (Overwrite if repo exists)
    endpoint_source = initialize_graphdb_repo(
        config["graphDB_source_repo_name"],
        config["graphDB_config_file_path"],
        config["graphDB_host"]
    )

    # Task 3: Load JSON-LD into GraphDB as RDF triples.
    load_data_to_graphdb(jsonld, endpoint_source)

    # Task 4: Extract the Vocabularium and Application Profiles.
    list_result = query_voc_and_ap_list(endpoint_source, config["extract_query"])

    # Task 5: Create batches
    batches = make_batches(list_result)

    # Task 6: Process batches in parallel
    batch_futures = [
    construct_item.submit(batch, endpoint_source, config["construct_query"])
        for batch in batches
    ]
    
    # Wait for all batch processing to complete
    constructed_results = [future.result() for future in batch_futures]
    
    logger.info(f"Completed processing {len(constructed_results)} batches")

    # Task 7: Validate each entry
    validated_futures = [
        validate_data_graph.submit(
            constructed_item, 
            config["validator"]["url"],
            config["validator"]["payload"],
            config["validator"]["headers"]
        )
            for constructed_item in constructed_results
    ]

    validated_results = [future.result() for future in validated_futures]
    
    # Task 8: Load validated entries in GraphDB (TODO emporary SRM in GraphDB)
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


 
if __name__ == "__main__":

    result = parallel_processing_flow()
    print(f"\nFinal Result: {result}")
 