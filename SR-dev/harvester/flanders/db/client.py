from SPARQLWrapper import SPARQLWrapper, JSON

def get_sparql_client(endpoint_url: str) -> SPARQLWrapper:
    """
    Initialize and return a configured SPARQL client.

    Args:
        endpoint_url (str): URL of the SPARQL endpoint.

    Returns:
        SPARQLWrapper: Configured SPARQL client.
    """
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setReturnFormat(JSON)
    sparql.setMethod("POST")
    return sparql
