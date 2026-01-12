from cProfile import label
from prefect import task, get_run_logger
from typing import List
from ...db.client import get_sparql_client
from SPARQLWrapper import TURTLE
from string import Template
import ssl
import urllib3
import os

@task(
    name="construct item", 
    retries=3, 
    retry_delay_seconds=60,
    timeout_seconds=300
)
async def construct_item(batch: str, db_path: str, construct_query: str) -> List[str]:
    """
    Construct items from a batch using a SPARQL query.

    :param batch: A batch of identifiers or input items to process.
    :param db_path: Path or endpoint of the GraphDB repository.
    :param construct_query: SPARQL query string used to construct the items.
    :return: List of strings representing the constructed items for the batch.
    """

    logger = get_run_logger()

    query_template = construct_query

    logger.info(f"Constructing list for batch: {batch}")  
 
    try:
        template = Template(query_template)
        query = template.substitute(uri=batch[0])
        
        logger.info(f"Query to execute:\n{query[:500]}") 

        sparql = get_sparql_client(db_path)

        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        ssl._create_default_https_context = ssl._create_unverified_context

        os.environ['CURL_CA_BUNDLE'] = ''
        os.environ['REQUESTS_CA_BUNDLE'] = ''
        os.environ['PYTHONHTTPSVERIFY'] = '0'

        sparql.setQuery(query)
        sparql.setReturnFormat(TURTLE)
        sparql.setTimeout(120) 
        
        logger.info(f"Executing query...")
        results = sparql.query().convert()
        
        result_size = len(results) if isinstance(results, (str, bytes)) else "unknown"
        logger.info(f"Query completed. Result size: {result_size} bytes")
        logger.info(f"construct item result: {results}")

        return results
        
    except Exception as e:
        logger.error(f"Constructing FAILED for batch: {batch}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise 


async def get_class_label(class_uri, predicate, db_path: str, construct_query: str) -> List[str]:
    """
    Construct items from a batch using a SPARQL query.

    :param batch: A batch of identifiers or input items to process.
    :param db_path: Path or endpoint of the GraphDB repository.
    :param construct_query: SPARQL query string used to construct the items.
    :return: List of strings representing the constructed items for the batch.
    """

    logger = get_run_logger()

    query_template = construct_query

    logger.info(f"retrieving labels for rdfs:Class: {class_uri}")  
 
    try:
        template = Template(query_template)
        query = template.substitute(uri=class_uri, label=predicate)
        
        logger.info(f"Query to execute:\n{query[:500]}") 

        sparql = get_sparql_client(db_path)

        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        ssl._create_default_https_context = ssl._create_unverified_context

        os.environ['CURL_CA_BUNDLE'] = ''
        os.environ['REQUESTS_CA_BUNDLE'] = ''
        os.environ['PYTHONHTTPSVERIFY'] = '0'

        sparql.setQuery(query)
        sparql.setReturnFormat(TURTLE)
        sparql.setTimeout(120) 
        
        logger.info(f"Executing query...")
        results = sparql.query().convert()
        
        result_size = len(results) if isinstance(results, (str, bytes)) else "unknown"
        logger.info(f"Query completed. Result size: {result_size} bytes")
        logger.info(f"construct item result: {results}")

        return str(results)
        
    except Exception as e:
        logger.error(f"Constructing FAILED for batch: {class_uri}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise 