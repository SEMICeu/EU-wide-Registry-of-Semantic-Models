from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class Synonym(BaseModel):
    term: str
    source: str
    score: int

class DetectedLanguage(BaseModel):
    language: str
    score: float

class TranslationItem(BaseModel):
    term: str
    lang: str

class TranslationResponse(BaseModel):
    detectedLanguage: DetectedLanguage
    translations: List[TranslationItem]

class ErrorResponse(BaseModel):
    error: str
    detail: str

class Theme(BaseModel):
    term: str
    score: int

class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class EnrichmentJobPost(BaseModel):
    id: str
    graph_uri: str
    source_endpoint: str

class EnrichmentJobResponse(BaseModel):
    id: str
    graph_uri: str
    source_endpoint: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus
    error_log: Optional[str] = None

