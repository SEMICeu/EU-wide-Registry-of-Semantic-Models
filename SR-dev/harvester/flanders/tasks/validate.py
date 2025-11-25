from prefect import flow, task, get_run_logger
from pyshacl import validate
from rdflib import Graph
import requests


@task(name="Validate", retries=3, retry_delay_seconds=120)
def validate_data_graph(data: str) -> bool:

    """

    Task 4: Validate the enriched data

    This task will run in parallel for each enriched item

    """

    logger = get_run_logger()

    g = Graph()
    g.parse(data=data, format='turtle')
    shacle_graph= Graph()
    
    url = "https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.0/shacl/srm-SHACL.ttl"
    try:
        response = requests.get(url)

        if response.status_code == 200:
            shacle_graph.parse(data=response.text, format='turtle')
            logger.info(f"shacl_graph: {response.text}")
        
            
    except Exception as e:
            logger.error(f"Connection Error: {e}")

    try:

        logger.info("Checking input data is turtle format")
        result = validate(g, shacle_graph)

        conforms, results_graph, results_text = result

        if conforms:
            logger.info(f"Validation passed")
            logger.warning(f"result graph {results_graph}")
            logger.warning(f"result text {results_text}")

        else:
            logger.warning(f"Validation failed for {results_graph}")
            logger.warning(f"Validation failed for {results_text}")
            logger.warning(f"Input Data: {data}")


        return conforms

    except Exception as e:

        logger.error(f"Format not in turtle: {str(e)}")

        raise
 