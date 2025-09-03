from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON, XML, CSV, TSV, TURTLE, RDF, N3, POST
from SPARQLWrapper.SPARQLExceptions import SPARQLWrapperException

def execute_sparql_query(endpoint, query, return_format, query_type, username, password):
    """Execute using SPARQLWrapper with authentication"""
    logger = get_run_logger()

    sparql = SPARQLWrapper(endpoint)
    
    # Set credentials if provided
    if (username is not None and password is not None):
        logger.info(f"[SPARQL] enabling authentication")
        sparql.setCredentials(username, password)
        sparql.setHTTPAuth("DIGEST")
    
    sparql.setQuery(query)
    try:
        if query_type.lower() == 'update' or query_type.lower() == 'delete':
            # For UPDATE operations, we don't need to set return format
            sparql.setMethod('POST')
            result = sparql.query()
            logger.info(f"[SPARQL] posting data to {endpoint} - Success")
            return {"status": "success", "message": result.response.read().decode("utf-8"), "http_code": 200}
        else:
            # Only set return format for SELECT/ASK/CONSTRUCT/DESCRIBE queries
            sparql_formats = {
                'json': JSON,
                'xml': XML,
                'csv': CSV,
                'tsv': TSV,
                'turtle': TURTLE,
                'rdf': RDF,
                'n3': N3
            }
            sparql.setReturnFormat(sparql_formats.get(return_format.lower(), JSON))
            
            result = sparql.query().convert()
            logger.info(f"[SPARQL] Query successful")
            return {"data": result, "http_code": 200}
            
    except SPARQLWrapperException as e:
        logger.error(f"[SPARQL] query failed: {e}")
        # Try to extract HTTP code from exception message if possible
        error_msg = str(e)
        http_code = None
        if "401" in error_msg:
            http_code = 401
        elif "403" in error_msg:
            http_code = 403
        elif "404" in error_msg:
            http_code = 404
        elif "500" in error_msg:
            http_code = 500
            
        return {"status": "error", "message": error_msg, "http_code": http_code}

def execute_sparql_select(endpoint, query, return_format='json', username=None, password=None):
    """Execute SPARQL SELECT/ASK/CONSTRUCT/DESCRIBE queries"""
    return execute_sparql_query(endpoint, query, return_format, 'select', username, password)

def execute_sparql_update(endpoint, update_query, username=None, password=None):
    """Execute SPARQL UPDATE operations"""
    return execute_sparql_query(endpoint, update_query, None, 'update', username, password)

def execute_sparql_delete(endpoint, update_query, username=None, password=None):
    """Execute SPARQL UPDATE operations"""
    return execute_sparql_query(endpoint, update_query, None, 'delete', username, password)