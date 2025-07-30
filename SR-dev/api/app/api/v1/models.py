from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

class AnalysisStatusEnum(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class OntologyMetric(BaseModel):
    standard_uri: str = Field(..., description="The URI of the dct:Standard ontology")
    preferred_namespace_uri: str = Field(..., description="The preferred namespace URI of the ontology")
    backlinks: int = Field(..., description="Number of other ontologies that use this ontology")
    lovrank: float = Field(..., description="LOVRank score between 0 and 1")
    main_namespace: Optional[str] = Field(None, description="The main namespace of the ontology")

class AnalysisResult(BaseModel):
    analysis_id: str = Field(..., description="Unique identifier for the analysis")
    total_ontologies: int = Field(..., description="Total number of ontologies processed")
    dependencies_established: int = Field(..., description="Number of dct:requires relationships created")
    execution_time: float = Field(..., description="Time taken to complete the analysis in seconds")
    ontology_metrics: List[OntologyMetric] = Field(..., description="Metrics for each ontology")
    log_file: str = Field(..., description="Path to the log file")
    started_at: datetime = Field(default_factory=datetime.now, description="When the analysis started")
    completed_at: Optional[datetime] = Field(None, description="When the analysis completed")

class AnalysisStatus(BaseModel):
    analysis_id: str = Field(..., description="Unique identifier for the analysis")
    status: AnalysisStatusEnum = Field(..., description="Current status of the analysis")
    progress: Optional[str] = Field(None, description="Current progress description")
    result: Optional[AnalysisResult] = Field(None, description="Analysis result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(default_factory=datetime.now, description="When the analysis was created")

class AnalysisRequest(BaseModel):
    """Request model for starting an analysis - currently no parameters needed but extensible"""
    config_override: Optional[Dict] = Field(None, description="Optional configuration overrides")
    
class AnalysisStartResponse(BaseModel):
    analysis_id: str = Field(..., description="Unique identifier for the started analysis")
    message: str = Field(..., description="Success message")
    status: AnalysisStatusEnum = Field(default=AnalysisStatusEnum.STARTING, description="Initial status")

class AnalysisListItem(BaseModel):
    analysis_id: str = Field(..., description="Unique identifier for the analysis")
    status: AnalysisStatusEnum = Field(..., description="Current status")
    progress: Optional[str] = Field(None, description="Current progress description")
    created_at: datetime = Field(..., description="When the analysis was created")
    execution_time: Optional[float] = Field(None, description="Execution time if completed")

class AnalysisListResponse(BaseModel):
    analyses: List[AnalysisListItem] = Field(..., description="List of all analyses")
    total: int = Field(..., description="Total number of analyses")

class DeleteResponse(BaseModel):
    message: str = Field(..., description="Success message")
    analysis_id: str = Field(..., description="ID of the deleted analysis")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    error_type: Optional[str] = Field(None, description="Type of error")

# Configuration models
class SPARQLConfig(BaseModel):
    sparql_query_endpoint: str
    sparql_update_endpoint: str
    bypass_ssl: bool = False

class AnalyzerConfig(BaseModel):
    sparql: SPARQLConfig
    sparql_query: str
    lovrank_update_query: str
    requires_update_query: str