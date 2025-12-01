from prefect import task, get_run_logger
from bs4 import BeautifulSoup
from SPARQLWrapper import TURTLE
from rdflib import Graph
from pathlib import Path
import requests
import json

from sqlalchemy import false


@task(name="Extract JSON-LD", retries=3, retry_delay_seconds=120)
def fetch_jsonld(web_url: str) -> dict:
    """
    Task 1: Extract JSON-LD from a Vlaanderen standards page.

    :param str web_url: URL to fetch.
    :return: Parsed JSON-LD.
    """
    logger = get_run_logger()
    logger.info(f"Crawling {web_url}")

    try:
        response = requests.get(web_url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        script_tag = soup.find("script", {"id": "standards-jsonld", "type": "application/ld+json"})
        if not script_tag:
            raise ValueError("Could not find JSON-LD script tag in page")

        jsonld_text = script_tag.text.strip()
        jsonld_data = json.loads(jsonld_text)

        logger.info("JSON-LD successfully extracted")
        logger.info(jsonld_data)

        return jsonld_data

    except Exception as e:
        return Exception(f"Error extracting JSON-LD from {web_url}")



@task
def initialize_graphdb_repo(repo_name: str, config_file_path: str, host: str = "http://localhost:7200") -> str:
    """
    Task 2: Create a new repository in GraphDB. (Overwrite if repo exists)

    :param str repo_name: Name/ID of the repository to create.
    :config_file_path: path to the graphDB config file for repository creation 
    :param str host: Base URL of the GraphDB server.

    :return: SPARQL endpoint URL of the created repository.
    """
    logger = get_run_logger()

    check_url = f"{host}/rest/repositories/{repo_name}"
    check_response = requests.get(check_url)
    
    if check_response.status_code == 200:
        logger.info(f"Repository '{repo_name}' already exists. Deleting it...")
        delete_response = requests.delete(check_url)
        
        if delete_response.status_code in (200, 204):
            logger.info(f"Repository '{repo_name}' deleted successfully")
        else:
            logger.warning(f"Failed to delete repository: {delete_response.status_code}, {delete_response.text}")

    
    config_file = Path(__file__).parents[1] / config_file_path

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

    return f"{host}/repositories/{repo_name}"



@task(name="Load JSON-LD into GraphDB")
def load_jsonld_to_graphdb(jsonld_data: dict, graphdb_endpoint: str) -> bool:
    """
    Task 3: Load JSON-LD into GraphDB as RDF triples.

    :param dict jsonld_data: JSON-LD content to convert and upload.
    :param str graphdb_endpoint: SPARQL endpoint URL of the target repository.
    """

    logger = get_run_logger()
    g = Graph()
    g.parse(data=json.dumps(jsonld_data), format="json-ld")

    logger.info(f"Parsed {len(g)} RDF triples")

    turtle_data = g.serialize(format="turtle")

    response = requests.post(f"{graphdb_endpoint}/statements",
                     data=turtle_data,
                     headers={"Content-Type": "text/turtle"})
    response.raise_for_status()

    if response.status_code == 204:
        logger.info("Upload to GraphDB completed")
        return True
    else:
        logger.error(f"Upload failed with status {response.status_code}")
        return False
