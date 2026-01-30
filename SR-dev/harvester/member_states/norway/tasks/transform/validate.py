from typing import Dict, Any
from prefect import flow, task, get_run_logger
from ...config import load_config
from ......provenance.tracker import ProvenanceTracker
import requests
import json


def extract_conforms(jsonld: dict) -> bool | None:
    """
    Extract 'conforms' property from the JSON-LD object returned by the ITB SHACL validation.

    :param jsonld: JSON-LD object returned by the ITB SHACL validation.
    :return: boolean.
    """

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


@task(name="Validate")
def validate_data_graph(
    data: str,
    api_url: str,
    payload_template: Dict[str, Any],
    headers: Dict[str, str],
    tracker: ProvenanceTracker
) -> dict[str,any]:    
    """
    Validate enriched data using SHACL.

    :param data: RDF or JSON-LD content to be validated.
    :param api_url: URL of the SHACL validation service.
    :param payload_template: Template for the validation request payload.
    :param headers: HTTP headers for the validation request.
    :param tracker: provenanceTracker for writing failed entries to a report

    :return: Dictionary containing the validation results and status.
    """
    
    logger = get_run_logger()
    config = load_config()

    if isinstance(data, bytes):
        data = data.decode("utf-8")

    payload = payload_template.copy()
    payload["contentToValidate"] = data

    try:
        response = requests.post(url=api_url, json=payload, headers=headers)
        logger.info(f"---payload--- \n{payload}")
        logger.info(f"---SHACL response--- {response.text}")

        if response.status_code != 200:
            logger.error(f"Validation failed (HTTP): {response.status_code}")
            raise ValueError(f"HTTP error {response.status_code}: {response.text}")

        try:
            json_data = response.json()
        except Exception:
            logger.error("Response is not valid JSON.")
            raise ValueError(f"Invalid JSON response: {response.text}") from e

        conforms = extract_conforms(json_data)

        if conforms is None:
            logger.error("Could not find sh:conforms in SHACL response.")
            raise ValueError("Missing sh:conforms in SHACL validation response")

        if conforms is True:
            logger.info("SHACL validation PASSED.")
            return payload
        else:
            logger.error("SHACL validation FAILED (conforms = false).")

            shacl_report = json.dumps(json_data, indent=2)

            tracker.write_failed_validation_to_report(
                member_state=config["member_state"],
                failed_validation=shacl_report,
                report_path=config["provenance_report_path"]
            )

            raise ValueError("SHACL validation failed: conforms = false")


    except Exception as e:
        logger.error(f"Connection Error: {e}")
        raise
