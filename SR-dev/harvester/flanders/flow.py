from prefect import flow, task, get_run_logger
from typing import List, Dict, Any
import time
from tasks.jsonld_ingest import fetch_jsonld, initialize_graphdb_repo, load_jsonld_to_graphdb
from tasks.extract import query_voc_and_ap_list, construct_list
from tasks.validate import validate_data_graph
from config import load_config
 
@task(name="Split List", retries=3, retry_delay_seconds=120)
def split_list(items: List[str], chunk_size: int = 3) -> List[List[str]]:

    """

    Task 2: Split the list into chunks for parallel processing

    """

    logger = get_run_logger()

    logger.info(f"Splitting list into chunks of size {chunk_size}...")

    chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

    logger.info(f"Created {len(chunks)} chunks")

    return chunks
 
 
@task(name="Enrich Standard", retries=3, retry_delay_seconds=120)

def enrich_standard(item: str) -> Dict[str, Any]:

    """

    Task 3: Enrich each item with additional data

    This task will run in parallel for each item

    """

    logger = get_run_logger()

    logger.info(f"Enriching {item}...")

    try:

        time.sleep(0.5)  # Simulate processing time

        enriched_data = {

            "original": item,

            "enriched_field_1": f"{item}_enriched",

            "enriched_field_2": len(item),

            "timestamp": time.time()

        }

        logger.info(f"Completed enrichment for {item}")

        return enriched_data

    except Exception as e:

        logger.error(f"Error enriching {item}: {str(e)}")

        raise
 
 

 
@task(name="Store", retries=3, retry_delay_seconds=120)

def store(validated_data: Dict[str, Any]) -> bool:

    """

    Task 5: Store the validated data

    This task will run in parallel for each validated item

    """

    logger = get_run_logger()

    logger.info(f"Storing {validated_data['original']}...")

    try:

        time.sleep(0.2)  # Simulate storage time

        # Simulate storing to a database or file

        if validated_data.get("is_valid"):

            logger.info(f"Successfully stored {validated_data['original']}")

            return True

        else:

            logger.warning(f"Skipped storing invalid item {validated_data['original']}")

            return False

    except Exception as e:

        logger.error(f"Error storing {validated_data['original']}: {str(e)}")

        raise
 
 
@flow(name="Parallel Processing Pipeline")

def parallel_processing_flow():

    """

    Main flow that orchestrates all tasks with parallel processing

    """
    config = load_config()

    logger = get_run_logger()
    logger.info("Starting parallel processing flow...")

    # Task 1: Extract JSON-LD from a Vlaanderen standards page.
    jsonld = fetch_jsonld(config["web_source_url"])

    #Task 2: Create a new repository in GraphDB. (Overwrite if repo exists)
    endpoint = initialize_graphdb_repo(config["graphDB_repo_name"],config["graphDB_config_file_path"],config["graphDB_host"])

    # Task 3: Load JSON-LD into GraphDB as RDF triples.
    load_jsonld_to_graphdb(jsonld, endpoint)

    # Task 4:     Task 4: Extract the Vocabularium and Application Profiles .
    list = query_voc_and_ap_list(endpoint, config["extract_query"])


    # chunks = chunk_list(list)

    # Task 25 validate

    # list2 = construct_list("http://localhost:7200/repositories/oslo", config["construct_query"])

    validated_futures = [
        validate_data_graph.submit(
            list, 
            config["validator"]["url"],
            config["validator"]["payload"],
            config["validator"]["headers"]
        )]
    validated_results = [future.result() for future in validated_futures]


    # items = get_list()

    # # Task 2: Split the list into chunks (optional - can process all at once)

    # chunks = split_list(items)

    # # Process all items in parallel through tasks 3, 4, and 5

    # results = []

    # # Flatten chunks back to individual items for parallel processing

    # all_items = [item for chunk in chunks for item in chunk]

    # logger.info(f"Processing {len(all_items)} items in parallel...")

    # # Task 3: Enrich (parallel)

    # enriched_futures = [enrich_standard.submit(item) for item in all_items]

    # enriched_results = [future.result() for future in enriched_futures]

    # logger.info(f"Enrichment completed for all items")

    # # Task 4: Validate (parallel)

    # validated_futures = [validate.submit(enriched) for enriched in enriched_results]

    # validated_results = [future.result() for future in validated_futures]

    # logger.info(f"Validation completed for all items")

    # # Task 5: Store (parallel)

    # store_futures = [store.submit(validated) for validated in validated_results]

    # store_results = [future.result() for future in store_futures]

    # logger.info(f"Storage completed for all items")

    # # Summary

    # successful_stores = sum(store_results)

    # logger.info(f"=== Pipeline Complete ===")

    # logger.info(f"Total items processed: {len(all_items)}")

    # logger.info(f"Successfully stored: {successful_stores}")

    # logger.info(f"Failed/Skipped: {len(all_items) - successful_stores}")

    # return {

    #     "total_processed": len(all_items),

    #     "successful": successful_stores,

    #     "failed": len(all_items) - successful_stores

    # }
 
 
if __name__ == "__main__":

    # Run the flow locally

    result = parallel_processing_flow()

    print(f"\nFinal Result: {result}")
 