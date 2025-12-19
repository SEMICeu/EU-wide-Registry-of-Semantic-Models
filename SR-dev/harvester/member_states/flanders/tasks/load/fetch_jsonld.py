from prefect import task, get_run_logger
from bs4 import BeautifulSoup
import requests
import json


@task(name="Extract JSON-LD", retries=3, retry_delay_seconds=120)
def fetch_jsonld(web_url: str) -> dict:
    """
    Extract JSON-LD from a Vlaanderen standards page.

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