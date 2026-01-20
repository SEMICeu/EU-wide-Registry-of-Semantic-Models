from typing import Optional
from datetime import datetime
from .model import TransformationExecution, Transformation, JobStatus, TaskType
from prefect.context import get_run_context
from prefect import get_run_logger
from .adapters.prefect_adapter import PrefectArtifactAdapter
from .adapters.graph_adapter import GraphAdapter
from .utils import load_data_to_prov_graphdb

class ProvenanceTracker:
    """
    Main tracker that maintains YOUR PROV structure and publishes to multiple backends
    """
    
    def __init__(self, 
                 enable_graph_storage: bool = False,
                 enable_prefect_artifacts: bool = True):
        
        self.enable_graph_storage = enable_graph_storage
        self.enable_prefect_artifacts = enable_prefect_artifacts
        
        # Adapters
        self.prefect_adapter = PrefectArtifactAdapter()
        self.graph_adapter = GraphAdapter()

        self.lineage: Optional[TransformationExecution] = None

    def start_activity(self) -> TransformationExecution:
    
        context = get_run_context()

        transformation = Transformation()

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
        Update a transformation task
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

        if (status == JobStatus.completed):
            end_time = datetime.now()
            self.lineage.end_time = end_time
            logger.info(f"✓ Updated end_time to {end_time}")
        

    def publish(self, graphdb_endpoint: str ):
        """
        Mark activity complete and publish to all backends
        """

        logger = get_run_logger()
        if self.lineage is None:
            logger.warning("Cannot update status: no active lineage")
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
            
                load_data_to_prov_graphdb(
                    rdf_data=rdf_string,
                    graphdb_endpoint=graphdb_endpoint,
                    format="json-ld"
                )

                logger.info("✓ Published to provenance graph triple store")
            except Exception as e:
                logger.warning(f"Failed to create graph rdf: {e}")
                
            except Exception as e:
                logger.warning(f"Failed to publish to graph triple store: {e}")
        
       