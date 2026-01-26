from prefect import task, get_run_logger
from typing import  List
import pandas as pd
from ...db.client import get_sparql_client
from cProfile import label
from prefect import task, get_run_logger
from typing import List, Optional
from ...db.client import get_sparql_client
from SPARQLWrapper import JSON
from prefect.cache_policies import NONE as NO_CACHE
from string import Template
import ssl
import urllib3
import os
from datetime import datetime
from typing import List, Optional
from string import Template
import requests
from prefect import task, get_run_logger

@task(
    name="extract provenance date", 
    retries=3, 
    retry_delay_seconds=60,
    timeout_seconds=300,
    cache_policy=NO_CACHE
)
def extract_last_provenance_date(repo_name: str, extract_provenance_date_query: str,  host: str = "http://localhost:7200") -> str:
    """
    returns the date from the provenance db when last the pipeline has been run.

    :param repo_name: Path or endpoint of the GraphDB repository.
    :param extract_provenance_date_query: SPARQL query to extract date.
    :return: date in string format
    """

    logger = get_run_logger()


    logger.info(f"Extracting last provenance date from {repo_name}")  
 
    try:
    
        endpoint = f"{host}/repositories/{repo_name}"
        sparql = get_sparql_client(endpoint)

        # Disable SSL warnings
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        ssl._create_default_https_context = ssl._create_unverified_context

        os.environ['CURL_CA_BUNDLE'] = ''
        os.environ['REQUESTS_CA_BUNDLE'] = ''
        os.environ['PYTHONHTTPSVERIFY'] = '0'

        sparql.setQuery(extract_provenance_date_query)
        sparql.setReturnFormat(JSON)
        sparql.setTimeout(120) 
        
        logger.info(f"Executing query...")
        result = sparql.query().convert()
        
        result_size = len(result) if isinstance(result, (str, bytes)) else "unknown"
        logger.info(f"Query completed. Result size: {result_size} bytes")

        logger.info(f"Last date when provenance pipeline was run: {result}")

        # Parse JSON results
        if result and "results" in result and "bindings" in result["results"]:
            bindings = result["results"]["bindings"]
            
            if bindings:
                # Get the first result (latest end time)
                end_time = bindings[0].get("endTime", {}).get("value")
                
                if end_time:
                    logger.info(f"✓ Last provenance pipeline run: {end_time}")
                    # return "2016-01-21T14:30:10.406435"
                    return end_time
                else:
                    logger.warning("No endTime value found in results")
                    return None
            else:
                logger.warning("No provenance data found in GraphDB")
                return None
        else:
            logger.warning("Invalid SPARQL results format")
            return None
        
    except Exception as e:
        logger.error(f"Failed extracting provenance date for: {endpoint}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise

@task(
    name="cleanup provenance graphdb",
    retries=2,
    retry_delay_seconds=30,
    timeout_seconds=300,
)
def delete_entries_for_provenance(
    asset_to_delete: str,
    repo_name: str,
    cleanup_query: str,
    host: str = "http://localhost:7200",
    enable_provenance: bool =True
) -> bool:
    """
    Deletes entries which have been flaged for re-harvisting by the provenence step

    :param repo_name: Name/ID of the GraphDB repository
    :param cleanup_query: SPARQL DELETE query template with $keep_latest placeholder
    :param asset_to_delete: asset entrie to delete
    :param host: Base URL of the GraphDB server
    :return: True if cleanup successful, False otherwise
    """

    if enable_provenance:
        logger = get_run_logger()
        logger.info(f"Deleting entries before re-harvesting as identified by provenance step")

        check_url = f"{host}/rest/repositories/{repo_name}"
        update_url = f"{host}/repositories/{repo_name}/statements"

        check_response = requests.get(check_url)
        if check_response.status_code != 200:
            logger.error(f"Repository '{repo_name}' does not exist")
            return False

        logger.info(f"Repository '{repo_name}' exists")


        try:

            template = Template(cleanup_query)
            query = template.safe_substitute(uri=str(asset_to_delete))

            logger.info(f"Executing DELETE query:\n{query}")

            response = requests.post(
                update_url,
                data={"update": query},
                timeout=120,
            )

            if response.status_code in (200, 204):
                logger.info(f"✓ Successfully deleted entry for subject {asset_to_delete} - {response.status_code})")
                return True

            logger.error(
                f"✗ Failed to delete entry for subject {asset_to_delete} - {response.status_code}): {response.text}"
            )
            return False

        except Exception:
            logger.exception("Failed Delete entries before re-harvesting")
            return False
    else:
        logger.info("provenance disabled, skipping deleting entries")

@task(
    name="Extract List from result dataframe",
    cache_policy=NO_CACHE
)
def extract_list_from_result(df: pd.DataFrame, provenance_date: Optional[str] = None,  enable_provenance: bool =True) -> List[str]:
    """
    Extract a list of owl:Ontology from a dataframe, filtering by date.
    
    Only includes entries where dct:issued or dct:modified is later than the provenance_date.

    :param df: dataframe containing owl:Ontology, dct:issued, and dct:modified columns
    :param provenance_date: ISO format date string from last pipeline run
    :return: List of ontology URIs to process
    """
    logger = get_run_logger()
    logger.info("Extracting list from result dataframe")
    
    logger.info(f"DataFrame shape: {df.shape}")
    logger.info(f"DataFrame columns: {df.columns.tolist()}")

    try:
 
        if not provenance_date or not enable_provenance:
            if not enable_provenance:
                logger.info("Provenance disabled")
            elif not provenance_date:
                logger.info("No provenance date provided - returning all entries")
            list_ontologies = df[df.columns[0]].tolist()
            logger.info(f"✓ {len(list_ontologies)} items in ontology list")
            if list_ontologies:
                logger.info(f"First item: {list_ontologies[0]}")
            return list_ontologies
        
        try:
            provenance_dt = datetime.fromisoformat(provenance_date.replace('Z', '+00:00'))
            logger.info(f"Filtering entries newer than: {provenance_dt}")
        except Exception as e:
            logger.warning(f"Could not parse provenance date '{provenance_date}': {e}")
            logger.info("Returning all entries due to invalid provenance date")
            list_ontologies = df[df.columns[0]].tolist()
            return list_ontologies
        
        ontology_col = df.columns[0]
        issued_col = df.columns[1]
        modified_col = df.columns[2]
        
        filtered_ontologies = []
        skipped_count = 0
        
        logger.info("Starting provenance check...")

        for idx, row in df.iterrows():
            ontology_uri = row[ontology_col]
            should_include = False
            
            if issued_col and pd.notna(row[issued_col]):
                try:
                    issued_dt = datetime.fromisoformat(str(row[issued_col]).replace('Z', '+00:00'))
                    if issued_dt > provenance_dt:
                        should_include = True
                        logger.debug(f"  ✓ Issued date {issued_dt} > provenance date")
                except Exception as e:
                    logger.debug(f"  Could not parse issued date for {ontology_uri}: {e}")
            
            if modified_col and pd.notna(row[modified_col]):
                try:
                    modified_dt = datetime.fromisoformat(str(row[modified_col]).replace('Z', '+00:00'))
                    if modified_dt > provenance_dt:
                        should_include = True
                        logger.debug(f"  ✓ Modified date {modified_dt} > provenance date")
                except Exception as e:
                    logger.debug(f"  Could not parse modified date for {ontology_uri}: {e}")
            
            if should_include:
                filtered_ontologies.append(ontology_uri)
                logger.debug(f"✓ Including: {ontology_uri} issued: {issued_dt} - modified: {modified_dt}")
            else:
                skipped_count += 1
                logger.info(f"⊗ Skipping entry, already harvested: {ontology_uri}")
        
        logger.info(f"✓ Filtered results: {len(filtered_ontologies)} new entries, {skipped_count} already harvested")
        
        if filtered_ontologies:
            logger.info(f"First new item: {filtered_ontologies[0]}")

        else:
            logger.info("No new entries to process")
        
        return filtered_ontologies

    except Exception as e:
        logger.error(f"Error extracting list from dataframe: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        raise