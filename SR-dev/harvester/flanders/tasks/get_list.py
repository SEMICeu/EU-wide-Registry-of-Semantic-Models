from prefect import task, get_run_logger

from typing import List
 
 
@task(name="Get List", retries=3, retry_delay_seconds=120)
def get_list() -> List[str]:

    """

    Task 1: Get the initial list of items to process

    """

    logger = get_run_logger()

    logger.info("Getting list of items...")

    # Example: returning a list of items to process

    items = [f"item_{i}" for i in range(1, 11)]

    logger.info(f"Retrieved {len(items)} items")

    return items