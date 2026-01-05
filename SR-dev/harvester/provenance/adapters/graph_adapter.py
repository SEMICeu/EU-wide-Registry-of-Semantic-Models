from prefect import get_run_logger
from ..model import TransformationExecution, TransformationExecutionDTO
import json

class GraphAdapter:
    """
    Adapter: PROV -> Graph triple store
    """
    
    @staticmethod
    def create_rdf(lineage: TransformationExecution):
        """
        Create an rdf summary for Graph triples
        """

        logger = get_run_logger()

        url = "http://localhost:4200/runs/flow-run/" + lineage.id

        dto = TransformationExecutionDTO(
            id= url,
            title= lineage.title,
            start_time= lineage.start_time,
            end_time= lineage.end_time,
            status= lineage.status,
            task= lineage.task,
            transformation= lineage.transformation,
            generated= lineage.generated
        )

        json_ld = {    
            "@context": {
                "Activity": "http://www.w3.org/ns/prov#Activity",
                "Code": "http://www.w3.org/2004/02/skos/core#Concept",
                "DateTime": "http://www.w3.org/2001/XMLSchema#dateTime",
                "Distribution": "https://www.w3.org/ns/dcat#Distribution",
                "Entity": "http://www.w3.org/ns/prov#Entity",
                "NonNegativeInteger": "http://www.w3.org/2001/XMLSchema#nonNegativeInteger",
                "String": "http://www.w3.org/2001/XMLSchema#string",
                "Text": "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString",
                "TransfomationExecution": "https://data.europa.eu/m8g/transform-validate-ontology#TransformationExecution",
                "Transformation": "https://data.europa.eu/m8g/transform-validate-ontology#Transformation",
                "TransformationReport": "https://data.europa.eu/m8g/transform-validate-ontology#TransformationReport",
                "URI": "http://www.w3.org/2001/XMLSchema#anyURI",
                "declaresOutputDistribution": {
                "@id": "https://data.europa.eu/m8g/transform-validate-ontology#declaresOutputDistribution",
                "@type": "@id"
                },
                "endedAtTime": {
                "@id": "http://www.w3.org/ns/prov#endedAtTime",
                "@type": "http://www.w3.org/2001/XMLSchema#dateTime"
                },
                "executedTransformation": {
                "@container": "@set",
                "@id": "https://data.europa.eu/m8g/transform-validate-ontology#executedTransformation",
                "@type": "@id"
                },
                "generated": {
                "@id": "http://www.w3.org/ns/prov#generated",
                "@type": "@id"
                },
                "hadInputSource": {
                "@id": "https://data.europa.eu/m8g/transform-validate-ontology#hadInputSource",
                "@type": "@id"
                },
                "identifier": {
                "@id": "http://purl.org/dc/terms/identifier",
                "@type": "http://www.w3.org/2001/XMLSchema#string"
                },
                "startedAtTime": {
                "@id": "http://www.w3.org/ns/prov#startedAtTime",
                "@type": "http://www.w3.org/2001/XMLSchema#dateTime"
                },
                "status": {
                "@id": "http://www.w3.org/ns/adms#status",
                "@type": "@id"
                },
                "title": {
                "@container": "@set",
                "@id": "http://purl.org/dc/terms/title",
                "@type": "http://www.w3.org/1999/02/22-rdf-syntax-ns#langString"
                }
        },    
            **dto.model_dump(by_alias=True, mode='json')
        }

        output =  json.dumps(json_ld, indent=2)
        logger.info(f"output {output}")

        