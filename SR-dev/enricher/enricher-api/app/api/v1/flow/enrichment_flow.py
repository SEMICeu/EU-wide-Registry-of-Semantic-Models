from prefect import flow, task
from SPARQLWrapper import SPARQLWrapper, JSON
import requests

@task
def fetch_data(source_endpoint: str = "http://63.32.50.253:81/sparql", graph_uri : str = "http://semic.registry.eu"):
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

    print("Fetched data:", data)  # <-- This prints the fetched dictionary to stdou
    return data

@task
def enrich_graph(source_endpoint, graph_uri, data):

    url = "http://127.0.0.1:8000/api/v1/classify"
    enriched_results = {}

    for standard_uri, props in data.items():
        description = props.get("description", "")
        if not description:
            print(f"No description for {standard_uri}, skipping.")
            continue
        params = {
            "context": description,
            "max": 1
        }

        response = requests.get(url, params=params)
        if response.status_code == 200:
            classification_list = response.json()
            if classification_list and isinstance(classification_list, list):
                # Extract 'term' from first item, if exists
                term = classification_list[0].get("term") if "term" in classification_list[0] else None
                print(f"Classification term for {standard_uri}: {term}")
                enriched_results[standard_uri] = term
            else:
                print(f"Unexpected response format for {standard_uri}: {classification_list}")
                enriched_results[standard_uri] = None
        else:
            print(f"Failed to classify {standard_uri}: HTTP {response.status_code}")
            enriched_results[standard_uri] = None

    print(enriched_results)

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
    print(sparql_update)

    # Headers for the SPARQL update request
    headers = {
        "Content-Type": "application/sparql-update"
    }

    # Send the POST request
    response = requests.post(source_endpoint, data=sparql_update.encode('utf-8'), headers=headers)

    # Check response
    if response.status_code == 200:
        print("SPARQL update successful!")
    else:
        print(f"Error {response.status_code}: {response.text}")
    pass

@flow
def enrichment_flow(graph_uri: str, source_endpoint: str, job_id: str = None):
    print(f"Starting enrichment for job_id={job_id}")
    data = fetch_data(source_endpoint, graph_uri)
    enrich_graph(source_endpoint, graph_uri, data)
    print(f"Completed enrichment for job_id={job_id}")