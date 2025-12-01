from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
from typing import List, Dict, Any
import time
from tasks.jsonld_ingest import fetch_jsonld, initialize_graphdb_repo, load_jsonld_to_graphdb
from tasks.extract import query_voc_and_ap_list, construct_item, make_batches
from tasks.validate import validate_data_graph
from config import load_config


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
    endpoint = initialize_graphdb_repo(
        config["graphDB_repo_name"],
        config["graphDB_config_file_path"],
        config["graphDB_host"]
    )

    # Task 3: Load JSON-LD into GraphDB as RDF triples.
    isLoaded = load_jsonld_to_graphdb(jsonld, endpoint)

    # Task 4: Extract the Vocabularium and Application Profiles.
    list_result = query_voc_and_ap_list(endpoint, config["extract_query"])

    # Task 5: Create batches
    batches = make_batches(list_result)

    # Task 6: Process batches in parallel
    batch_futures = [
        construct_item.submit(batch, endpoint, config["construct_query"])
        for batch in batches
    ]
    
    # Wait for all batch processing to complete
    results = [future.result() for future in batch_futures]
    
    logger.info(f"Completed processing {len(results)} batches")
    
    return results
 
 
if __name__ == "__main__":

    # Run the flow locally

    result = parallel_processing_flow()

    print(f"\nFinal Result: {result}")
 