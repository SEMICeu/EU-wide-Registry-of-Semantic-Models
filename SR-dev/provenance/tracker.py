from typing import Optional
from datetime import datetime
from .model import Distribution, TransformationExecution, Transformation, JobStatus, TaskType, TransformationReport
from prefect.context import get_run_context
from prefect import get_run_logger
from .adapters.prefect_adapter import PrefectArtifactAdapter
from .adapters.graph_adapter import GraphAdapter
import re

class ProvenanceTracker:
    """
    Main tracker that maintains YOUR PROV structure and publishes to multiple backends
    """

    def __init__(self, 
                 enable_graph_storage: bool = True,
                 enable_prefect_artifacts: bool = False):
        
        self.enable_graph_storage = enable_graph_storage
        self.enable_prefect_artifacts = enable_prefect_artifacts
        
        # Adapters
        self.prefect_adapter = PrefectArtifactAdapter()
        self.graph_adapter = GraphAdapter()

        self.lineage: Optional[TransformationExecution] = None

    def start_activity(self, source_acces_url: str) -> TransformationExecution:
        """
        Start the provenance for a new pipeline 
        """

        context = get_run_context()

    
        source_distribution = Distribution(accesURL=source_acces_url)
        transformation = Transformation(input_source=source_distribution, output_source=None)

        activity = TransformationExecution(
            id=str(context.flow_run.id),
            title=context.flow_run.name,
            start_time=datetime.now(),
            status=JobStatus.running,
            task=None,
            transformation=transformation)

        self.lineage = activity

        return activity


    def update_activity_task(self, task: TaskType):
        """
        Update the current task being processed in the pipeline
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot update task: no active lineage")
            return

        self.lineage.task = task
        logger.info(f"✓ Updated task type to {task}")


    def update_status(self,status: JobStatus):
        """
        Update status of the transformation execution.
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot update status: no active lineage")
            return

        self.lineage.status = status
        logger.info(f"✓ Updated status to {status}")
    

    def update_transformation(self, task: TaskType, amount: int):
        """
        Update a transformation task
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot update transformation: no active lineage")
            return

        if task == TaskType.load_input:
            self.lineage.transformation.extracted_assets_from_source = amount
            logger.info(f"✓ Updated transformation: extracted_assets_from_source: {amount}")
        if task == TaskType.transform:
            self.lineage.transformation.transformed_assets = amount
            logger.info(f"✓ Updated transformation: transformed_assets: {amount}")
        if task == TaskType.validate:
            self.lineage.transformation.succesfuly_validated_assets = amount
            logger.info(f"✓ Updated transformation: succesfuly_validated_assets: {amount}")
            failed_validation_assets =  self.lineage.transformation.transformed_assets - amount
            self.lineage.transformation.failed_validation_assets = failed_validation_assets
            logger.info(f"✓ Updated transformation: failed_validation_assets: {failed_validation_assets}")
        if task == TaskType.load_output:
            self.lineage.transformation.loaded_output = amount
            logger.info(f"✓ Updated transformation: loaded output: {amount}")


    def update_completed(self,  target_acces_url: str, provenance_acces_url: str, member_state: str, report_path: str ):
        """
        Update properties when the pipeline has finished + call to write the transformation to the report
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot update transformation properties: no active lineage")
            return

        if (self.lineage.status == JobStatus.completed):
            end_time = datetime.now()
            self.lineage.end_time = end_time
            logger.info(f"✓ Updated end_time to {end_time}")

            target_distribution = Distribution(accesURL=target_acces_url)
            self.lineage.transformation.output_source = target_distribution
            logger.info(f"✓ Updated output_source to {target_acces_url}")

            transformationReport = TransformationReport(accesURL=provenance_acces_url)
            self.lineage.generated = transformationReport
            logger.info(f"✓ Updated generated rdf to {provenance_acces_url}")

            self.write_transformation_to_report(member_state, report_path)
        

    def publish(self, graphdb_endpoint: str ):
        """
        Mark activity complete and publish to all backends
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot publish provenance: no active lineage")
            return

        # Publish to Prefect artifacts
        if self.enable_prefect_artifacts:
            try:
                self.prefect_adapter.create_summary_table(self.lineage)
                logger.info("✓ Published to Prefect artifacts")
            except Exception as e:
                logger.warning(f"Failed to create Prefect artifacts: {e}")

        # Publish to graph triple store
        if self.enable_graph_storage:
            try:
                rdf_string = self.graph_adapter.create_rdf(self.lineage)
            
                self.graph_adapter.load_data_to_prov_graphdb(
                    rdf_data=rdf_string,
                    graphdb_endpoint=graphdb_endpoint,
                    format="json-ld"
                )

                logger.info("✓ Published to provenance graph triple store")
                
            except Exception as e:
                logger.warning(f"Failed to publish to graph triple store: {e}")

    def clean_db(self, repo_name: str, cleanup_query: str, keep_latest: int, host: str):
        """
        call for deleting old entries in the provenance DB
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot clean provenance db: no active lineage")
            return

        if self.enable_graph_storage:
            try:

                self.graph_adapter.cleanup_provenance_graphdb(
                    repo_name=repo_name,
                    cleanup_query=cleanup_query,
                    keep_latest=keep_latest,
                    host=host,
                )

                logger.info("✓ Cleaned provenance graph triple store")
                
            except Exception as e:
                logger.warning(f"Failed to clean provenance graph triple store: {e}")

    
    def initialise_report(self, member_state: str, provenance_report_dir: str) -> None:
        """
        Create or overwrite the provenanve report for a given member state.
        """

        logger = get_run_logger()

        report_template = f"""
# Harvesting Report {member_state}

...

## Transformation Report

{{transformation_report}}

## Failed entries

"""

        try:
            report_path = f"{provenance_report_dir}/{member_state.lower()}_harvesting_report.md"

            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report_template)

            logger.info(f"✓ Harvesting report initialised: {report_path}")

        except Exception as e:
            logger.warning(f"Failed to initialise report for {member_state}: {e}")
        
    def write_transformation_to_report(self, member_state: str, report_path: str):
        """
        Write properties which hold valuable information from the transformation to the report for the memberstates
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot write transformation properties to report: no active lineage")
            return

        try:
            
            if not report_path:
                logger.warning(f"No report path defined for member state: {member_state}")
                return

            if (self.lineage.status != JobStatus.completed):
                logger.warning(f"Can only write transformation to report if the pipeline has finished! (JobStatus != completed)")
                return
            
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "{transformation_report}" in content:
                
                content = content.replace("{transformation_report}", self.lineage.__str__())
            else:
                logger.warning("{transformation_report} not found in report")
         
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            
        except Exception as e:
            logger.warning(f"Failed to write transformation to report: {e}")


    def write_failed_validation_to_report(self, member_state: str, failed_validation: str, report_path: str):
        """
        Write entries who failed the validation SHACL validation to a report. 
        This report is aimed to inform memberstates about issues regarding the quality of the data
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot write failed validation entries to report: no active lineage")
            return

        try:
            logger.info(f"SHACL validation failed for MS {member_state}: {failed_validation}")
            
            if not report_path:
                logger.warning(f"No report path defined for member state: {member_state}")
                return
            
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            existing_entries = re.findall(r"### Failed Entry (\d+)", content)
            next_number = len(existing_entries) + 1

            failed_entry = f"\n### Failed Entry {next_number}\n\n```\n{failed_validation}\n```\n"
            content += failed_entry
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"✓ Failed validation written to report: {report_path}")
            
        except Exception as e:
            logger.warning(f"Failed to write validation to report: {e}")
        
        
       