from prefect import task
from prefect.logging import get_run_logger

@task
def fetch_data_to_synonyms(source_endpoint):
    logger = get_run_logger()
    logger.info(f"Fetching data for synonyms from {source_endpoint}")
    return {"data": "synonyms"}

@task
def synonyms_and_enrich(data):
    logger = get_run_logger()
    logger.info("Finding synonyms...")
    return {"synonyms": data}