from string import Template
import requests
from prefect import task, get_run_logger


@task(
    name="cleanup provenance graphdb",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
)
def cleanup_provenance_graphdb(
    repo_name: str,
    cleanup_query: str,
    keep_latest: int = 2,
    host: str = "http://localhost:7200",
) -> bool:
    """
    Clean up provenance GraphDB using a SPARQL DELETE query.
    Keeps only the N most recent executions based on endedAtTime.

    :param repo_name: Name/ID of the GraphDB repository
    :param cleanup_query: SPARQL DELETE query template with $keep_latest placeholder
    :param keep_latest: Number of latest executions to keep
    :param host: Base URL of the GraphDB server
    :return: True if cleanup successful, False otherwise
    """
    logger = get_run_logger()
    logger.info(f"Starting provenance cleanup – keeping latest {keep_latest} executions")

    check_url = f"{host}/rest/repositories/{repo_name}"
    update_url = f"{host}/repositories/{repo_name}/statements"

    check_response = requests.get(check_url)
    if check_response.status_code != 200:
        logger.error(f"Repository '{repo_name}' does not exist")
        return False

    logger.info(f"Repository '{repo_name}' exists")

    try:
        template = Template(cleanup_query)
        query = template.safe_substitute(keep_latest=keep_latest)

        logger.info(f"Executing DELETE query:\n{query}")

        response = requests.post(
            update_url,
            data={"update": query},
            timeout=120,
        )

        if response.status_code in (200, 204):
            logger.info(f"✓ Cleanup completed successfully (status {response.status_code})")
            return True

        logger.error(
            f"✗ Cleanup failed (status {response.status_code}): {response.text}"
        )
        return False

    except Exception:
        logger.exception("Failed to cleanup provenance GraphDB")
        return False