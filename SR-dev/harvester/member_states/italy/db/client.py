from SPARQLWrapper import SPARQLWrapper, JSON

def get_sparql_client(endpoint_url: str) -> SPARQLWrapper:
    """
    Initialize and return a configured SPARQL client.

    Args:
        endpoint_url (str): URL of the SPARQL endpoint.

    Returns:
        SPARQLWrapper: Configured SPARQL client.
    """
    import requests
    from SPARQLWrapper import SPARQLWrapper
    from urllib3.exceptions import InsecureRequestWarning
    
    # Suppress the insecure request warning (optional)
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    
    # Create a session with SSL verification disabled
    session = requests.Session()
    session.verify = False
 
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setReturnFormat(JSON)
    sparql.setMethod("POST")
    return sparql
