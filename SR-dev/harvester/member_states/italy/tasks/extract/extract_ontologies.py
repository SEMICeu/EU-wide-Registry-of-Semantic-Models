from prefect import task, get_run_logger
from typing import  List
import pandas as pd


@task(name="Extract List from result dataframe")
def extract_list_from_result(df: pd.DataFrame) -> List[str]:
    """
    Extracting a list of owl:Ontology from a dataframe

    :param df: dataframe containing for each entry owl:Ontology and dct:issued / dct:moddified
    """

    logger = get_run_logger()
    logger.info("Extract List from result dataframe")

    try:
        list_ontologies = df[df.columns[0]].tolist()
    
        logger.info(f"{len(list_ontologies)} items in ontology list")
        logger.info(f"first list item: {list_ontologies[0]}")
        return list_ontologies

    except Exception as e:
        logger.error(f"Error extracting list from dataframe: {e}")
        return