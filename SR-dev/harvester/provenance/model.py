from uuid import UUID
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class TaskType(str, Enum):
    extract = "extract"
    load_input = "load_input"
    load_output = "load_output"
    transform = "transform"
    validate = "validate"

class Distribution(BaseModel):
    accesURL: str

class Transformation(BaseModel):
    input_source: Optional[Distribution] = None
    output_source: Optional[Distribution] = None

class TransformationReport(BaseModel):
    accesURL: str

class TransformationExecution(BaseModel):
    id: str
    title: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    status: JobStatus
    task: Optional[TaskType] = None
    transformation: Transformation
    generated: Optional[TransformationReport] = None