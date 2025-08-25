from prefect import task
from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON
import requests
from string import Template

# Suggest improvements for this function
@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_themes_to_classify(
    endpoint: str, 
    graph_uri : str,
    fetch_themes_to_classify_query : str
    ):

    logger = get_run_logger()
    logger.info(f"Fetching data from {endpoint}")

    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)

    template = Template(fetch_themes_to_classify_query)
    params = {
        "graph_uri" : graph_uri
    }
    query = template.substitute(params)
    logger.info(f"Query: {query}")
    #  FILTER (STRSTARTS(str(?theme),"test-")) .
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

    logger.info(f"Fetched data: {data}")
    return data

@task(tags=["classify", "enrich"], retries=3, retry_delay_seconds=120, retry_jitter_factor=0.2)
def classify(classify_api, data):
    logger = get_run_logger()
    logger.info(f"Classifying the data...")

    url = classify_api
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
        logger.info(f"Calling classify API {url} for {standard_uri}")
        response = requests.get(url, params=params, timeout=30)
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
    return enriched_results

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@task
def add_themes_to_graph(endpoint: str, graph_uri: str, enriched_results: dict, queries: dict):
    logger = get_run_logger()
    logger.info(f"Adding themes to the graph {graph_uri}...")

    prefixes = queries["prefixes"]
    query_template = queries["query"]

    #prefixes = """
    #PREFIX dcat: <http://www.w3.org/ns/dcat#>
    #"""

    sparql_update_blocks = []

    for uri, theme in enriched_results.items():
        if theme:
            template = Template(query_template)
            sparql_update_blocks.append(
                template.substitute(graph_uri=graph_uri, uri=uri, theme=f"test-{theme}")
            )

    sparql_update = prefixes + "\n" + "\n".join(sparql_update_blocks)
    logger.info("SPARQL update query:\n" + sparql_update)

    # Headers for the SPARQL update request
    headers = {
        "Content-Type": "application/sparql-update"
    }

    try:
        # Send the POST request
        response = requests.post(endpoint, data=sparql_update.encode('utf-8'), headers=headers, verify=False)

        # Check response and raise exception if failed
        if response.status_code == 200:
            logger.info("SPARQL update successful!")
            return {"classify response sparql": response.status_code}
        else:
            error_msg = f"SPARQL update failed with status {response.status_code}: {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
