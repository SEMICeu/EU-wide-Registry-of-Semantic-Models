from prefect import task, get_run_logger
from typing import Any, List
from db.client import get_sparql_client
from SPARQLWrapper import TURTLE
from string import Template



@task(name="Extract List", retries=3, retry_delay_seconds=120)
def query_voc_and_ap_list(db_path: str, extract_query: str) -> List[str]:
    """
    Task 4: Extract the Vocabularium and Application Profiles .

    Execute a SPARQL query and print results in a table format.
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


def chunk_dict(list: List[str], chunk_size):
    """Split dict into chunks of size chunk_size."""
    for i in range(0, len(list), chunk_size):
        yield list[i:i+chunk_size]


@task(name="make batches", retries=3, retry_delay_seconds=120)
def make_batches(results_by_standard, batch_size=1):
    logger = get_run_logger()
    batches = list(chunk_dict(results_by_standard, batch_size))
    logger.info(f"Creating {len(batches)} batches of size {batch_size}")
    return batches


@task(
    name="construct item", 
    retries=3, 
    retry_delay_seconds=60,
    timeout_seconds=300
)
async def construct_item(batch: str, db_path: str, construct_query: str) -> List[str]:
    """
    Execute a SPARQL query and print results in a table format.
    """
    logger = get_run_logger()

    query_template = construct_query

    logger.info(f"Constructing list for batch: {batch}")  
 
    try:
        template = Template(query_template)
        query = template.substitute(uri=batch)
        
        logger.info(f"Query to execute:\n{query[:500]}") 

        sparql = get_sparql_client(db_path)
        sparql.setQuery(query)
        sparql.setReturnFormat(TURTLE)
        sparql.setTimeout(120) 
        
        logger.info(f"Executing query...")
        results = sparql.query().convert()
        
        result_size = len(results) if isinstance(results, (str, bytes)) else "unknown"
        logger.info(f"Query completed. Result size: {result_size} bytes")

        return results
        
    except Exception as e:
        logger.error(f"FAILED for batch: {batch}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise 