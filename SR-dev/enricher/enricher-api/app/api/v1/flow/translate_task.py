from prefect import task
from prefect.logging import get_run_logger

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_data_to_translate(source_endpoint):
    logger = get_run_logger()
    logger.info(f"Fetching data for translate from {source_endpoint}")
    return {"data": "translate"}

@task
def translate_and_enrich(data):
    logger = get_run_logger()
    logger.info("Running translation...")
    return {"translated": data}