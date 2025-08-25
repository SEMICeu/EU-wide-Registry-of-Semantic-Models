from prefect import task
from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON
import requests
from string import Template

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_labels_to_synonyms(
    endpoint: str, 
    graph_uri : str,
    fetch_labels_to_synonyms_query : str
    ):
    
    logger = get_run_logger()
    logger.info(f"Fetching data from {endpoint}")

    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)

    template = Template(fetch_labels_to_synonyms_query)
    params = {
        "graph_uri" : graph_uri
    }
    # ?class skos:altLabel ?altLabel .
    # FILTER (STRSTARTS(str(?altLabel),"test-")) .
    query = template.substitute(params)
    logger.info(f"Query: {query}")

    sparql.setQuery(query)
    results = sparql.query().convert()

    # Process results into a dict: { standard_uri: { property_uri: [values] } }
    data = {}
    for result in results["results"]["bindings"]:
        s = result["class"]["value"]
        description = result["description"]["value"]
        labels = result["labels"]["value"]
        data[s] = {
            "description": description,
            "labels" : labels
        }

    logger.info(f"Fetched data: {data}")  # <-- This prints the fetched dictionary to stdout
    return data

@task(tags=["synonyms", "enrich"], retries=3, retry_delay_seconds=120, retry_jitter_factor=0.2)
def synonyms(synonyms_api, data):
    logger = get_run_logger()
    logger.info(f"Getting synonyms...")
    
    url = synonyms_api
    enriched_results = {}

    for aclass, props in data.items():
        description = props.get("description", "")
        labels = props.get("labels", "")
        splitted_labels = labels.split(",")
        for label in splitted_labels:
            params = {
                "term": label,
                "context" : description,
                "max": 1
            }

            response = requests.get(url, params=params)
            if response.status_code == 200:
                synonyms_list = response.json()
                # Take the first synonym if exists, else None
                term = synonyms_list[0]["term"].replace("_", " ") if synonyms_list else None
                if term:
                    logger.info(f"Synonym for {aclass}: {term}")
                else:
                    logger.info(f"No synonyms found for {aclass} and label '{label}'")
                enriched_results[aclass] = term
            else:
                logger.error(f"Failed to get synonyms for {aclass}, label '{label}': HTTP {response.status_code}")
                enriched_results[aclass] = None

    logger.info(enriched_results)
    return enriched_results

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@task
def add_synonyms_to_graph(endpoint: str, graph_uri: str, enriched_results: dict,  queries: dict):
    logger = get_run_logger()
    logger.info(f"Add synonyms to the graph {graph_uri}...")

    prefixes = queries["prefixes"]
    query_template = queries["query"]
    sparql_update_blocks = []

    for uri, altLabel  in enriched_results.items():
        if altLabel :
            template = Template(query_template)
            sparql_update_blocks.append(
                template.substitute(graph_uri=graph_uri, uri=uri, altLabel=f"test-{altLabel}")
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
