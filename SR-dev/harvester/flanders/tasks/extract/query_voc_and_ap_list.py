from prefect import task, get_run_logger
from typing import  List
from db.client import get_sparql_client


@task(name="Extract List", retries=3, retry_delay_seconds=120)
def query_voc_and_ap_list(db_path: str, extract_query: str) -> List[str]:
    """
    Extract the Vocabularium and Application Profiles from a GraphDB repository.

    :param db_path: Path or endpoint of the GraphDB repository.
    :param extract_query: SPARQL query string used to extract the desired list.
    :return: List of strings representing extracted Vocabularium and Application Profiles.
    """

    logger = get_run_logger()
    logger.info("Connecting to SPARQL endpoint...")

    sparql = get_sparql_client(db_path)
    sparql.setQuery(extract_query)

    try:
        logger.info("Extracting Vocabularium and Application Profiles from the Flanders Register...")
        results = sparql.query().convert()
    except Exception as e:
        logger.error(f"Error extracting data from the Flanders Register: {e}")
        return

    vars = results["head"]["vars"]
    bindings = results["results"]["bindings"]

    if not bindings:
        logger.info("No results found.")
        return

    header = " | ".join(vars)
    logger.info(header)
    logger.info("-" * len(header.expandtabs()))

    for row in bindings:
        row_values = [row[v]["value"] if v in row else "" for v in vars]
        logger.info(" | ".join(row_values))

    logger.info(f"\n✅ Total rows: {len(bindings)}\n")

    return [row[vars[0]]["value"] for row in bindings] 