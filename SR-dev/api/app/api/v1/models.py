from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class OntologyMetric(BaseModel):
    standard_uri: str = Field(..., description="The URI of the dct:Standard ontology")
    preferred_namespace_uri: str = Field(..., description="The preferred namespace URI of the ontology")
    backlinks: int = Field(..., description="Number of other ontologies that use this ontology")
    lovrank: float = Field(..., description="LOVRank score between 0 and 1")

class AnalysisResult(BaseModel):
    analysis_id: str = Field(..., description="Unique identifier for the analysis")
    total_ontologies: int = Field(..., description="Total number of ontologies processed")
    dependencies_established: int = Field(..., description="Number of dct:requires relationships created")
    execution_time: float = Field(..., description="Time taken to complete the analysis in seconds")
    ontology_metrics: List[OntologyMetric] = Field(..., description="Metrics for each ontology")
    log_file: str = Field(..., description="Path to the log file")
    started_at: datetime = Field(default_factory=datetime.now, description="When the analysis started")
    completed_at: Optional[datetime] = Field(None, description="When the analysis completed")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of error")