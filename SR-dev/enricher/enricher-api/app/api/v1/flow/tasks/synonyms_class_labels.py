from prefect import task
from prefect.logging import get_run_logger
from ..util_sparql import execute_sparql_select, execute_sparql_update
import requests
from string import Template

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_labels_to_synonyms(
    endpoint: str, 
    graph_uri : str,
    fetch_labels_to_synonyms_query : str,
    auth_dict: dict
    ):
    
    logger = get_run_logger()
    logger.info(f"Fetching data from {endpoint}")

    template = Template(fetch_labels_to_synonyms_query)
    params = {
        "graph_uri" : graph_uri
    }
    # ?class skos:altLabel ?altLabel .
    # FILTER (STRSTARTS(str(?altLabel),"test-")) .
    query = template.substitute(params)
    logger.info(f"[SPARQL] Query: {query}")

    sparql_result = execute_sparql_select(endpoint, query, "JSON", auth_dict["username"], auth_dict["password"])
    if(sparql_result['http_code'] == 200):
        results = sparql_result['data']
    
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

    logger.info(f"Fetched data: {data}")
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
def add_synonyms_to_graph(
    endpoint: str, 
    source_graph: str,
    target_graph: str, 
    enriched_results: dict,  
    queries: dict, 
    auth_dict: dict
    ):

    logger = get_run_logger()
    logger.info(f"Add synonyms to the graph {target_graph}...")

    prefixes = queries["prefixes"]
    query_template = queries["query"]
    sparql_update_blocks = []

    for uri, altLabel  in enriched_results.items():
        if altLabel :
            template = Template(query_template)
            if (target_graph != source_graph):
                sparql_update_blocks.append(
                    template.substitute(graph_uri=target_graph, uri=uri, altLabel=f"{altLabel}")
                )
            else:
                sparql_update_blocks.append(
                    template.substitute(graph_uri=target_graph, uri=uri, altLabel=f"test-{altLabel}")
                )

    sparql_update = prefixes + "\n" + "\n".join(sparql_update_blocks)
    logger.info("[SPARQL] update query:\n" + sparql_update)

    try:
        # Send the POST request
        sparql_result = execute_sparql_update(endpoint, sparql_update.encode('utf-8'), auth_dict["username"], auth_dict["password"])

        # Check response and raise exception if failed
        if (sparql_result['http_code'] == 200):
            logger.info("[SPARQL] update successful!")
            return {"classify response sparql": sparql_result['http_code'] }
        else:
            error_msg = f"[SPARQL] update failed with status {sparql_result['http_code'] }: {sparql_result['message'] }"
            logger.error(error_msg)
            raise Exception(error_msg)
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
