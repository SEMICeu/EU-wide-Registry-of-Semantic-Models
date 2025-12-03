from prefect import task, get_run_logger
from SPARQLWrapper import TURTLE
from rdflib import Graph
from typing import Union
import requests
import json

@task(name="Load RDF into GraphDB")
def load_data_to_graphdb(
    data: Union[str, dict], 
    graphdb_endpoint: str, 
    format: str = "turtle"
) -> bool:
    """
    Load RDF data into GraphDB. Accepts both string-based RDF formats and JSON-LD dicts.

    :param data: RDF content as string (Turtle, N-Triples, etc.) or dict (JSON-LD)
    :param graphdb_endpoint: SPARQL endpoint URL
    :param format: RDF format ("turtle", "json-ld", "xml", "nt", etc.)
    """
    logger = get_run_logger()
    
    # Content type mapping
    content_types = {
        "turtle": "text/turtle",
        "json-ld": "application/ld+json",
        "xml": "application/rdf+xml",
        "nt": "application/n-triples",
        "n3": "text/n3"
    }
    
    # Handle JSON-LD dict specially
    if isinstance(data, dict):
        if format != "json-ld":
            logger.warning(f"Data is dict but format is '{format}'. Assuming JSON-LD.")
            format = "json-ld"
        data = json.dumps(data)
    
    # Ensure data is string at this point
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    
    content_type = content_types.get(format, "text/turtle")
    
    logger.info(f"Uploading {len(data)} bytes as {format}")
    
    try:
        response = requests.post(
            f"{graphdb_endpoint}/statements",
            data=data,
            headers={"Content-Type": content_type}
        )
        response.raise_for_status()

        if response.status_code == 204:
            logger.info("Upload to GraphDB completed")
            return True
        else:
            logger.error(f"Upload failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise

# @task(name="Load JSON-LD into GraphDB")
# def load_jsonld_to_graphdb(jsonld_data: dict, graphdb_endpoint: str) -> bool:
#     """
#     Task 3: Load JSON-LD into GraphDB as RDF triples.

#     :param dict jsonld_data: JSON-LD content to convert and upload.
#     :param str graphdb_endpoint: SPARQL endpoint URL of the target repository.
#     """

#     logger = get_run_logger()
#     g = Graph()
#     g.parse(data=json.dumps(jsonld_data), format="json-ld")

#     logger.info(f"Parsed {len(g)} RDF triples")

#     turtle_data = g.serialize(format="turtle")

#     response = requests.post(f"{graphdb_endpoint}/statements",
#                      data=turtle_data,
#                      headers={"Content-Type": "text/turtle"})
#     response.raise_for_status()

#     if response.status_code == 204:
#         logger.info("Upload to GraphDB completed")
#         return True
#     else:
#         logger.error(f"Upload failed with status {response.status_code}")
#         return False