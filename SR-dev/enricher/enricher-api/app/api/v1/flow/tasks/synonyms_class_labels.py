from prefect import task
from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON
import requests

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_labels_to_synonyms(
    endpoint: str = "https://health.semic.eu/virtuoso/sparql", 
    graph_uri : str = "http://semic.registry.eu"
    ):
    
    logger = get_run_logger()
    logger.info(f"Fetching data from {endpoint}")

    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)

    query = f"""
    PREFIX dct: <http://purl.org/dc/terms/>
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    select distinct ?class (group_concat(distinct ?lowLabel;separator=",") as ?labels) ?description
    FROM <{graph_uri}>
    where {{
      ?standard a dct:Standard .
      ?standard dct:description ?description .
      FILTER(lang(?description) = "en") .
      ?standard dct:hasPart ?class .
      ?class rdfs:label ?label .
      BIND(LCASE(?label) as ?lowLabel) .
      FILTER(lang(?label) = "en")
      
    }}
    GROUP BY ?class ?description
    """
    # ?class skos:altLabel ?altLabel .
    # FILTER (STRSTARTS(str(?altLabel),"test-")) .
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
                if synonyms_list and isinstance(synonyms_list, list):
                    # Extract 'term' from first item, if exists
                    term = synonyms_list[0].get("term") if "term" in synonyms_list[0] else None
                    logger.info(f"synonyms for {aclass}: {term}")
                    term = term.replace("_", " ")
                    enriched_results[aclass] = term
                else:
                    logger.error(f"Unexpected response format for {aclass}: {synonyms_list}")
                    enriched_results[aclass] = None
            else:
                logger.error(f"Failed to find synonyms for {aclass}: HTTP {response.status_code}")
                enriched_results[aclass] = None

    logger.info(enriched_results)
    return enriched_results

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@task
def add_synonyms_to_graph(endpoint, graph_uri, enriched_results):
    logger = get_run_logger()
    logger.info(f"Add synonyms to the graph {graph_uri}...")
    prefixes = """
    PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
    """

    update_blocks = "\n".join(
        f"""
        DELETE {{
        GRAPH <{graph_uri}> {{
            <{uri}> skos:altLabel ?altLabel .
        }}
        }}
        INSERT {{
        GRAPH <{graph_uri}> {{
            <{uri}> skos:altLabel "test-{altLabel}" .
        }}
        }}
        WHERE {{
        GRAPH <{graph_uri}> {{
            OPTIONAL {{ <{uri}> skos:altLabel ?altLabel . }}
        }}
        }}
        """ for uri, altLabel in enriched_results.items() if altLabel
    )

    sparql_update = prefixes + update_blocks
    logger.info("sparql query: " + sparql_update)

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
