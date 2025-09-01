from prefect import task
from prefect.logging import get_run_logger
import requests
from ..util_sparql import execute_sparql_select, execute_sparql_update
from string import Template
import re

def clean_text(text: str) -> str:
    """
    Preprocess text before embedding:
    - remove URLs
    - remove email-like tokens
    - collapse extra whitespace
    """
    # remove URLs (http, https, www)
    text = re.sub(r'http\S+|www\.\S+', '', text)

    # remove email addresses or s3-like tokens
    text = re.sub(r'\S+@\S+|\S+\.s3-\S+', '', text)

    # collapse multiple spaces/newlines into one space
    text = re.sub(r'\s+', ' ', text).strip()

    return text

# Suggest improvements for this function
@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_themes_to_classify(
    endpoint: str, 
    graph_uri : str,
    fetch_themes_to_classify_query : str,
    auth_dict: dict
    ):

    logger = get_run_logger()
    logger.info(f"Fetching data from {endpoint}")

    template = Template(fetch_themes_to_classify_query)
    params = {
        "graph_uri" : graph_uri
    }
    query = template.substitute(params)
    logger.info(f"[SPARQL] Query: {query}")
    #  FILTER (STRSTARTS(str(?theme),"test-")) .
    
    # sparql = SPARQLWrapper(endpoint)
    # sparql.setReturnFormat(JSON)
    # sparql.setQuery(query)
    # results = sparql.query().convert()

    sparql_result = execute_sparql_select(endpoint, query, "JSON", auth_dict["username"], auth_dict["password"])
    if(sparql_result['http_code'] == 200):
        results = sparql_result['data']

    # Process results into a dict: { standard_uri: { property_uri: [values] } }
    data = {}
    for result in results["results"]["bindings"]:
        s = result["standard"]["value"]
        description = result["description"]["value"]
        labels = result["labels"]["value"]
        keywords = result["keywords"]["value"]
        data[s] = {
            "description": description,
            "labels": labels,
            "keywords": keywords
        }

    logger.info(f"Fetched data: {data}")
    return data

@task(tags=["classify", "enrich"], retries=3, retry_delay_seconds=120, retry_jitter_factor=0.2)
def classify(
        classify_api: str, 
        data: dict
    ):

    logger = get_run_logger()
    logger.info(f"Classifying the data...")

    url = classify_api
    enriched_results = {}

    for standard_uri, props in data.items():
        description = props.get("description", "")
        if not description:
            logger.info(f"No description for {standard_uri}, skipping.")
            continue
        labels = props.get("labels", "")
        keywords = props.get("keywords", "")
        params = {
            "context": description + " " + labels + " " + keywords,
            "classification" : "datathemes",
            "max": 1
        }
        logger.info(f"Calling classify API {url} for {standard_uri} with context {params['context']} ")
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            classification_list = response.json()
            if classification_list and isinstance(classification_list, list):
                # Extract 'term' from first item, if exists
                term = classification_list[0].get("term") if "term" in classification_list[0] else None
                score = classification_list[0].get("score") if "score" in classification_list[0] else None
                logger.info(f"Classification term for {standard_uri}: {term}-{score}")
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
def add_themes_to_graph(
        endpoint: str,
        source_graph: str, 
        target_graph: str, 
        enriched_results: dict, 
        queries: dict, 
        auth_dict: dict
    ):

    logger = get_run_logger()
    logger.info(f"Adding themes to the graph {target_graph}...")

    prefixes = queries["prefixes"]
    query_template = queries["query"]

    sparql_update_blocks = []

    for uri, theme in enriched_results.items():
        if theme:
            template = Template(query_template)
            if (target_graph != source_graph):
                sparql_update_blocks.append(
                    template.substitute(graph_uri=target_graph, uri=uri, theme=f"{theme}")
                )
            else:
                sparql_update_blocks.append(
                    template.substitute(graph_uri=target_graph, uri=uri, theme=f"{theme}-test")
                )            

    sparql_update = prefixes + "\n" + "\n".join(sparql_update_blocks)
    logger.info("[SPARQL] update query:\n" + sparql_update)

    try:
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
