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
    """

    input_source: Optional[Distribution] = None
    output_source: Optional[Distribution] = None

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

class TransformationExecutionDTO(BaseModel):
    """
    The DTO for the transformation execution. (needed for the graph adapter)
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: str = Field(alias="@id")
    title: Optional[str] = Field(None, alias="@title")
    start_time: datetime = Field(alias="@startedAtTime")
    end_time: Optional[datetime] = Field(default=None, alias="@endedAtTime")
    status: JobStatus = Field(alias="@status")
    task: Optional[TaskType] = Field(default=None, alias="@task")
    transformation: Optional[Transformation] = None
    generated: Optional[TransformationReport] = None