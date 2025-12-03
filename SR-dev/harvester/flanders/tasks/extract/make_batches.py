from prefect import task, get_run_logger
from typing import List


def chunk_dict(list: List[str], chunk_size):
    """
    Split a list of strings into consecutive chunks of a specified size.

    :param items: List of strings to be split into chunks.
    :param chunk_size: Maximum number of items per chunk.
    :return: A generator that yields lists of strings, each of length up to chunk_size.
    """
    for i in range(0, len(list), chunk_size):
        yield list[i:i+chunk_size]


@task(name="make batches")
def make_batches(results_by_standard, batch_size=1):
    logger = get_run_logger()
    batches = list(chunk_dict(results_by_standard, batch_size))
    logger.info(f"Creating {len(batches)} batches of size {batch_size}")
    return batches