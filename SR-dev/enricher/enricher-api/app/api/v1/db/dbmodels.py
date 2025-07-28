# models.py
from sqlalchemy import Column, String, DateTime, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class EnrichmentJob(Base):
    __tablename__ = "enrichment_jobs"

    id = Column(String, primary_key=True)
    graph_uri = Column(String)
    source_endpoint = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(Enum(JobStatus), default=JobStatus.pending)
    error_log = Column(Text, nullable=True)
    flow_run_id = Column(String, nullable=True)
    flow_url = Column(String, nullable=True)