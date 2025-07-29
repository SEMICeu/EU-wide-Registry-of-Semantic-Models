from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON
from prefect import task
import requests

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_data_to_classify(source_endpoint: str = "http://63.32.50.253:81/sparql", graph_uri : str = "http://semic.registry.eu"):
    logger = get_run_logger()
    logger.info(f"Fetching data from {source_endpoint}")

    sparql = SPARQLWrapper(source_endpoint)
    sparql.setReturnFormat(JSON)

    query = f"""
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    SELECT distinct ?standard ?description
    FROM <{graph_uri}>
    WHERE {{
      ?standard a dct:Standard .
      ?standard dcat:theme ?theme .
      ?standard dct:description ?description .
      FILTER (STRSTARTS(str(?theme),"test-")) .
    }}
    """
    sparql.setQuery(query)
    results = sparql.query().convert()

    # Process results into a dict: { standard_uri: { property_uri: [values] } }
    data = {}
    for result in results["results"]["bindings"]:
        s = result["standard"]["value"]
        description = result["description"]["value"]
        data[s] = {
            "description": description
        }

    logger.info("Fetched data:", data)  # <-- This prints the fetched dictionary to stdout
    return data

@task
def classify_and_enrich(source_endpoint, graph_uri, data):
    logger = get_run_logger()
    logger.info(f"Enriching graph {graph_uri} with data")

    url = "http://127.0.0.1:8000/enricher-api/v1/classify"
    enriched_results = {}

    for standard_uri, props in data.items():
        description = props.get("description", "")
        if not description:
            logger.info(f"No description for {standard_uri}, skipping.")
            continue
        params = {
            "context": description,
            "classification" : "datathemes",
            "max": 1
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            classification_list = response.json()
            if classification_list and isinstance(classification_list, list):
                # Extract 'term' from first item, if exists
                term = classification_list[0].get("term") if "term" in classification_list[0] else None
                logger.info(f"Classification term for {standard_uri}: {term}")
                enriched_results[standard_uri] = term
            else:
                logger.error(f"Unexpected response format for {standard_uri}: {classification_list}")
                enriched_results[standard_uri] = None
        else:
            logger.error(f"Failed to classify {standard_uri}: HTTP {response.status_code}")
            enriched_results[standard_uri] = None

    logger.info(enriched_results)

    prefixes = """
    PREFIX dcat: <http://www.w3.org/ns/dcat#>
    """

    update_blocks = "\n".join(
        f"""
        DELETE {{
        GRAPH <{graph_uri}> {{
            <{uri}> dcat:theme ?oldTheme .
        }}
        }}
        INSERT {{
        GRAPH <{graph_uri}> {{
            <{uri}> dcat:theme "test-{theme}" .
        }}
        }}
        WHERE {{
        GRAPH <{graph_uri}> {{
            OPTIONAL {{ <{uri}> dcat:theme ?oldTheme . }}
        }}
        }}
        """ for uri, theme in enriched_results.items() if theme
    )

    sparql_update = prefixes + update_blocks
    logger.info("sparql query: " +sparql_update)

    # Headers for the SPARQL update request
    headers = {
        "Content-Type": "application/sparql-update"
    }

    # Send the POST request
    response = requests.post(source_endpoint, data=sparql_update.encode('utf-8'), headers=headers)

    # Check response
    if response.status_code == 200:
        logger.info("SPARQL update successful!")
    else:
        logger.error(f"Error {response.status_code}: {response.text}")
    pass

    return {"classify response sparql": response.status_code}
