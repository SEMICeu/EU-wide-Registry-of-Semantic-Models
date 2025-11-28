from typing import Dict, Any
from prefect import flow, task, get_run_logger
from rdflib import Graph
import requests


def extract_conforms(jsonld: dict) -> bool | None:

    logger = get_run_logger()
    nodes = jsonld.get("@graph", [jsonld])

    for node in nodes:
        if "sh:conforms" in node:
            val = node["sh:conforms"]
            logger.info(f"SHACL sh:conforms = {val}")
            if isinstance(val, dict):
                return val.get("@value") in ["true", True]
            if isinstance(val, bool):
                return val
    return None


@task(name="Validate", retries=3, retry_delay_seconds=120)
def validate_data_graph(
    data: str,
    api_url: str,
    payload_template: Dict[str, Any],
    headers: Dict[str, str]
) -> bool:    
    """
    Validate the enriched data using SHACL.
    """
    logger = get_run_logger()

    if isinstance(data, bytes):
        data = data.decode("utf-8")

    payload = payload_template.copy()
    payload["contentToValidate"] = data

    g = Graph()
    g.parse(data=data, format='turtle')

    try:
        response = requests.post(url=api_url, json=payload, headers=headers)
        logger.info(f"SHACL response: {response.text}")

        if response.status_code != 200:
            logger.error(f"Validation failed (HTTP): {response.status_code}")
            return False

        try:
            json_data = response.json()
        except Exception:
            logger.error("Response is not valid JSON.")
            return False

        conforms = extract_conforms(json_data)

        if conforms is None:
            logger.error("Could not find sh:conforms in SHACL response.")
            return False

        if conforms is True:
            logger.info("SHACL validation PASSED.")
            return True
        else:
            logger.error("SHACL validation FAILED (conforms = false).")
            return False

    except Exception as e:
        logger.error(f"Connection Error: {e}")
        return False