from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class JobStatus(str, Enum):
    """
    The status of a current running job.
    """

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class TaskType(str, Enum):
    """
    The type of task that is being executed.
    """

    extract = "extract"
    load_input = "load_input"
    load_output = "load_output"
    transform = "transform"
    validate = "validate"

class Distribution(BaseModel):
    """
    The distribution of a resource.
    """

    accesURL: str

class Transformation(BaseModel):
    """
    The transformation of a resource.

        input_source: Distribution of the input resource.
        output_source: Distribution of the output resource.
        extracted_assets: amount of assets extracted from the source
        transformed_assets: amount of assets transformed to conform with Semantic Registry Model
        validated_assets: amount of assets validated by the SHACL validation
        failed_validation_assets: amount of assets that failed the SHACL validation
        loaded_assets: amount of assets loaded in the Semantic Registry
    """

    input_source: Optional[Distribution] = None
    output_source: Optional[Distribution] = None

    extracted_assets_from_source: int = 0
    transformed_assets : int = 0
    succesfuly_validated_assets: int = 0
    failed_validation_assets: int = 0
    loaded_assets: int = 0

class TransformationReport(BaseModel):
    """
    The report of a transformation.
    """

    accesURL: str

class TransformationExecution(BaseModel):
    """
    The provenance data for the execution of a transformation.

    Attributes:
        id: Unique identifier of the transformation execution.
        title: prefect generated title of the execution.
        start_time: Timestamp indicating when the execution started.
        end_time: Timestamp indicating when the execution finished, if completed.
        status: Current status of the execution.
        task: Type of task performed during the execution.
        transformation: The transformation that was executed.
        generated: Report or artifact generated as a result of the execution.
    """

    id: str
    title: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    status: JobStatus
    task: Optional[TaskType] = None
    transformation: Transformation
    generated: Optional[TransformationReport] = None

    def __str__(self) -> str:
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()
        
        return f"""
TransformationExecution:
    Start Time: {self.start_time}
    End Time: {self.end_time or 'In Progress'}
    Duration: {f'{duration}s' if duration else 'N/A'}

Transformation:
    Input Access URL: {self.transformation.input_source.accesURL if self.transformation.input_source else 'N/A'}
    Output Access URL: {self.transformation.output_source.accesURL if self.transformation.output_source else 'N/A'}
    Extracted Assets: {self.transformation.extracted_assets_from_source}
    Transformed Assets: {self.transformation.transformed_assets}
    Validated Assets: {self.transformation.succesfuly_validated_assets}
    Failed Validation Assets: {self.transformation.failed_validation_assets}
    Loaded Assets: {self.transformation.loaded_assets}

Provenance Report: 
    ProvenanceAccess URL: {self.generated.accesURL if self.generated else 'N/A'}
"""
# ID: {self.id}
# Title: {self.title or 'N/A'}
# Status: {self.status.value}
# Task: {self.task.value if self.task else 'N/A'}
# Generated Report: {self.generated.accesURL if self.generated else 'N/A'}

class TransformationExecutionDTO(BaseModel):
    """
    The DTO for the transformation execution. (needed for the graph adapter)
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: str = Field(alias="@id")
    title: Optional[str] = Field(None, alias="title")
    start_time: datetime = Field(alias="startedAtTime")
    end_time: Optional[datetime] = Field(default=None, alias="endedAtTime")
    status: JobStatus = Field(alias="status")
    task: Optional[TaskType] = Field(default=None, alias="task")
    transformation: Optional[Transformation] = None
    generated: Optional[TransformationReport] = None