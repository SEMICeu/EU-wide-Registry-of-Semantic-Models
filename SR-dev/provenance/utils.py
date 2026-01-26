from prefect import get_run_logger
import requests

def load_data_to_prov_graphdb(
    rdf_data: str, 
    graphdb_endpoint: str, 
    format: str = "json-ld"
) -> bool:
    """
    Load provenance RDF data into GraphDB.

    :param rdf_data: RDF content as string (Turtle, N-Triples, JSON-LD, etc.)
    :param graphdb_endpoint: SPARQL endpoint URL
    :param format: RDF format ("turtle", "json-ld", "xml", "nt", "n3")
    :return: True if upload successful, False otherwise
    """
    logger = get_run_logger()
    
    content_types = {
        "turtle": "text/turtle",
        "json-ld": "application/ld+json",
        "xml": "application/rdf+xml",
        "nt": "application/n-triples",
        "n3": "text/n3"
    }
    
    content_type = content_types.get(format, "application/ld+json")
    
    logger.info(f"Uploading {len(rdf_data)} bytes as {format}")
    
    try:
        response = requests.post(
            f"{graphdb_endpoint}/statements",
            data=rdf_data,
            headers={"Content-Type": content_type}
        )
        response.raise_for_status()

        if response.status_code == 204:
            logger.info("Upload to provenance GraphDB completed")
            return True
        else:
            logger.error(f"Upload failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise
