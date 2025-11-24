from prefect import flow, task, get_run_logger
from typing import List, Dict, Any
from SPARQLWrapper import SPARQLWrapper, JSON
from pathlib import Path

# def query(sparql_endpoint: str, sparql_query: str, db_path: str ):
#     """
#     Execute a SPARQL query and print results in a table format.
    
#     Args:
#         sparql_endpoint (str): SPARQL endpoint URL
#         sparql_query (str): SPARQL query string
#     """
#     sparql = SPARQLWrapper(sparql_endpoint)
#     sparql.setQuery(sparql_query)
#     sparql.setReturnFormat(JSON)
#     sparql.setMethod("POST")

#     try:
#         results = sparql.query().convert()
#     except Exception as e:
#         print("Error querying SPARQL endpoint:", e)
#         return

#     vars = results["head"]["vars"]
#     bindings = results["results"]["bindings"]

#     if not bindings:
#         print("No results found.")
#         return

#     header = " | ".join(vars)
#     print(header)
#     print("-" * len(header.expandtabs()))

#     for row in bindings:
#         row_values = [row[v]["value"] if v in row else "" for v in vars]
#         print(" | ".join(row_values))

#     print(f"\n✅ Total rows: {len(bindings)}\n")


if __name__ == "__main__":
    # Example: get all contact points
    contact_point_query = """
    PREFIX m8g: <http://data.europa.eu/m8g/>
    PREFIX dcterms: <http://purl.org/dc/terms/>
    SELECT ?subject ?contactPoint
    WHERE {
      ?subject m8g:contactPoint ?contactPoint .
    }
    """

    # # Example: count all triples
    # count_query = """
    # SELECT (COUNT(*) AS ?triplesCount)
    # WHERE {
    #   ?s ?p ?o .
    # }
    # """
    # query(SPARQL_ENDPOINT_FLANDERS_REGISTER, count_query)

@task(name="Extract", retries=3, retry_delay_seconds=120)
def extract_list(db_path: str, extract_query: str) -> List[str]:
    """

    Task 1: Extract the Vocabularium and Application Profiles from the Flanders Register

    Execute a SPARQL query and print results in a table format.
    
    Args:
        sparql_endpoint (str): SPARQL endpoint URL
        sparql_query (str): SPARQL query string
    """
    sparql = SPARQLWrapper(db_path)
    sparql.setQuery(extract_query)
    sparql.setReturnFormat(JSON)
    sparql.setMethod("POST")

    try:

        logger = get_run_logger()
        logger.info("Extracting Vocabularium and Application Profiles from the Flanders Register...")
        results = sparql.query().convert()
    except Exception as e:
        logger.error("Error extracting Vocabularium and Application Profiles from the Flanders Register:", e)
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

