from prefect import flow
from prefect.runtime import flow_run
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.v1.db.dbmodels import EnrichmentJob
from datetime import datetime, UTC
import os
from .classify_task import fetch_data_to_classify, classify_and_enrich

from prefect.logging import get_run_logger

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "enrichment_jobs.db")

engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)

@flow
def enrichment_flow(graph_uri: str, source_endpoint: str, job_id: str = None):
    logger = get_run_logger()
     # ✅ Get Prefect flow_run_id
    flow_run_id = flow_run.id

    # ✅ Update DB with flow_run_id
    session = SessionLocal()
    try:
        job = session.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        if job:
            job.flow_run_id = flow_run_id
            job.status = "running"
            session.commit()

        logger.info(f"Job {job_id} status set to RUNNING with flow_run_id {flow_run_id}")

        data = fetch_data_to_classify(source_endpoint, graph_uri)
        classify_and_enrich(source_endpoint, graph_uri, data)

        # ✅ Mark job as completed
        if job:
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            session.commit()
            logger.info(f"Job {job_id} status set to COMPLETED")

        logger.info(f"Completed enrichment for job_id={job_id}")

    except Exception as e:
        # ✅ Mark job as failed
        if job:
            job.status = "failed"
            job.error_log = str(e)
            job.completed_at = datetime.now(UTC)
            session.commit()
            logger.error(f"Job {job_id} status set to FAILED due to error: {e}")

        raise  # re-raise so Prefect marks the flow as failed

    finally:
        session.close()