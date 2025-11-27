from prefect import flow, task, get_run_logger
from rdflib import Graph
import requests


@task(name="Validate", retries=3, retry_delay_seconds=120)
def validate_data_graph(data: str) -> bool:
    """
    Validate the enriched data using SHACL.
    """
    logger = get_run_logger()

    # Ensure data is a string
    if isinstance(data, bytes):
        data = data.decode("utf-8")

    g = Graph()
    g.parse(data=data, format='turtle')
    
    url = "http://localhost:8080/shacl/srm/api/validate"
    payload = {
        "version": "v3.0.0",
        "contentSyntax": "text/turtle",
        "contentToValidate": data    
    }
   
    headers = {
        "Accept": "application/ld+json",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url=url, json=payload, headers=headers)
        logger.info(f"SHACL response: {response.text}")

        if response.status_code == 200:
            return True
        else:
            logger.error(f"Validation failed: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Connection Error: {e}")
        return False


    # try:

    #     logger.info("Checking input data is turtle format")
    #     result = validate(g, shacle_graph)

    #     conforms, results_graph, results_text = result

    #     if conforms:
    #         logger.info(f"Validation passed")
    #         logger.warning(f"result graph {results_graph}")
    #         logger.warning(f"result text {results_text}")

    #     else:
    #         logger.warning(f"Validation failed for {results_graph}")
    #         logger.warning(f"Validation failed for {results_text}")
    #         logger.warning(f"Input Data: {data}")


    #     return conforms

    # except Exception as e:

    #     logger.error(f"Format not in turtle: {str(e)}")

    #     raise
 