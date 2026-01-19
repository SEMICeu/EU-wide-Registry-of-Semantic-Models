from prefect import task, get_run_logger
from pathlib import Path
import requests


@task
def initialize_graphdb_repo(repo_name: str, config_file_path: str, host: str = "http://localhost:7200") -> str:
    """
    Create a new repository in GraphDB. (Overwrite if repo exists)

    :param str repo_name: Name/ID of the repository to create.
    :config_file_path: path to the graphDB config file for repository creation 
    :param str host: Base URL of the GraphDB server.

    :return: SPARQL endpoint URL of the created repository.
    """
    logger = get_run_logger()

    check_url = f"{host}/rest/repositories/{repo_name}"
    check_response = requests.get(check_url)

    repo_url= f"{host}/repositories/{repo_name}"
    
    if check_response.status_code == 200:
        logger.info(f"Repository '{repo_name}' already exists.")
        return repo_url


    logger.info(f"Repository '{repo_name}' does not exists, creating new repo...")
    
    config_file = Path(__file__).parents[2] / config_file_path

    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    
    config_ttl = config_file.read_text().format(repo_id=repo_name)

    url = f"{host}/rest/repositories"

    files = {
        "config": (f"{repo_name}.ttl", config_ttl, "text/turtle")
    }

    response = requests.post(url, files=files)

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create repository: {response.status_code}, {response.text}")

    logger.info(f"Repository '{repo_name}' created successfully")

    return repo_url