from prefect import flow
from prefect.runtime import flow_run
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.v1.db.dbmodels import EnrichmentJob
from datetime import datetime, UTC
import os
from .tasks.classify_themes import fetch_themes_to_classify, classify, add_themes_to_graph
from .tasks.synonyms_class_labels import fetch_labels_to_synonyms, synonyms, add_synonyms_to_graph
from .tasks.translate_descriptions import fetch_descriptions_to_translate, translate, add_translations_to_graph, make_batches, translate_batch, add_translations_to_graph_batch, translate_batch_lock, translate_batch_lock2 

from prefect.logging import get_run_logger
from prefect.settings import PREFECT_UI_URL

import yaml
from pathlib import Path

from typing import Dict, List

from prefect.task_runners import ConcurrentTaskRunner

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "enrichment_jobs.db")

engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)

config_path = Path(__file__).resolve().parents[3] / "config.yaml"
with open(config_path, "r") as file:
    config = yaml.safe_load(file)

# Utility function to split a dict into chunks
def chunk_dict(data: Dict, chunk_size: int) -> List[Dict]:
    items = list(data.items())
    return [dict(items[i:i + chunk_size]) for i in range(0, len(items), chunk_size)]

@flow(name="enrichment-flow")
def enrichment_flow(graph_uri: str, source_endpoint: str, job_id: str = None, batch_size: int = 5):
    logger = get_run_logger()
    # ✅ Get Prefect flow_run_id
    flow_run_id = flow_run.id

    ui_base = PREFECT_UI_URL.value() if PREFECT_UI_URL.value() else "http://127.0.0.1:4200"
    flow_url = f"{ui_base}/flow-runs/flow-run/{flow_run_id}"
    logger.info(f"🔗 Flow started: {flow_url}")
    
    # ✅ Update DB with flow_run_id
    session = SessionLocal()
    try:
        job = session.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        if job:
            job.flow_run_id = flow_run_id
            job.flow_url = flow_url
            job.status = "running"
            session.commit()

        logger.info(f"Job {job_id} status set to RUNNING with flow_run_id {flow_run_id}")

        fetch_themes_future = fetch_themes_to_classify.submit(source_endpoint, graph_uri)
        classify_api = config["classify_api"]
        classify_future = classify.submit(classify_api, fetch_themes_future)
        add_themes_to_graph.submit(source_endpoint, graph_uri, classify_future)

        fetch_labels_future = fetch_labels_to_synonyms.submit(source_endpoint, graph_uri)
        synonyms_api = config["synonyms_api"]
        synonyms_future = synonyms.submit(synonyms_api, fetch_labels_future)
        add_synonyms_to_graph.submit(source_endpoint, graph_uri, synonyms_future)

        languages = config["languages"]
        #fetch_descriptions_future = fetch_descriptions_to_translate.submit(source_endpoint, graph_uri)
        #translate_api = config["translate_api"]
        #translate_future = translate.submit(source_endpoint, graph_uri, translate_api, fetch_descriptions_future)
        #add_translations_to_graph.submit(source_endpoint, graph_uri, translate_future)
        
        # Step 1: ferch
        fetch_descriptions_future = fetch_descriptions_to_translate.submit(source_endpoint, graph_uri, languages)
        # Step 2: Batch (as a Prefect task)
        batches_future = make_batches.submit(fetch_descriptions_future)  # only one dependency here
        

        # Step 3: Submit translation batches in parallel
        batch_futures = [
            translate_batch_lock.submit(source_endpoint, graph_uri, batch,  wait_for=[batches_future])
            for batch in batches_future.result()   # ensures Prefect sees only batch_translate as upstream
        ]

        # Step 4: Gather results
        all_translations = {}
        for f in batch_futures:
            result = f.result()
            for uri, langs in result.items():
                all_translations.setdefault(uri, {}).update(langs)

        # Step 5: Insert into graph
        translate_future = add_translations_to_graph_batch.submit(source_endpoint, graph_uri, all_translations)

        # Wait for results
        class_res = classify_future.result()
        trans_res = translate_future.result()
        syn_res = synonyms_future.result()

        logger.info("All tasks finished:")
        logger.info(f"All tasks finished: {class_res}, {trans_res}, {syn_res}")

        #data = fetch_data_to_classify(source_endpoint, graph_uri)
        #classify_and_enrich(source_endpoint, graph_uri, data)

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