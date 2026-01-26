from prefect import task, get_run_logger

from prefect.flows import R
from rdflib import Graph, RDF, Namespace, Literal, URIRef
from rdflib.namespace import XSD
from pathlib import Path
from rdflib import Literal, XSD
from datetime import datetime, timezone
from .construct_item import get_property
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

            # adms:Asset/dct:license
            for a, _, distribution_uri in source_graph.triples((s, ADMSAPIT.hasSemanticAssetDistribution, None)):
                try:

                    target_graph.add((a, DCAT.distribution, URIRef(distribution_uri)))
                    target_graph.add((URIRef(distribution_uri), RDF.type, ADMS.AssetDistribution))

                    # adms:Asset/dcat:distribution/dcat:isDefinedBy/rdfs:Class
                    for _, _, classUri in source_graph.triples((None, ADMSAPIT.hasKeyClass, None)):
                        target_graph.add((URIRef(classUri), RDFS.isDefinedBy, URIRef(distribution_uri)))
                        target_graph.add((URIRef(classUri), RDF.type, RDFS.Class))

                        logger.info(f"rdfs label {str(RDFS.label)}")

                        result = await get_property(
                            str(classUri), 
                            str(RDFS.label),
                            config["web_source_url"],
                            config["construct_custom_query"],
                            )

                        if result:
                            class_graph = Graph()
                            class_graph.parse(data=result, format="turtle")

                            label_found = False
                            # adms:Asset/dcat:distribution/dcat:isDefinedBy/rdfs:Class/rdfs:label
                            for _, _, label in class_graph.triples((None, RDFS.label, None)):

                                if isinstance(label, Literal):
                                    target_graph.add((URIRef(classUri), RDFS.label, label))
                                    label_found = True

                            if not label_found:
                                uri_str = str(classUri)
                                if '/' in uri_str:
                                    label = uri_str.split('/')[-1]
                                    logger.info(f"No rdfs:label found in result for rdfs:Class {uri_str}, using generated label: {label}")
                                    target_graph.add((URIRef(classUri), RDFS.label, Literal(label, lang="en")))


                    logger.info("Requesting admsapit:hasSemanticAssetDistribution...")
                
                    headers = {
                    "Accept" : "text/turtle"
                    }
                    response = requests.get(str(distribution_uri),headers=headers)

                    distribution_graph = Graph()
                    distribution_graph.parse(data=response.text, format="turtle")

                    if response.status_code == 200:
                        logger.info("Request Succesfull for admsapit:hasSemanticAssetDistribution")

                        for _, b, c in distribution_graph.triples((distribution_uri, None, None)):
        
                            # adms:Asset/dct:license
                            if b == DCT.license:
                                license_str = str(c)
                                if license_str in ["https://w3id.org/italia/controlled-vocabulary/licences/A21_CCBY40", "http://creativecommons.org/licenses/by/4.0/"]:
                                    license_url = "http://publications.europa.eu/resource/authority/licence/CC_BY_4_0"
                                    logger.info(f"transforming license url {license_str} to {license_url}")
                                    
                                    target_graph.add((s, DCT.license, URIRef(license_url)))
                                    target_graph.add((URIRef(license_url), RDF.type, DCT.LicenseDocument))
                                    target_graph.add((URIRef(license_url), RDF.type, SKOS.Concept))
                                    target_graph.add((URIRef(license_url), SKOS.inScheme, URIRef("http://publications.europa.eu/resource/authority/license")))
                                else:
                                    logger.error(f"license url not recognized {license_str}")
                            
                            # adms:Asset/dcat:distribution/dcat:downloadURL
                            elif b == DCAT.downloadURL:
                                logger.info(f"extracting dcat:downloadURL")
                                target_graph.add((distribution_uri, DCAT.downloadURL, Literal(c, datatype=XSD.anyURI)))
                            
                            # adms:Asset/dcat:distribution/dct:format
                            elif b == DCT['format']:
                                logger.info(f"extracting dct:format")
                                target_graph.add((distribution_uri, DCT['format'], URIRef(c)))
                                target_graph.add((URIRef(c), RDF.type, DCT.MediaTypeOrExtent))
                            
                            # adms:Asset/dcat:distribution/dct:title
                            elif b == DCT.title:     
                                logger.info(f"extracting dct:title")                          
                                target_graph.add((distribution_uri, DCT.title, Literal(c, datatype=RDF.langString)))

                except requests.exceptions.RequestException as e:
                    logger.error(f"Failed to check distribution {distribution_uri}: {e}")                   

        # adms:Asset/dct:description
        for s, p, o in source_graph.triples((None, DCT.description, None)):
            if str(o).endswith(".png") or str(o).endswith(".jpg"):
                logger.info(" dct:description: found a .png or .jpg, description will not be added")

            else:
                target_graph.add((s, DCT.description, o))

        # adms:Asset/m8g:isReusedBy
        for s, p, o in source_graph.triples((None, ADMSAPIT.semanticAssetInUse, None)):
            target_graph.add((s, M8G.isReusedBy,  Literal(o, datatype=XSD.anyURI)))

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
                
        # adms:Asset/dcat:keyword
        for s, p, o in source_graph.triples((None, DCAT.keyword, None)):
            if isinstance(o, Literal) and o.language is None:
                target_graph.add((s, DCAT.keyword, Literal(str(o), lang='it')))
        else:
            target_graph.add((s, DCAT.keyword, o))

        # adms:Asset/dct:language
        for s, p, o in source_graph.triples((None, DCT.language, None)):
            target_graph.add((s, DCT.language, URIRef(str(o))))
            target_graph.add((URIRef(str(o)), RDF.type, SKOS.Concept))

        # adms:Asset/dct:modified
        for s, p, o in source_graph.triples((None, DCT.modified, None)):
            try:
                value = str(o)

                if "T" in value:
                    dateTime = value.replace("+00:00", "Z")

                    if "." in dateTime and not dateTime.endswith("Z"):
                        dateTime = dateTime.split(".")[0] + "Z"

                    if not dateTime.endswith("Z"):
                        dateTime = dateTime + "Z"

                elif len(value) == 10:
                    dateTime = value + "T00:00:00Z"

                else:
                    logger.info(f"dct:modified - unsupported format: {o}")
                    continue

                target_graph.add((s,DCT.modified,Literal(dateTime, datatype=XSD.dateTime)))

            except Exception as e:
                logger.info(f"dct:modified - could not convert date: {o} (error: {e})")
                continue

        # adms:Asset/adms:status
        for s, p, o in source_graph.triples((None, ADMSAPIT.status, None)):
            mappedStatus = ""
            status_value = str(o)

            if status_value in ["published", "catalogued"]:
                mappedStatus = "http://purl.org/adms/status/Completed"
            elif status_value in ["initial draft", "draft", "final draft"]:
                mappedStatus = "http://purl.org/adms/status/UnderDevelopment"
            else:
                logger.warning(f"Could not identify status code: {status_value}")
            
            if len(mappedStatus) > 0:              
                target_graph.add((s, ADMS.status, URIRef(mappedStatus)))
                target_graph.add((URIRef(mappedStatus), RDF.type, SKOS.Concept))

        # adms:Asset/dct:theme
        for s, p, o in source_graph.triples((None, DCAT.theme, None)):
            target_graph.add((s, DCAT.theme, o))
            target_graph.add((o, RDF.type, SKOS.Concept))

        # adms:Asset/dct:title
        for s, p, o in source_graph.triples((None, DCT.title, None)):
            target_graph.add((s, DCT.title, Literal(o, datatype=RDF.langString)))

        # adms:Asset/owl:versionInfo
        for s, p, o in source_graph.triples((None, OWL.versionInfo, None)):
            if isinstance(o, Literal) and o.language == "en":
                logger.info("adding owl:versionInfo with 'en' language tag")
                target_graph.add((s, OWL.versionInfo, Literal(str(o), datatype=XSD.string))) 

        # adms:Asset/dct:requires
        for s, p, o in source_graph.triples((None, OWL.imports, None)):
            target_graph.add((s, DCT.requires, URIRef(o)))
            # target_graph.add((o, RDF.type, ADMS.Asset))

        # adms:Asset/dcat:contactPoint
        # adms:Asset/dcat:contactPoint/vcard:Kind
        for s, p, o in source_graph.triples((None, DCAT.contactPoint, None)):

            result = await get_property(
                        str(o), 
                        str(VCARD.hasEmail),
                        config["web_source_url"],
                        config["construct_custom_query"],
                        )

            vcard_graph = Graph()
            vcard_graph.parse(data=result, format="turtle")

            target_graph.add((s, DCAT.contactPoint, URIRef(o)))
            target_graph.add((URIRef(o), RDF.type, VCARD.Kind))

            for a, _, hasEmail in vcard_graph.triples((None, VCARD.hasEmail, None)):
                logger.info(f"Found email: {hasEmail} for contact point: {a}")       
                target_graph.add((hasEmail, RDF.type, VCARD.Email))
                target_graph.add((URIRef(o), VCARD.hasEmail, URIRef(hasEmail)))

        # adms:Asset/dct:creator
        # adms:Asset/dct:creator/foaf:Agent/foaf:name
        # adms:Asset/dct:creator/foaf:Agent/dct:spatial
        for s, p, o in source_graph.triples((None, DCT.creator, None)):

            result = await get_property(
                        str(o), 
                        str(FOAF.name),
                        config["web_source_url"],
                        config["construct_custom_query"],
                        )

            agent_graph = Graph()
            agent_graph.parse(data=result, format="turtle")

            target_graph.add((s, DCT.creator, URIRef(o)))
            target_graph.add((URIRef(o), RDF.type, FOAF.Agent))

            spatial_code = "http://publications.europa.eu/resource/authority/country/ITA"
            target_graph.add((URIRef(o), DCT.spatial, URIRef(spatial_code)))
            target_graph.add((URIRef(spatial_code), RDF.type, DCT.Location))

            for a, _, name in agent_graph.triples((None, FOAF.name, None)):
                logger.info(f"dct:creator: Found foaf:name: {name} for Agent: {a}")

                if isinstance(name, Literal) and name.language == None:
                    logger.info(f"dct:creator: No language found for foaf:name: {name} for Agent: {a}")
                    target_graph.add((URIRef(o), FOAF.name, Literal(name, lang="it")))

                else:
                    target_graph.add((URIRef(o), FOAF.name, Literal(name, datatype=RDF.langString)))

        # adms:Asset/dct:publisher
        # adms:Asset/dct:publisher/foaf:Agent/foaf:name
        # adms:Asset/dct:publisher/foaf:Agent/dct:spatial
        for s, p, o in source_graph.triples((None, DCT.publisher, None)):

            result = await get_property(
                        str(o), 
                        str(FOAF.name),
                        config["web_source_url"],
                        config["construct_custom_query"],
                        )

            agent_graph = Graph()
            agent_graph.parse(data=result, format="turtle")

            target_graph.add((s, DCT.publisher, URIRef(o)))
            target_graph.add((URIRef(o), RDF.type, FOAF.Agent))

            spatial_code = "http://publications.europa.eu/resource/authority/country/ITA"
            target_graph.add((URIRef(o), DCT.spatial, URIRef(spatial_code)))
            target_graph.add((URIRef(spatial_code), RDF.type, DCT.Location))

            for a, _, name in agent_graph.triples((None, FOAF.name, None)):
                logger.info(f"dct:publisher: Found foaf:name: {name} for Agent: {a}")

                if isinstance(name, Literal) and name.language == None:
                    logger.info(f"dct:publisher: No language found for foaf:name: {name} for Agent: {a}")
                    target_graph.add((URIRef(o), FOAF.name, Literal(name, lang="it")))

                else:
                    target_graph.add((URIRef(o), FOAF.name, Literal(name, datatype=RDF.langString)))
        target_data = target_graph.serialize(format="turtle")

        logger.info(f"Transformed target Data: {target_data}")
        return target_data
        
    except Exception as e:
        logger.error(f"Transofrmation FAILED for batch: {batch}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        raise

