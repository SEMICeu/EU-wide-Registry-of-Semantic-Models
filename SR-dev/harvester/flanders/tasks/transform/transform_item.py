from ast import parse
from prefect import task, get_run_logger
from typing import List

from rdflib import Graph, RDF, Namespace, Literal, URIRef
from rdflib.namespace import XSD
from db.client import get_sparql_client
from SPARQLWrapper import TURTLE
from string import Template
import requests


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
        DCAT = Namespace("http://www.w3.org/ns/dcat#")
        VANN = Namespace("http://purl.org/vocab/vann/")
        FOAF = Namespace("http://xmlns.com/foaf/0.1/")
        SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
        SCHEMA = Namespace("http://schema.org/")
        VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")
        M8G = Namespace("http://data.europa.eu/m8g/")
        ORG = Namespace("http://www.w3.org/ns/org#")

        target_graph.bind("adms", ADMS)
        target_graph.bind("dct", DCT)
        target_graph.bind("vann", VANN)
        target_graph.bind("foaf", FOAF)
        target_graph.bind("skos", SKOS)
        target_graph.bind("schema", SCHEMA)
        target_graph.bind("vcard", VCARD)
        target_graph.bind("m8g", M8G)
        target_graph.bind("dcat", DCAT)
        target_graph.bind("org", ORG)

        # adms:Asset
        for s, p, o in source_graph.triples((None, RDF.type, ADMS.Asset)):
            target_graph.add((s, RDF.type, ADMS.Asset))

        # adms:Asset/dct:created
        created_by_subject = {}

        for s, p, o in source_graph.triples((None, DCT.created, None)):
            if str(o) == "N.v.t.":
                logger.info(f"dct:created - skipping N.v.t. for subject {s}")
                continue
            try:
                date_value = o.toPython()
                created_by_subject.setdefault(s, []).append(date_value)
            except Exception as e:
                logger.info(f"dct:created - could not convert date: {o} (error: {e})")
                continue

        for s, dates in created_by_subject.items():
            date_count = len(dates)

            if date_count == 1:
                dateTime = str(dates[0]) + "T00:00:00"
                target_graph.add((s, DCT.created, Literal(dateTime, datatype=XSD.dateTime)))
            elif date_count > 1:
                latest_date = max(dates)
                dateTime = str(latest_date) + "T00:00:00"

                logger.info(f"dct:created - subject {s} has {date_count} dates, keeping latest: {dateTime}")
                target_graph.add((s, DCT.created, Literal(dateTime, datatype=XSD.dateTime)))

        # adms:Asset/dct:identifier
        for s, p, o in source_graph.triples((None, DCT.identifier, None)):
            target_graph.add((s, DCT.identifier, o))

        # adms:Asset/dct:issued
        issued_by_subject = {}

        for s, p, o in source_graph.triples((None, DCT.issued, None)):
            if str(o) == "N.v.t.":
                logger.info(f"dct:issued - skipping N.v.t. for subject {s}")
                continue
            try:
                date_value = o.toPython()
                issued_by_subject.setdefault(s, []).append(date_value)
            except Exception as e:
                logger.info(f"dct:issued - could not convert date: {o} (error: {e})")
                continue

        for s, dates in issued_by_subject.items():
            date_count = len(dates)

            if date_count == 1:
                dateTime = str(dates[0]) + "T00:00:00"
                target_graph.add((s, DCT.issued, Literal(dateTime, datatype=XSD.dateTime)))
            elif date_count > 1:
                latest_date = max(dates)
                dateTime = str(latest_date) + "T00:00:00"

                logger.info(f"dct:issued - subject {s} has {date_count} dates, keeping latest: {dateTime}")
                target_graph.add((s, DCT.issued, Literal(dateTime, datatype=XSD.dateTime)))

        # adms:Asset/dct:language
        for s, p, o in source_graph.triples((None, DCT.language, None)):
            target_graph.add((s, DCT.language, o))
            target_graph.add((o, RDF.type, SKOS.Concept))

        # adms:Asset/dct:modified
        modified_by_subject = {}

        for s, p, o in source_graph.triples((None, DCT.modified, None)):
            if str(o) == "N.v.t.":
                logger.info(f"dct:modified - skipping N.v.t. for subject {s}")
                continue
            try:
                date_value = o.toPython()
                modified_by_subject.setdefault(s, []).append(date_value)
            except Exception as e:
                logger.info(f"dct:modified - could not convert date: {o} (error: {e})")
                continue

        for s, dates in modified_by_subject.items():
            date_count = len(dates)

            if date_count == 1:
                dateTime = str(dates[0]) + "T00:00:00"
                target_graph.add((s, DCT.modified, Literal(dateTime, datatype=XSD.dateTime)))
            elif date_count > 1:
                latest_date = max(dates)
                dateTime = str(latest_date) + "T00:00:00"

                logger.info(f"dct:modified - subject {s} has {date_count} dates, keeping latest: {dateTime}")
                target_graph.add((s, DCT.modified, Literal(dateTime, datatype=XSD.dateTime)))

        # adms:Asset/vann:preferredNamespaceUri
        for s, p, o in source_graph.triples((None, VANN.preferredNamespaceUri, None)):
            target_graph.add((s, VANN.preferredNamespaceUri, o))

        # adms:Asset/dct:title
        titles_by_subject = {}
        for s, p, o in source_graph.triples((None, DCT.title, None)):
            titles_by_subject.setdefault(s, []).append(o)

        for s, titles in titles_by_subject.items():
            title_count = len(titles)
            
            if title_count == 1:
                target_graph.add((s, DCT.title, titles[0]))
            elif title_count > 1:
                longest = max(titles, key=lambda t: len(str(t)))
                logger.info(
                    f"dct:title - more than 2 titles, keeping longest: '{longest}' "
                    f"({len(str(longest))} chars)"
                )
                target_graph.add((s, DCT.title, longest))

        # adms:Asset/dct:type
        for s, p, o in source_graph.triples((None, DCT.type, None)):
            assetType = ""
            if str(o) == "https://data.vlaanderen.be/id/concept/StandaardType/Applicatieprofiel":
               assetType = "http://www.w3.org/ns/dx/prof/Profile"
            elif str(o) == "https://data.vlaanderen.be/id/concept/StandaardType/Vocabularium":
               assetType = "http://purl.org/vocommons/voaf#Vocabulary"
            else:
                logger.error("assetType is empty")
            
            target_graph.add((s, DCT.type, URIRef(assetType)))
            target_graph.add((URIRef(assetType), RDF.type, SKOS.Concept))

        # adms:Asset/adms:status
        for s, p, o in source_graph.triples((None, ADMS.status, None)):
            mappedStatus = ""
            if str(o) == "https://data.vlaanderen.be/id/concept/StandaardStatus/HerroepenStandaard":
                mappedStatus = "http://purl.org/adms/status/Withdrawn"
            elif str(o) == "https://data.vlaanderen.be/id/concept/StandaardStatus/ErkendeStandaard":
                mappedStatus = "http://purl.org/adms/status/Completed"
            elif str(o) == "https://data.vlaanderen.be/id/concept/StandaardStatus/VerouderdeStandaard":
                mappedStatus = "http://purl.org/adms/status/Deprecated"
            elif str(o) == "https://data.vlaanderen.be/id/concept/StandaardStatus/KandidaatStandaard":
                mappedStatus = "http://purl.org/adms/status/UnderDevelopment"
            if len(mappedStatus) > 0:              
                target_graph.add((s, ADMS.status, URIRef(mappedStatus)))
                target_graph.add((URIRef(mappedStatus), RDF.type, SKOS.Concept))

        # adms:Asset/foaf:homepage/foaf:Document/
        for s, p, o in source_graph.triples((None, FOAF.homepage, None)):
            target_graph.add((s, FOAF.homepage, o))
            target_graph.add((o, RDF.type, FOAF.Document))


        # adms:Asset/dct:creator/foaf:Agent 
        # adms:Asset/dct:creator/foaf:Agent/foaf:name
        # adms:Asset/dct:creator/foaf:Agent/dct:spatial
        for s, p, o in source_graph.triples((None, DCT.creator, None)):
            target_graph.add((s, DCT.creator, o))
            target_graph.add((o, RDF.type, FOAF.Agent))

            spatial_code = "http://publications.europa.eu/resource/authority/country/BEL"
            target_graph.add((o, DCT.spatial, URIRef(spatial_code)))
            target_graph.add((URIRef(spatial_code), RDF.type, DCT.Location))

            url = o
            if str(o).startswith("http://"):
                logger.warning(f"url starting with http:// - {o}")
                url = str(o).replace("http://","https://")
                logger.info(f"transformed url to: {url}")


            headers = {
                "Accept" : "text/turtle"
            }
            response = requests.get(url,headers=headers)

            org_graph = Graph()
            org_graph.parse(data=response.text, format="turtle")
        
            if response.status_code == 200:
                logger.info("Request Succesfull for foaf:Agent")
                for a, b, c in org_graph.triples((URIRef(url), SKOS.prefLabel, None)):
                    target_graph.add((o, FOAF.name, Literal(c, datatype=RDF.langString)))
                
                for a, b, c in org_graph.triples((URIRef(url), ORG.classification, None)):
                    agentType = ""
                    if str(c) == "https://data.vlaanderen.be/doc/concept/organisatieclassificatie/de8494e0-f1a9-4a9f-9df2-60f958826821":
                        agentType = "http://publications.europa.eu/resource/authority/organization-type/COMPANY"
                    if str(c) == "https://data.vlaanderen.be/id/concept/organisatieclassificatie/7847213d-dc31-29d0-5877-45a6b81100cc":
                        agentType = "http://publications.europa.eu/resource/authority/organization-type/GOV"
                    if len(agentType) > 0:
                        logger.info(f"agentType found: {agentType}")

                        target_graph.add((o, DCT.type, URIRef(agentType)))
                        target_graph.add((URIRef(agentType), RDF.type, SKOS.Concept))
            else:
                logger.error("Request FAILED for foaf:Agent")

        
        # adms:Asset/dcat:contactPoint/vcard:Kind
        # adms:Asset/dcat:contactPoint/vcard:Kind/vcard:hasEmail
        for s, p, o in source_graph.triples((None, M8G.contactPoint, None)):
            target_graph.add((s, DCAT.contactPoint, o))
            target_graph.add((o, RDF.type, VCARD.Kind))
        
            url = o
            if str(o).startswith("http://"):
                logger.warning(f"url starting with http:// - {o}")
                url = str(o).replace("http://","https://")
                logger.info(f"transformed url to: {url}")

            headers = {
                "Accept" : "text/turtle"
            }
            response = requests.get(url,headers=headers)

            if response.status_code == 200:
                logger.info("Request Successful for vcard:Kind")
                
                contactPoint_graph = Graph()
                contactPoint_graph.parse(data=response.text, format="turtle")
                
                for a, b, c in contactPoint_graph.triples((None, SCHEMA.email, None)):
                    if (a, RDF.type, SCHEMA.ContactPoint) in contactPoint_graph:
                        logger.info(f"Found email: {c} for contact point: {a}")
                        emailURI =  "mailto:" + c
                        target_graph.add((o, VCARD.hasEmail, URIRef(emailURI)))
                        target_graph.add((URIRef(emailURI), RDF.type, VCARD.Email,))

            else:
                logger.error(f"Request FAILED for vcard:Kind - Status: {response.status_code}")


        target_data = target_graph.serialize(format="turtle")

        logger.info(f"Transformed target Data: {target_data}")
        return target_data
        
    except Exception as e:
        logger.error(f"Transofrmation FAILED for batch: {batch}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise