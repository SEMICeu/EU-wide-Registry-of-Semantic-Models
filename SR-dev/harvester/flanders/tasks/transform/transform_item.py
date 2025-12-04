from ast import parse
from prefect import task, get_run_logger
from typing import List

from rdflib import Graph, RDF, Namespace, Literal
from rdflib.namespace import XSD
from db.client import get_sparql_client
from SPARQLWrapper import TURTLE
from string import Template


@task(
    name="transform item", 
    retries=3, 
    retry_delay_seconds=60,
    timeout_seconds=300
)
async def transform_item(batch: str) -> str:
    """
    ...
    """
    
    logger = get_run_logger()
    logger.info(f"Transforming batch: {batch}")  
 
    try:
       source_graph = Graph()
       source_graph.parse(data=batch, format="turtle")

       target_graph = Graph()
       ADMS = Namespace("http://www.w3.org/ns/adms#")
       DCT = Namespace("http://purl.org/dc/terms/")
       target_graph.bind("adms", ADMS)
       target_graph.bind("dct", DCT)

       # adms:Asset
       for s, p, o in source_graph.triples((None, RDF.type, DCT.Standard)):
            target_graph.add((s, RDF.type, ADMS.Asset))

       # adms:Asset/dct:created
       for s, p , o in source_graph.triples((None, DCT.created, None)):
            target_graph.add((s, DCT.created, o))

       # adms:Asset/dct:identifier
       for s, p , o in source_graph.triples((None, DCT.identifier, None)):
            target_graph.add((s, DCT.identifier, o))

       # adms:Asset/dct:issued
       dateList = [] 
       for s, p, o in source_graph.triples((None, DCT.issued, None)):
            if str(o) == "N.v.t.":
                logger.info(f"Skipping N.v.t: {latest_date}")
                continue
            try:
                date_value = o.toPython()
                dateList.append(date_value)
            except:
                logger.info(f"Could not convert date: {o}")
                continue

       if dateList:
            latest_date = max(dateList)
            logger.info(f"Latest date: {latest_date}")
            latest_date_literal = Literal(latest_date, datatype=XSD.dateTime)
            target_graph.add((s, DCT.issued, latest_date_literal))

       target_data = target_graph.serialize(format="turtle")

       logger.info(f"Transformed target Data: {target_data}")
       return target_data
        
    except Exception as e:
        logger.error(f"Transofrmation FAILED for batch: {batch}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise 