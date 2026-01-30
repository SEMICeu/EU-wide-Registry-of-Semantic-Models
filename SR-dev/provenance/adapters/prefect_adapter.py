from prefect.artifacts import create_table_artifact
from ..model import TransformationExecution

class PrefectArtifactAdapter:
    """
    Adapter: PROV -> Prefect Artifacts
    """
    
    @staticmethod
    def create_summary_table(lineage: TransformationExecution):
        """
        Create a summary table for Prefect UI
        """
        
        summary_data = [{
            "flow_run_id": str(lineage.id),
            "flow_name": lineage.title,
            "input_source": lineage.transformation.input_source if lineage.transformation.input_source else None,
            "output_source": lineage.transformation.output_source if lineage.transformation.output_source else None,
            "task_type": lineage.task.name if lineage.task else None,
            "status": lineage.status.name if lineage.status else None, 
            "started_at": lineage.start_time.isoformat() if lineage.start_time else None,
            "extracted_assets_from_source": lineage.transformation.extracted_assets_from_source,
            "transformed_assets" : lineage.transformation.transformed_assets,
            "succesfuly_validated_assets": lineage.transformation.succesfuly_validated_assets,
            "loaded_assets": lineage.transformation.loaded_assets,
            "ended_at": lineage.end_time.isoformat() if lineage.end_time else None,
            "generated": lineage.generated.accesURL if lineage.generated else None
        }]
        
        create_table_artifact(
            key="prefect-flow-summary",
            table=summary_data,
            description="Prefect flow execution summary"
        )