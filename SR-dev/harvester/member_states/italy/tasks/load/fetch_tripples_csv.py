from prefect import task, get_run_logger
import requests
from urllib.parse import quote
import requests
import pandas as pd
from io import StringIO

def url_encode_sparql_query(web_url: str, format_params: str, sparql_query: str):
    """
    Helper function for url encoding a sparql query to be executed on an endpoint (schema.gov.it in this case)

    :param str web_url: url of the endpoint
    :param str format_params: custom uri params needed to execute the query
    :param str sparql_query: sparql query to be executed

    :return: complete encoded url
    """
    encoded_query = quote(sparql_query, safe='')
    
    encoded_url = f"{web_url}{encoded_query}{format_params}"
    
    return encoded_url
 

@task(name="fetch entries with SPARQL query", retries=3, retry_delay_seconds=120)
def fetch_sparql_to_csv(web_url: str, format_params: str, sparql_query: str) -> str:
    """
    Execute a sparql query and store CSV returned results in dataframa

    :param str web_url: url of the endpoint
    :param str format_params: custom uri params needed to execute the query
    :param str sparql_query: sparql query to be executed

    :return: dataframe containing results
    """

    logger = get_run_logger()
    logger.info(f"fetch entries with SPARQL query")

    try:
        encoded_url = url_encode_sparql_query(web_url, format_params, sparql_query)
        
        headers = {
            "Accept": "text/csv"
        }
        response = requests.get(encoded_url, headers=headers)
        
        if response.status_code == 200:
            logger.info(f"request SUCCESFULL for encoded_url: {encoded_url}")
            df = pd.read_csv(StringIO(response.text))
            
            logger.info(f"CSV file counts {df.shape[0]} rows")
            logger.info(f"Top 5 rows: \n {df.head}")

            return df
        else:
            logger.errer(f"request FAILED for encoded_url: {encoded_url}")
            response.raise_for_status()
            
    except Exception as e:
        print(f"Error fetching or parsing SPARQL data: {e}")
        raise