from prefect import task, get_run_logger

from prefect.flows import R
from rdflib import BNode, Graph, RDF, Namespace, Literal, URIRef
from rdflib.namespace import XSD, split_uri
from pathlib import Path
from rdflib import Literal, XSD
from datetime import datetime, timezone
from .construct_item import query_subject
import requests
import sys
import json


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from config import load_config

@task(
    name="transform item", 
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
        ROV   = Namespace(config["transformation"]["namespaces"]["rov"])
        MODELLDCATNO = Namespace(config["transformation"]["namespaces"]["modelldcatno"])

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
        target_graph.bind("rov", ROV)
        target_graph.bind("modelldcatno", MODELLDCATNO)

        BASE_DIR = Path(__file__).resolve().parent
        MAPPING_THEME_FILE = BASE_DIR / "asset_theme_mapping.json"
        MAPPING_ORG_TYPE_FILE = BASE_DIR / "org_type_mapping.json"


        with open(MAPPING_THEME_FILE, "r", encoding="utf-8") as f:
            theme_mapping = json.load(f)

        with open(MAPPING_ORG_TYPE_FILE, "r", encoding="utf-8") as f:
            org_type_mapping = json.load(f)

        # adms:Asset
        for s, p, o in source_graph.triples((None, RDF.type, MODELLDCATNO.InformationModel)):
            logger.info(f"modelcattno:InformationModel: {s} - TRANSFORMATION STARTED...")
            target_graph.add((s, RDF.type, ADMS.Asset))

            for _, p2, o2 in source_graph.triples((s, None, None)):
 
                # adms:Asset/dct:description
                if p2 == DCT.description:
                    logger.info(f"dct:description: {o2}")
                    target_graph.add((s, DCT.description, o2))

                # adms:Asset/dct:identifier
                if p2 == DCT.identifier:
                    logger.info(f"dct:identifier: {o2}")
                    target_graph.add((s, DCT.identifier, Literal(str(o2))))

                # adms:Asset/dct:issued
                # adms:Asset/dct:modified
                if p2 == DCT.issued or p2 == DCT.modified:
                    if p2 == DCT.issued:
                        logger.info(f"dct:issued: {o2}")
                    elif p2 == DCT.modified:
                        logger.info(f"dct:modified: {o2}")

                    date_str = str(o2)
                    
                    try:                        
                        parsed_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        logger.info(f"Parsed as ISO datetime: {parsed_date}")
                    except ValueError as e:
                        try:
                            parsed_date = datetime.strptime(date_str, '%Y/%m/%d')
                            logger.info(f"Parsed as date (YYYY/MM/DD): {parsed_date}")
                        except ValueError as e:
                            logger.error(f"Failed to parse date in any format: {date_str} (error: {e})")
                            continue
                    
                    target_graph.add((s, p2, Literal(parsed_date, datatype=XSD.dateTime)))

                # adms:Asset/dcat:keyword
                if p2 == DCAT.keyword:
                    logger.info(f"dcat:keyword: {o2}")
                    target_graph.add((s, DCAT.keyword, o2))

                # adms:Asset/dct:language
                if p2 == DCT.language:
                    logger.info(f"dct:language: {o2}")
                    target_graph.add((s, DCT.language, URIRef(str(o2))))
                    target_graph.add((URIRef(str(o2)), RDF.type, SKOS.Concept))
                
                # adms:Asset/dct:language
                if p2 == DCT.license:
                    logger.info(f"dct:license: {o2}")
                    target_graph.add((s, DCT.license, URIRef(o2)))
                    target_graph.add((URIRef(o2), RDF.type, DCT.LicenseDocument))

                # adms:Asset/dct:title
                if p2 == DCT.title:     
                    logger.info(f"dct:title: {o2}")                          
                    target_graph.add((s, DCT.title, Literal(o2, datatype=RDF.langString)))

                # adms:Asset/owl:versionInfo
                if p2 == OWL.versionInfo:     
                    logger.info(f"owl:versionInfo: {o2}")                          
                    target_graph.add((s, OWL.versionInfo, Literal(str(o2), datatype=XSD.string))) 

                # adms:Asset/adms:status
                if p2 == ADMS.status:    
                    logger.info(f"adms:status: {o2}") 
                    target_graph.add((s, ADMS.status, URIRef(o2)))
                    target_graph.add((URIRef(o2), RDF.type, SKOS.Concept))  

                # adms:Asset/adms:status
                if p2 == DCAT.theme:    
                    logger.info(f"dcat:theme: {o2}") 

                    try:
                        mapped_theme = theme_mapping[str(o2)]
                        logger.info(f"dcat:theme: {o2} mapped to {mapped_theme}") 

                        target_graph.add((s, DCAT.theme, URIRef(mapped_theme)))
                        target_graph.add((URIRef(mapped_theme), RDF.type, SKOS.Concept))
                    except KeyError:
                        logger.error(f"No theme mapping found for dcat:theme {o2}")

                # adms:Asset/dct:creator
                # adms:Asset/dct:publisher
                # adms:Asset/dct:creator/foaf:Agent/foaf:name
                # adms:Asset/dct:creator/foaf:Agent/dct:spatial
                if p2 == DCT.publisher:    
                    logger.info(f"dct:publisher: {o2}") 
                    target_graph.add((s, DCT.publisher, URIRef(o2)))
                    target_graph.add((URIRef(o2), RDF.type, FOAF.Agent)) 

                    logger.warning(f"dct:publisher will be also used as dct:creator") 
                    target_graph.add((s, DCT.creator, URIRef(o2)))
                    target_graph.add((URIRef(o2), RDF.type, FOAF.Agent))

                    spatial_code = "http://publications.europa.eu/resource/authority/country/NOR"
                    target_graph.add((URIRef(o2), DCT.spatial, URIRef(spatial_code)))
                    target_graph.add((URIRef(spatial_code), RDF.type, DCT.Location))

                    try:
                        headers = {
                        "Accept" : "text/turtle",
                        "User-Agent": "SEMIC"
                        }
                        response = requests.get(str(o2),headers=headers)

                        agent_graph = Graph()
                        
                        if response.status_code == 200:
                            logger.info("Request Succesfull for foaf:Agent")
                            agent_graph.parse(data=response.text, format="turtle")

                            for _, _, name in agent_graph.triples((None, FOAF.name, None)):
                                target_graph.add((URIRef(o2), FOAF.name, Literal(name, datatype=RDF.langString)))

                        else:
                            logger.error("Failed request for foaf:Agent {o2}")
                            logger.error(f"URL:            {response.url}")
                            logger.error(f"Status:         {response.status_code}")
                            logger.error(f"Request headers: {response.request.headers}")
                            logger.error(f"Response headers: {dict(response.headers)}")
                            logger.error(f"Response body (first 500 chars): {response.text[:500]}")
                    
                    except Exception as e:
                        logger.error(f"Failed requist for foaf:Agent - {str(e)}")
                        

                    for _, _, orgType in agent_graph.triples((None, ROV.orgType, None)):

                        try:
                            mapped_org_type = org_type_mapping[str(orgType)]
                            logger.info(f"dct:type: {orgType} mapped to {mapped_org_type}") 

                            target_graph.add((o2, DCT.type, URIRef(mapped_org_type)))
                            target_graph.add((URIRef(mapped_org_type), RDF.type, SKOS.Concept))
                        except KeyError:
                            logger.error(f"No organisation_type mapping found for dcat:theme {o2}")
                        

                # adms:Asset/dcat:contactPoint
                if p2 == DCAT.contactPoint:    
                    logger.info(f"dcat:contactPoint: {o2}") 

                    try:
                        result = await query_subject(
                            str(o2), 
                            config["web_source_url"],
                            config["construct_custom_query"],
                            str(VCARD.hasEmail),
                        )

                        if result:
                            logger.info(f"Successfully reached endpoint for dct:contactPoint {o2}")

                            target_graph.add((s, DCAT.contactPoint, URIRef(o2)))
                            target_graph.add((URIRef(o2), RDF.type, VCARD.Kind))

                            vcard_graph = Graph()
                            vcard_graph.parse(data=result, format="turtle")

                            for _, _, hasEmail in vcard_graph.triples((None, VCARD.hasEmail, None)):
                                logger.info(f"Found email: {hasEmail} for contact point: {o2}")       
                                target_graph.add((URIRef(o2), VCARD.hasEmail, URIRef(hasEmail)))
                                target_graph.add((URIRef(hasEmail), RDF.type, VCARD.Email))

                            
                            logger.info(f"Successfully transformed contact point: {o2}")
                        else:
                            logger.warning(f"No result returned for contact point: {o2}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process contact point {o2}: {e}")

                # adms:Asset/foaf:homepage
                # adms:Asset/foaf:homepage/foaf:Document
                if p2 == FOAF.homepage:
                    logger.info(f"foaf:homepage: {o2}")
                    target_graph.add((s, FOAF.homepage, o2))
                    target_graph.add((o2, RDF.type, FOAF.Document))

        # adms:Asset/dcat:distribution/adms:AssetDistribution
        # adms:Asset/dcat:distribution/adms:AssetDistribution/dcat:downloadURL
        # adms:Asset/dcat:distribution/adms:AssetDistribution/dct:format
        # adms:Asset/dcat:distribution/adms:AssetDistribution/dct:title
        # adms:Asset/dcat:distribution/adms:AssetDistribution/rdfs:isDefinedBy/rdfs:Class
        # adms:Asset/dcat:distribution/adms:AssetDistribution/rdfs:isDefinedBy/rdfs:Class/rdfs:label
        # adms:Asset/vann:preferredNamespaceUri
        for s, p, o in target_graph.triples((None, RDF.type, ADMS.Asset)):

            has_homepage = any(
                target_graph.triples((s, FOAF.homepage, None))
            )

            has_distribution = any(
                target_graph.triples((s, DCAT.distribution, None))
            )
        
            # ! ONLY FOR Assets PersonOgEnhet & AdresseModel -> here we use homepage to derive the properties mentioned above
            if has_homepage and not has_distribution:
                logger.info(f"INSIDE TARGET_GRAPH: {s} has foaf:homepage but no dcat:distribution")
                logger.warning(f"foaf:homepage will be used to derive dct:distribution and adms:AssetDistribution")

                for _, p2, o2 in source_graph.triples((s, None, None)):
 
                    if p2 == FOAF.homepage:
                        logger.info(f"dct:homepage: {o2}")

                        distributionURI = BNode()

                        target_graph.add((s, DCAT.distribution, distributionURI))
                        target_graph.add((distributionURI, RDF.type, ADMS.AssetDistribution))

                        #Todo extract form homepage URL
                        target_graph.add((distributionURI, DCT.title, Literal(o2, datatype=RDF.langString)))

                        target_graph.add((distributionURI, DCAT.downloadURL, Literal(o2, datatype=XSD.anyURI)))

                        fileType = "http://publications.europa.eu/resource/authority/file-type/HTML"
                        hasRole = "http://www.w3.org/ns/dx/prof/role/specification"

                        target_graph.add((distributionURI, DCT['format'], URIRef(fileType)))
                        target_graph.add((URIRef(fileType), RDF.type, DCT.MediaTypeOrExtent))

                        target_graph.add((distributionURI, PROF.hasRole, URIRef(hasRole)))
                        target_graph.add((URIRef(hasRole), RDF.type, SKOS.Concept))

                        try:
                            result = await query_subject(
                                str(s), 
                                config["web_source_url"],
                                config["construct_classes_belonging_to_model"],
                            )

                            if result:
                                logger.info(f"Successfully reached endpoint for modelldcatno:InformationModel: {s}")

                                class_graph = Graph()
                                class_graph.parse(data=result, format="turtle")

                                preferredNamespaceUri = ""
                                previous_namespace = None

                                for classURI, _, title in class_graph.triples((None, DCT.title, None)):
                                    logger.info(f"Found Class: {classURI} with title: {title}")       
                                    target_graph.add((URIRef(classURI), RDFS.isDefinedBy, distributionURI))
                                    target_graph.add((URIRef(classURI), RDF.type, RDFS.Class))

                                    target_graph.add((URIRef(classURI), RDFS.label, Literal(title, datatype=RDF.langString)))
                                    
                                    base, local = split_uri(classURI)
                                    if previous_namespace is not None and base != previous_namespace:
                                        logger.warning(f"preferredNamespaceUri changed from '{previous_namespace}' to '{base}' - last value will be used")
                                    
                                    preferredNamespaceUri = base
                                    previous_namespace = base
                                    logger.info(f"vann:preferredNamespaceUri: base URI derived from rdfs:Class namespace {base}")                 
                                
                                target_graph.add((s, VANN.preferredNamespaceUri, Literal(preferredNamespaceUri, datatype=XSD.anyURI) ))

                                logger.info(f"Successfully transformed rdfs:Class for modelldcatno:InformationModel: {s}")
                            else:
                                logger.warning(f"No rdfs:Class result returned for modelldcatno:InformationModel: {s}")
                        
                        except Exception as e:
                            logger.error(f"Failed to reach endpoint for modelldcatno:InformationModel: {s}") 

            # ! ONLY FOR other 11 Assets except from PersonOgEnhet & AdresseModel -> for these other assets we will use dct:hasFormat -> rdfs:seeAlso
            if not has_homepage and not has_distribution:
                logger.info(f"INSIDE TARGET_GRAPH: {s} does not contain foaf:homepage and no no dcat:distribution")

                logger.warning(f"No Classes for {s}, using ontology URI as preferredNamespace")
                target_graph.add((s,VANN.preferredNamespaceUri, Literal(s, datatype=XSD.anyURI)))

                for _, p2, o2 in source_graph.triples((s, None, None)):
 
                    if p2 == DCT.hasFormat:
                        logger.info(f"dct:hasFormat: {o2}")

                        try:
                            result = await query_subject(
                                str(s), 
                                config["web_source_url"],
                                config["construct_dcat_distribution"],
                            )

                            if result:
                                logger.info(f"Successfully reached endpoint for modelldcatno:InformationModel: {s}")
                                

                                format_graph = Graph()
                                format_graph.parse(data=result, format="turtle")

                                for hasFormat, _, seeAlso in format_graph.triples((None, RDFS.seeAlso, None)):
                                    logger.info(
                                        f"Found rdfs:seeAlso: {seeAlso} "
                                        f"for dct:hasFormat: {hasFormat}"
                                    )

                                    try:
                                        seeAlso_str = str(seeAlso)

                                        if "#" in seeAlso_str:
                                            distributionURI, distribution_title = seeAlso_str.split("#")
                                            logger.info(f"Split on '#': distributionURI={distributionURI}, distribution_title={distribution_title}")
                                        else:
                                            parts = seeAlso_str.split("/")
                                            spec_index = parts.index("specification")
                                            distributionURI = "/".join(parts[:spec_index + 2])
                                            distribution_title = parts[spec_index + 1]
                                            logger.info(
                                                f"No '#' found, truncated to specification base: "
                                                f"distributionURI={distributionURI}, distribution_title={distribution_title}"
                                            )
                                    except (ValueError, IndexError) as e:
                                        logger.error(
                                            f"Failed to parse seeAlso URL: {seeAlso_str} — {e}, "
                                            f"skipping distribution for {s}"
                                        )
                                        continue 

                                    target_graph.add((s, RDFS.isDefinedBy, URIRef(distributionURI)))
                                    target_graph.add((URIRef(distributionURI), RDF.type, ADMS.AssetDistribution))

                                    target_graph.add((URIRef(distributionURI), DCT.title, Literal(distribution_title, lang="nb")))
                                    #TODO check donwload URI
                                    target_graph.add((URIRef(distributionURI), DCAT.downloadURL, Literal(distributionURI, datatype=XSD.anyURI)))

                                    fileType = "http://publications.europa.eu/resource/authority/file-type/HTML"
                                    hasRole = "http://www.w3.org/ns/dx/prof/role/specification"

                                    target_graph.add((URIRef(distributionURI), DCT['format'], URIRef(fileType)))
                                    target_graph.add((URIRef(fileType), RDF.type, DCT.MediaTypeOrExtent))

                                    target_graph.add((URIRef(distributionURI), PROF.hasRole, URIRef(hasRole)))
                                    target_graph.add((URIRef(hasRole), RDF.type, SKOS.Concept))

                                logger.info(f"Successfully transformed dcat:distribution for modelldcatno:InformationModel: {s}")
                            else:
                                logger.warning(f"No dcat:hasFormat and rdfs:seeAlso result returned for modelldcatno:InformationModel: {s}")
                        
                        except Exception as e:
                            logger.error(f"Failed to reach endpoint for modelldcatno:InformationModel: {s}") 


        target_data = target_graph.serialize(format="turtle")
        logger.info(f"Transformed target Data: {target_data}")
        
        return target_data
        
    except Exception as e:
        logger.error(f"Transofrmation FAILED for batch: {batch}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise

