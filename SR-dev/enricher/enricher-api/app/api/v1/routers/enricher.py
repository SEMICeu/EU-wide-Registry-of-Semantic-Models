from fastapi import APIRouter, Query, HTTPException, Request, Depends
import os
from typing import List, Optional
import logging
import uuid
from sqlalchemy.orm import Session
import sys
from pathlib import Path
import asyncio
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v1.models import ErrorResponse, JobStatus
from app.api.v1.db.dbmodels import EnrichmentJob
from app.api.v1.models import EnrichmentJobResponse, EnrichmentJobPost
from app.api.v1.db.db import get_db
from app.api.v1.flow.enrichment_flow import enrichment_flow
from app.schemas.tasktype import TaskType
logger = logging.getLogger(__name__)

enricher_router = APIRouter()

@enricher_router.post("/job",
    response_model=EnrichmentJobPost,
    responses={
        200: {"description": "Successful response", "model": EnrichmentJobPost},
        400: {"description": "Bad Request", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Post a job to the enricher",  
    description="This endpoint returns the job created",
    response_description="The response is a JSON object of the job created.")
async def submitjob(
    request: Request,
    endpoint: str = Query(
        default="https://health.semic.eu/virtuoso/sparql", 
        min_length=1, 
        description="the source endpoint used for the job"),
    graph_uri: str = Query(
        default="http://semic.registry.eu", 
        min_length=1, 
        description="the source graph_uri used for the job"),
    task : Optional[TaskType] = Query(
        "all", 
        description="Either all, or select one of those available"),
    db: Session = Depends(get_db)
    ):

    try:
        job_id = str(uuid.uuid4())
        job = EnrichmentJob(
            id=job_id,
            graph_uri=graph_uri,
            source_endpoint=endpoint
        )
        db.add(job)
        db.commit()

        logger.info(f"enrichment_flow is {enrichment_flow}")
        logger.info(f"callable? {callable(enrichment_flow)}")

        asyncio.create_task(asyncio.to_thread(enrichment_flow, graph_uri, endpoint, task, job_id))

        response = EnrichmentJobPost(
            id = job_id,
            graph_uri = graph_uri,
            source_endpoint = endpoint
        )
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(detail=str(e), error="INVALID_INPUT").model_dump()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(detail=str(e), error="INTERNAL_ERROR").model_dump()
        )
    
@enricher_router.get("/job/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(EnrichmentJob).get(job_id)
    if not job:
        return {"error": "Not found"}
    return job.__dict__

@enricher_router.delete("/jobs")
def delete_all_jobs(db: Session = Depends(get_db)):
    deleted = db.query(EnrichmentJob).delete()
    db.commit()
    return {"message": f"Deleted {deleted} job(s)"}

@enricher_router.delete("/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(EnrichmentJob).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"message": f"Deleted job {job_id}"}

@enricher_router.get("/jobs", response_model=List[EnrichmentJobResponse])
def list_jobs(
        db: Session = Depends(get_db),
        status: Optional[List[JobStatus]] = Query(None, description="Filter jobs by status")
    ):
    query = db.query(EnrichmentJob)
    if status:
        query = query.filter(EnrichmentJob.status.in_(status))
    jobs = query.order_by(EnrichmentJob.created_at.desc()).all()
    return jobs