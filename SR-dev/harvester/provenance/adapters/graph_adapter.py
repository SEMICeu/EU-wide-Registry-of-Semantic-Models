from pathlib import Path
from prefect.artifacts import create_table_artifact
import sys

from ..model import TransformationExecution, Transformation, TransformationReport, JobStatus

class GraphAdapter:
    """Adapter: PROV -> Graph triple store"""
    
    @staticmethod
    def create_summary_table(lineage: TransformationExecution):
        """Create a summary table for Prefect UI"""
        
        summary_data = [{
            "flow_run_id": str(lineage.id),
            "flow_name": lineage.title,
            "task_type": lineage.task.name if lineage.task else None,
            "status": lineage.status.name if lineage.status else None, 
            "started_at": lineage.start_time.isoformat(),
            # "loaded_input": current / total,
            # "transformed": current / total,
            # "validated": current / total,
            # "loaded_output": current / total,
            "ended_at": lineage.end_time.isoformat(),

        }]
        
        create_table_artifact(
            key="prefect-flow-summary",
            table=summary_data,
            description="Prefect flow execution summary"
        )