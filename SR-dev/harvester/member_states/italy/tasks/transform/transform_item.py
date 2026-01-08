from prefect import task, get_run_logger

from rdflib import Graph, RDF, Namespace, Literal, URIRef
from rdflib.namespace import XSD
from pathlib import Path
from rdflib import Literal, XSD
from datetime import datetime, timezone
import requests
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import load_config

@task(
    name="transform item", 
    retries=3, 
    retry_delay_seconds=60,
    timeout_seconds=300
)
async def transform_item(batch: str) -> str:
    """
    Transforming each entry to conform to the latest model of SRM

    :param batch: A batch of identifiers or input items to process.
    :return: RDF string representing transformed data
    """
    
    logger = get_run_logger()
    logger.info(f"Transforming batch: {batch}")  
    config = load_config()
 
    try:
        source_graph = Graph()
        source_graph.parse(data=batch, format="turtle")

        target_graph = Graph()
        ADMS   = Namespace(config["transformation"]["namespaces"]["adms"])
        ADMSAPIT   = Namespace(config["transformation"]["namespaces"]["admsapit"])
        DCT    = Namespace(config["transformation"]["namespaces"]["dct"])
        DCAT   = Namespace(config["transformation"]["namespaces"]["dcat"])
        VANN   = Namespace(config["transformation"]["namespaces"]["vann"])
        FOAF   = Namespace(config["transformation"]["namespaces"]["foaf"])
        SKOS   = Namespace(config["transformation"]["namespaces"]["skos"])
        SCHEMA = Namespace(config["transformation"]["namespaces"]["schema"])
        VCARD  = Namespace(config["transformation"]["namespaces"]["vcard"])
        M8G    = Namespace(config["transformation"]["namespaces"]["m8g"])
        ORG    = Namespace(config["transformation"]["namespaces"]["org"])
        PROF   = Namespace(config["transformation"]["namespaces"]["prof"])
        OWL    = Namespace(config["transformation"]["namespaces"]["owl"])
        RDFS   = Namespace(config["transformation"]["namespaces"]["rdfs"])

        target_graph.bind("adms", ADMS)
        target_graph.bind("admsapit", ADMSAPIT)
        target_graph.bind("dct", DCT)
        target_graph.bind("vann", VANN)
        target_graph.bind("foaf", FOAF)
        target_graph.bind("skos", SKOS)
        target_graph.bind("schema", SCHEMA)
        target_graph.bind("vcard", VCARD)
        target_graph.bind("m8g", M8G)
        target_graph.bind("dcat", DCAT)
        target_graph.bind("org", ORG)
        target_graph.bind("prof", PROF)
        target_graph.bind("owl", OWL)
        target_graph.bind("rdfs", RDFS)

        # adms:Asset
        # adms:Asset/dct:identifier
        for s, p, o in source_graph.triples((None, RDF.type, OWL.Ontology)):
            target_graph.add((s, RDF.type, ADMS.Asset))

            official_uri = source_graph.value(s, ADMSAPIT.officialURI)
            
            if official_uri:
                target_graph.add((s, DCT.identifier,Literal(str(official_uri))))
            else:
                target_graph.add((s, DCT.identifier, Literal(str(s))))
                logger.info(f"No officialURI for {s}, using ontology URI as identifier")

        # adms:Asset/dct:description
        for s, p, o in source_graph.triples((None, DCT.description, None)):
            target_graph.add((s, DCT.description, o))


        # adms:Asset/dct:issued
        for s, p, o in source_graph.triples((None, DCT.issued, None)):
            try:
                value = str(o)

                if "T" in value:
                    dateTime = value.replace("+00:00", "Z")

                    if not dateTime.endswith("Z"):
                        dateTime = dateTime + "Z"

                elif len(value) == 10:
                    dateTime = value + "T00:00:00Z"

                else:
                    logger.info(f"dct:issued - unsupported format: {o}")
                    continue

                target_graph.add((s,DCT.issued,Literal(dateTime, datatype=XSD.dateTime)))

            except Exception as e:
                logger.info(f"dct:issued - could not convert date: {o} (error: {e})")
                continue
                

        # adms:Asset/dct:language
        for s, p, o in source_graph.triples((None, DCT.language, None)):
            target_graph.add((s, DCT.language, o))
            target_graph.add((o, RDF.type, SKOS.Concept))

        # # adms:Asset/dct:modified
        # modified_by_subject = {}

        # for s, p, o in source_graph.triples((None, DCT.modified, None)):
        #     if str(o) == "N.v.t.":
        #         logger.info(f"dct:modified - skipping N.v.t. for subject {s}")
        #         continue
        #     try:
        #         date_value = o.toPython()
        #         modified_by_subject.setdefault(s, []).append(date_value)
        #     except Exception as e:
        #         logger.info(f"dct:modified - could not convert date: {o} (error: {e})")
        #         continue

        # for s, dates in modified_by_subject.items():
        #     date_count = len(dates)

        #     if date_count == 1:
        #         dateTime = str(dates[0]) + "T00:00:00"
        #         target_graph.add((s, DCT.modified, Literal(dateTime, datatype=XSD.dateTime)))
        #     elif date_count > 1:
        #         latest_date = max(dates)
        #         dateTime = str(latest_date) + "T00:00:00"

        #         logger.info(f"dct:modified - subject {s} has {date_count} dates, keeping latest: {dateTime}")
        #         target_graph.add((s, DCT.modified, Literal(dateTime, datatype=XSD.dateTime)))

        # # adms:Asset/vann:preferredNamespaceUri
        # for s, p, o in source_graph.triples((None, VANN.preferredNamespaceUri, None)):
        #     target_graph.add((s, VANN.preferredNamespaceUri, Literal(o, datatype=XSD.anyURI) ))

        # # adms:Asset/dct:title
        # titles_by_subject = {}
        # for s, p, o in source_graph.triples((None, DCT.title, None)):
        #     titles_by_subject.setdefault(s, []).append(o)

        # for s, titles in titles_by_subject.items():
        #     title_count = len(titles)
            
        #     if title_count == 1:
        #         target_graph.add((s, DCT.title, titles[0]))
        #     elif title_count > 1:
        #         longest = max(titles, key=lambda t: len(str(t)))
        #         logger.info(
        #             f"dct:title - more than 2 titles, keeping longest: '{longest}' "
        #             f"({len(str(longest))} chars)"
        #         )
        #         target_graph.add((s, DCT.title, longest))

        # # adms:Asset/dct:type
        # for s, p, o in source_graph.triples((None, DCT.type, None)):
        #     assetType = ""
        #     if str(o) == "https://data.vlaanderen.be/id/concept/StandaardType/Applicatieprofiel":
        #        assetType = "http://www.w3.org/ns/dx/prof/Profile"
        #     elif str(o) == "https://data.vlaanderen.be/id/concept/StandaardType/Vocabularium":
        #        assetType = "http://purl.org/vocommons/voaf#Vocabulary"
        #     if len(assetType) > 0:
        #         target_graph.add((s, DCT.type, URIRef(assetType)))
        #         target_graph.add((URIRef(assetType), RDF.type, SKOS.Concept))
        #     else:
        #         logger.error("assetType is empty")
                
        # # adms:Asset/adms:status
        # for s, p, o in source_graph.triples((None, ADMS.status, None)):
        #     mappedStatus = ""
        #     if str(o) == "https://data.vlaanderen.be/id/concept/StandaardStatus/HerroepenStandaard":
        #         mappedStatus = "http://purl.org/adms/status/Withdrawn"
        #     elif str(o) == "https://data.vlaanderen.be/id/concept/StandaardStatus/ErkendeStandaard":
        #         mappedStatus = "http://purl.org/adms/status/Completed"
        #     elif str(o) == "https://data.vlaanderen.be/id/concept/StandaardStatus/VerouderdeStandaard":
        #         mappedStatus = "http://purl.org/adms/status/Deprecated"
        #     elif str(o) == "https://data.vlaanderen.be/id/concept/StandaardStatus/KandidaatStandaard":
        #         mappedStatus = "http://purl.org/adms/status/UnderDevelopment"
        #     if len(mappedStatus) > 0:              
        #         target_graph.add((s, ADMS.status, URIRef(mappedStatus)))
        #         target_graph.add((URIRef(mappedStatus), RDF.type, SKOS.Concept))

        # # adms:Asset/foaf:homepage/foaf:Document/
        # for s, p, o in source_graph.triples((None, FOAF.homepage, None)):
        #     target_graph.add((s, FOAF.homepage, o))
        #     target_graph.add((o, RDF.type, FOAF.Document))

        # # adms:Asset/dct:creator/foaf:Agent 
        # # adms:Asset/dct:creator/foaf:Agent/foaf:name
        # # adms:Asset/dct:creator/foaf:Agent/dct:spatial
        # for s, p, o in source_graph.triples((None, DCT.creator, None)):
        #     url = o
        #     if str(o).startswith("http://"):
        #         url = str(o).replace("http://","https://")
        #         logger.info(f"foaf:Agent: replaced url containing 'http://' to 'https://': {o} -> {url}")
        #     if url.startswith("https://data.vlaanderen.be/doc/organisatie"):
        #         url = url.replace("https://data.vlaanderen.be/doc/organisatie","https://data.vlaanderen.be/id/organisatie")
        #         logger.info(f"foaf:Agent: replaced url containing 'doc' to 'id': {o} -> {url}")
        
        #     target_graph.add((s, DCT.creator, URIRef(url)))
        #     target_graph.add((URIRef(url), RDF.type, FOAF.Agent))

        #     spatial_code = "http://publications.europa.eu/resource/authority/country/BEL"
        #     target_graph.add((URIRef(url), DCT.spatial, URIRef(spatial_code)))
        #     target_graph.add((URIRef(spatial_code), RDF.type, DCT.Location))

        #     headers = {
        #             "Accept" : "text/turtle"
        #         }
        #     response = requests.get(url,headers=headers)

        #     org_graph = Graph()
        #     org_graph.parse(data=response.text, format="turtle")

        #     if response.status_code == 200:
        #         logger.info("Request Succesfull for foaf:Agent")
        #         for a, b, c in org_graph.triples((URIRef(url), SKOS.prefLabel, None)):              
        #             target_graph.add((URIRef(url), FOAF.name, Literal(str(c), lang="nl")))
                                      
        #         for a, b, c in org_graph.triples((URIRef(url), ORG.classification, None)):
        #             agentType = ""
        #             if str(c) == "https://data.vlaanderen.be/doc/concept/organisatieclassificatie/de8494e0-f1a9-4a9f-9df2-60f958826821":
        #                 agentType = "http://publications.europa.eu/resource/authority/organization-type/COMPANY"
        #             if str(c) == "https://data.vlaanderen.be/id/concept/organisatieclassificatie/7847213d-dc31-29d0-5877-45a6b81100cc":
        #                 agentType = "http://publications.europa.eu/resource/authority/organization-type/GOV"
        #             if len(agentType) > 0:
        #                 logger.info(f"agentType found: {agentType}")

        #                 target_graph.add((URIRef(url), DCT.type, URIRef(agentType)))
        #                 target_graph.add((URIRef(agentType), RDF.type, SKOS.Concept))
        #     else:
        #         logger.error("Request FAILED for foaf:Agent")
        
        # # adms:Asset/dcat:contactPoint/vcard:Kind
        # # adms:Asset/dcat:contactPoint/vcard:Kind/vcard:hasEmail
        # for s, p, o in source_graph.triples((None, M8G.contactPoint, None)):
        #     url = o
        #     if str(o).startswith("http://"):
        #         url = str(o).replace("http://","https://")
        #         logger.info(f"foaf:Agent: replaced url containing 'http://' to 'https://': {o} -> {url}")
        #     if url.startswith("https://data.vlaanderen.be/doc/organisatie"):
        #         url = url.replace("https://data.vlaanderen.be/doc/organisatie","https://data.vlaanderen.be/id/organisatie")
        #         logger.info(f"foaf:Agent: replaced url containing 'doc' to 'id': {o} -> {url}")
        #     target_graph.add((s, DCAT.contactPoint, URIRef(url)))
        #     target_graph.add((URIRef(url), RDF.type, VCARD.Kind))

        #     headers = {
        #         "Accept" : "text/turtle"
        #     }
        #     response = requests.get(url,headers=headers)

        #     if response.status_code == 200:
        #         logger.info("Request Successful for vcard:Kind")
                
        #         contactPoint_graph = Graph()
        #         contactPoint_graph.parse(data=response.text, format="turtle")
                
        #         for a, b, c in contactPoint_graph.triples((None, SCHEMA.email, None)):
        #             if (a, RDF.type, SCHEMA.ContactPoint) in contactPoint_graph:
        #                 logger.info(f"Found email: {c} for contact point: {a}")
        #                 emailURI =  "mailto:" + c
        #                 target_graph.add((URIRef(url), VCARD.hasEmail, URIRef(emailURI)))
        #                 target_graph.add((URIRef(emailURI), RDF.type, VCARD.Email,))

        #     else:
        #         logger.error(f"Request FAILED for vcard:Kind - Status: {response.status_code}")

        # # adms:Asset/dcat:distribution/adms:AssetDistribution
        # # adms:Asset/dcat:distribution/adms:AssetDistribution/dct:format
        # # adms:Asset/dcat:distribution/adms:AssetDistribution/dct:title
        # # adms:Asset/dcat:distribution/adms:AssetDistribution/prof:hasRole
        # # adms:AssetDistribution/rdfs:isDefinedBy/rdfs:Class
        # # adms:AssetDistribution/rdfs:isDefinedBy/rdfs:Class/rdfs:label
        # for s, p, o in source_graph.triples((None, DCAT.distribution, None)):
        #     target_graph.add((s, DCAT.distribution, o))
        #     target_graph.add((o, RDF.type, ADMS.AssetDistribution))

        #     for a, b, c in source_graph.triples((o, DCT.title, None)):
        #         target_graph.add((o, DCT.title, Literal(c, datatype=RDF.langString)))
            
        #     for a, b, c in source_graph.triples((o, DCAT.downloadURL, None)):
        #         target_graph.add((o, DCAT.downloadURL, Literal(c, datatype=XSD.anyURI)))
                    
        #     fileType = ""
        #     hasRole = ""
        #     downloadURL = ""
            
        #     for a, b, c in source_graph.triples((o, DCAT.mediaType, None)):
        #         if str(c) == "http://www.iana.org/assignments/media-types/text/html":
        #             fileType = "http://publications.europa.eu/resource/authority/file-type/HTML"
        #             hasRole = "http://www.w3.org/ns/dx/prof/role/specification"
        #         elif str(c) == "http://www.iana.org/assignments/media-types/text/turtle":
        #             fileType = "http://publications.europa.eu/resource/authority/file-type/RDF_TURTLE"
        #             hasRole = "http://www.w3.org/ns/dx/prof/role/vocabulary"
                    
        #         if len(fileType) > 0:
        #             target_graph.add((o, DCT['format'], URIRef(fileType)))
        #             target_graph.add((URIRef(fileType), RDF.type, SKOS.Concept))

        #             target_graph.add((o, PROF.hasRole, URIRef(hasRole)))
        #             target_graph.add((URIRef(hasRole), RDF.type, SKOS.Concept))
            
        #     for a, b, c in source_graph.triples((o, DCAT.downloadURL, None)):
        #         downloadURL = str(c)
                
        #     if fileType == "http://publications.europa.eu/resource/authority/file-type/RDF_TURTLE" and downloadURL:
        #         headers = {
        #             "Accept": "text/turtle"
        #         }
                
        #         try:
        #             response = requests.get(downloadURL, headers=headers)

        #             if response.status_code == 200:
        #                 content_type = response.headers.get('Content-Type', '').lower()

        #                 if 'turtle' not in content_type:
        #                     logger.warning(f"Expected Turtle but received {content_type} from {downloadURL}, skipping")
        #                 else:
        #                     logger.info(f"Request successful for downloadURL: {downloadURL}")

        #                     class_graph = Graph()
        #                     class_graph.parse(data=response.text, format="turtle")

        #                     uri_ontology = ""
        #                     for e, d, f in class_graph.triples((None, RDF.type, OWL.Ontology)):
        #                         logger.info(f"Found OWL Ontology: {e}")
        #                         uri_ontology = str(e)


        #                     for x, y, z in class_graph.triples((None, RDF.type, OWL.Class)):
        #                         logger.info(f"Found OWL Class: {x}")

        #                         isDefinedBy = list(class_graph.triples((x, RDFS.isDefinedBy, None)))

        #                         if isDefinedBy:
        #                             for j, k, l in isDefinedBy:
        #                                 logger.info(f"Found rdfs:isDefinedBy for {x}: {o}")
        #                                 logger.info(f"isDefinedBy : {j} - {k} - {o}")

        #                                 if str(l) == uri_ontology:
        #                                     logger.info(f"uri of owl:Ontology = object of isDefinedBy {uri_ontology} = {str(l)}")

        #                                     target_graph.add((x, RDFS.isDefinedBy, o))
        #                                     target_graph.add((x, RDF.type, RDFS.Class))

        #                                     labels = list(class_graph.triples((x, RDFS.label, None)))
                                            
        #                                     if labels:
        #                                         for _, _, label in labels:
        #                                             logger.info(f"Found rdfs:label : {label}")
        #                                             if str(j) == str(x):
        #                                                 logger.info(f"AssetDistribution matches isDefinedBy: {x} = {j}")
        #                                                 target_graph.add((x, RDFS.label, label))
        #                                             else:
        #                                                 logger.error(f"AssetDistribution does not match isDefinedBy: {x} = {j}")
        #                                     else:
        #                                         uri_str = str(x)
        #                                         if '#' in uri_str:
        #                                             label = uri_str.split('#')[-1]
                                                
        #                                             logger.info(f"No rdfs:label found for {x}, using generated label: {label}")
        #                                             target_graph.add((x, RDFS.label, Literal(label, lang="en")))
        #             else:
        #                 logger.warning(f"Request failed for {downloadURL}, status: {response.status_code}")
        #         except Exception as e:
        #             logger.error(f"Error processing {downloadURL}: {e}")


        target_data = target_graph.serialize(format="turtle")

        logger.info(f"Transformed target Data: {target_data}")
        return target_data
        
    except Exception as e:
        logger.error(f"Transofrmation FAILED for batch: {batch}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise

