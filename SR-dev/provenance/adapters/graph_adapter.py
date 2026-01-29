from prefect import get_run_logger
from ..model import TransformationExecution, TransformationExecutionDTO
import json
from prefect import get_run_logger
from string import Template
import requests

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
        # status_url = "http://purl.org/adms/status/" + lineage.status

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
                "TransformationExecution": "https://data.europa.eu/m8g/transform-validate-ontology#TransformationExecution",
                "Transformation": "https://data.europa.eu/m8g/transform-validate-ontology#Transformation",
                "Task": "https://data.europa.eu/m8g/transform-validate-ontology#Task",
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
                "task": {
                    "@id": "https://data.europa.eu/m8g/transform-validate-ontology#Task", 
                    "@type": "http://www.w3.org/2001/XMLSchema#string"
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

        output = json.dumps(json_ld, indent=2)
        logger.info(f"output {output}")

        return output

    @staticmethod
    def load_data_to_prov_graphdb(
        rdf_data: str, 
        graphdb_endpoint: str, 
        format: str = "json-ld"
    ) -> bool:
        """
        Load provenance RDF data into GraphDB.

        :param rdf_data: RDF content as string (Turtle, N-Triples, JSON-LD, etc.)
        :param graphdb_endpoint: SPARQL endpoint URL
        :param format: RDF format ("turtle", "json-ld", "xml", "nt", "n3")
        :return: True if upload successful, False otherwise
        """
        logger = get_run_logger()
        
        content_types = {
            "turtle": "text/turtle",
            "json-ld": "application/ld+json",
            "xml": "application/rdf+xml",
            "nt": "application/n-triples",
            "n3": "text/n3"
        }
        
        content_type = content_types.get(format, "application/ld+json")
        
        logger.info(f"Uploading {len(rdf_data)} bytes as {format}")
        
        try:
            response = requests.post(
                f"{graphdb_endpoint}/statements",
                data=rdf_data,
                headers={"Content-Type": content_type}
            )
            response.raise_for_status()

            if response.status_code == 204:
                logger.info("Upload to provenance GraphDB completed")
                return True
            else:
                logger.error(f"Upload failed with status {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    @staticmethod
    def cleanup_provenance_graphdb(
        repo_name: str,
        cleanup_query: str,
        keep_latest: int = 2,
        host: str = "http://localhost:7200",
    ) -> bool:
        """
        Clean up provenance GraphDB using a SPARQL DELETE query.
        Keeps only the N most recent executions based on endedAtTime.

        :param repo_name: Name/ID of the GraphDB repository
        :param cleanup_query: SPARQL DELETE query template with $keep_latest placeholder
        :param keep_latest: Number of latest executions to keep
        :param host: Base URL of the GraphDB server
        :return: True if cleanup successful, False otherwise
        """
        logger = get_run_logger()
        logger.info(f"Starting provenance cleanup – keeping latest {keep_latest} executions")

        check_url = f"{host}/rest/repositories/{repo_name}"
        update_url = f"{host}/repositories/{repo_name}/statements"

        check_response = requests.get(check_url)
        if check_response.status_code != 200:
            logger.error(f"Repository '{repo_name}' does not exist")
            return False

        logger.info(f"Repository '{repo_name}' exists")

        try:
            template = Template(cleanup_query)
            query = template.safe_substitute(keep_latest=keep_latest)

            logger.info(f"Executing DELETE query:\n{query}")

            response = requests.post(
                update_url,
                data={"update": query},
                timeout=120,
            )

            if response.status_code in (200, 204):
                logger.info(f"✓ Cleanup completed successfully (status {response.status_code})")
                return True

            logger.error(
                f"✗ Cleanup failed (status {response.status_code}): {response.text}"
            )
            return False

        except Exception:
            logger.exception("Failed to cleanup provenance GraphDB")
            return False
