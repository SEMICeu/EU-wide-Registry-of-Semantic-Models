from prefect import task
from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON
import requests

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_data_to_synonyms(source_endpoint: str = "http://63.32.50.253:81/sparql", graph_uri : str = "http://semic.registry.eu"):
    logger = get_run_logger()
    logger.info(f"Fetching data from {source_endpoint}")

    sparql = SPARQLWrapper(source_endpoint)
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
      ?class skos:altLabel ?altLabel .
      FILTER (STRSTARTS(str(?altLabel),"test-")) .
    }}
    GROUP BY ?class ?description
    """
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

    logger.info("Fetched data:", data)  # <-- This prints the fetched dictionary to stdout
    return data

@task
def synonyms_and_enrich(source_endpoint, graph_uri, data):
    logger = get_run_logger()
    logger.info(f"Enriching graph {graph_uri} with data")
    
    url = "http://127.0.0.1:8000/enricher-api/v1/synonyms"
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

    # Send the POST request
    response = requests.post(source_endpoint, data=sparql_update.encode('utf-8'), headers=headers)

    # Check response
    if response.status_code == 200:
        logger.info("SPARQL update successful!")
    else:
        logger.error(f"Error {response.status_code}: {response.text}")
    pass

    return {"synonyms response sparql": response.status_code}
