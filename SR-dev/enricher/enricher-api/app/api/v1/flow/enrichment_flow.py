from prefect import flow, task
from prefect.runtime import flow_run
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.api.v1.db.dbmodels import EnrichmentJob
from datetime import datetime, UTC
import os
from .tasks.classify_themes import fetch_themes_to_classify, classify, add_themes_to_graph
from .tasks.synonyms_class_labels import fetch_labels_to_synonyms, synonyms, add_synonyms_to_graph
from .tasks.translate_descriptions import delete_descriptions, fetch_descriptions_to_translate, translate, add_translations_to_graph, make_batches, translate_batch, add_translations_to_graph_batch, translate_batch_lock3 

from prefect.logging import get_run_logger
from prefect.settings import PREFECT_UI_URL

import yaml
from pathlib import Path

from typing import Dict, List


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "db", "enrichment_jobs.db")

engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)

#config_path = Path(__file__).resolve().parents[3] / "config_prefect.yaml"
#with open(config_path, "r") as file:
#    config = yaml.safe_load(file)

# Utility function to split a dict into chunks
def chunk_dict(data: Dict, chunk_size: int) -> List[Dict]:
    items = list(data.items())
    return [dict(items[i:i + chunk_size]) for i in range(0, len(items), chunk_size)]

# --- Aggregate all translations ---
@task
def combine_translations(batch_results):
    all_translations = {}
    for result in batch_results:
        for uri, langs in result.items():
            all_translations.setdefault(uri, {}).update(langs)
    return all_translations

def load_config():
    config_path = Path(__file__).resolve().parents[3] / "config_prefect.yaml"
    with open(config_path, "r") as file:
        return yaml.safe_load(file)
    
@flow(name="enrichment-flow")
def enrichment_flow(task: str = "all", job_id: str = None):
    logger = get_run_logger()
    # ✅ Get Prefect flow_run_id
    flow_run_id = flow_run.id

    ui_base = PREFECT_UI_URL.value() if PREFECT_UI_URL.value() else "http://127.0.0.1:4200"
    flow_url = f"{ui_base}/flow-runs/flow-run/{flow_run_id}"
    logger.info(f"🔗 Flow started: {flow_url}")
    
    config = load_config()
    if(config["sparql"]["authentication"]):
        source_endpoint = config["sparql"]["auth_endpoint"]
    else:
        source_endpoint = config["sparql"]["source_endpoint"]
    source_graph = config["sparql"]["source_graph_uri"]
    target_graph = config["sparql"]["target_graph_uri"]
    logger.info(f"[SPARQL] source endpoint: {source_endpoint}")
    logger.info(f"[SPARQL] source graph uri: {source_graph}")
    logger.info(f"[SPARQL] target graph uri: {target_graph}")

    auth_dict = {"username": None, "password": None}
    if(config["sparql"]["authentication"]):
        config_auth_path = Path(__file__).resolve().parents[3] / config["sparql"]["auth_file"]
        with open(config_auth_path, "r") as file:
            config_auth = yaml.safe_load(file)
            username = config_auth['username']
            password = config_auth['password']
            logger.info(f"[SPARQL] username: {username}")
            logger.info(f"[SPARQL] password: {password}")
            auth_dict = {"username": username, "password": password}
    # ✅ Update DB with flow_run_id
    session = SessionLocal()
    try:
        job = session.query(EnrichmentJob).filter(EnrichmentJob.id == job_id).first()
        if job:
            job.flow_run_id = flow_run_id
            job.flow_url = flow_url
            job.status = "running"
            job.started_at = datetime.now()
            session.commit()

        logger.info(f"Job {job_id} status set to RUNNING with flow_run_id {flow_run_id}")

        if(task == "all" or task == "classify"):
            fetch_themes_to_classify_query = config["classify"]["fetch_themes_to_classify_query"]
            fetch_themes_future = fetch_themes_to_classify.submit(source_endpoint, source_graph, fetch_themes_to_classify_query, auth_dict)
            classify_api = config["classify"]["classify_api"]
            classify_future = classify.submit(classify_api, fetch_themes_future)
            add_classification_query = config["classify"]["add_themes"]
            add_themes_to_graph.submit(source_endpoint, source_graph, target_graph, classify_future, add_classification_query, auth_dict)

        if(task == "all" or task == "synonyms"):
            fetch_labels_to_synonyms_query = config["synonyms"]["fetch_labels_to_synonyms_query"]
            fetch_labels_future = fetch_labels_to_synonyms.submit(source_endpoint, source_graph, fetch_labels_to_synonyms_query, auth_dict)
            synonyms_api = config["synonyms"]["synonyms_api"]
            synonyms_future = synonyms.submit(synonyms_api, fetch_labels_future)
            add_synonyms_query = config["synonyms"]["add_synonyms"]
            add_synonyms_to_graph.submit(source_endpoint, source_graph, target_graph, synonyms_future, add_synonyms_query, auth_dict)

        if(task == "all" or task == "translate"):
            #fetch_descriptions_future = fetch_descriptions_to_translate.submit(source_endpoint, graph_uri)

            #translate_future = translate.submit(source_endpoint, graph_uri, translate_api, fetch_descriptions_future)
            #add_translations_to_graph.submit(source_endpoint, graph_uri, translate_future)
            
            # Step 0: delete
            delete_source_descriptions_query = config["translate"]["delete_source_descriptions_query"]
            delete_target_descriptions_query = config["translate"]["delete_target_descriptions_query"]
            delete_descriptions_future = delete_descriptions.submit(source_endpoint, source_graph, target_graph, delete_source_descriptions_query, delete_target_descriptions_query, auth_dict)
            # Step 1: fetch
            languages = config["translate"]["languages"]
            fetch_descriptions_query = config["translate"]["fetch_descriptions_query"]
            fetch_descriptions_future = fetch_descriptions_to_translate.submit(source_endpoint, source_graph, languages, fetch_descriptions_query, auth_dict, wait_for=[delete_descriptions_future])
            # Step 2: Batch (as a Prefect task)
            batch_size = config["translate"]["batch_size"]
            batches_future = make_batches.submit(fetch_descriptions_future, batch_size)  # only one dependency here
            

            # Step 3: Submit translation batches in parallel
            translate_api = config["translate"]["translate_api"]
            hub_languages = config["translate"]["hub_languages"]
            translate_batch_query = config["translate"]["translate_batch_query"]
            multi_target = config["translate"]["multi_target"]
            preferred_pivot_for_target = config["translate"]["preferred_pivot_for_target"]
            batch_futures = [
                translate_batch_lock3.submit(source_endpoint, source_graph, translate_api, batch, hub_languages, translate_batch_query, auth_dict, multi_target,  preferred_pivot_for_target, wait_for=[batches_future])
                for batch in batches_future.result()   # ensures Prefect sees only batch_translate as upstream
            ]

            # Step 4: Gather results
            all_translations = {}
            for f in batch_futures:
                result = f.result()
                for uri, langs in result.items():
                    all_translations.setdefault(uri, {}).update(langs)

            # Step 5: Insert into graph
            triple_template = config["translate"]["add_translations"]["triple_template"]
            insert_query = config["translate"]["add_translations"]["insert_query"]
            translate_future = add_translations_to_graph_batch.submit(source_endpoint, target_graph, all_translations, triple_template, insert_query, auth_dict)

        # Wait for results
        if(task == "all" or task == "classify"):
            class_res = classify_future.result()
            logger.info(f"Task classify finished: {class_res}")
        if(task == "all" or task == "synonyms"):
            syn_res = synonyms_future.result()
            logger.info(f"Task synonyms finished: {syn_res}")
        if(task == "all" or task == "translate"):
            trans_res = translate_future.result()
            logger.info(f"Task translate finished: {trans_res}")


        logger.info("All tasks finished")
        #logger.info(f"All tasks finished: {class_res}, {trans_res}, {syn_res}")

        #data = fetch_data_to_classify(source_endpoint, graph_uri)
        #classify_and_enrich(source_endpoint, graph_uri, data)

        # ✅ Mark job as completed
        if job:
            job.status = "completed"
            job.completed_at = datetime.now()
            session.commit()
            logger.info(f"Job {job_id} status set to COMPLETED")

        logger.info(f"Job {job_id} status set to COMPLETED")

    except Exception as e:
        # ✅ Mark job as failed
        if job:
            session.rollback()  # very important
            job.flow_run_id = flow_run_id
            job.flow_url = flow_url
            job.status = "failed"
            job.error_log = str(e)
            job.completed_at = datetime.now()
            session.commit()
            logger.error(f"Job {job_id} status set to FAILED due to error: {e}")

        raise  # re-raise so Prefect marks the flow as failed

    finally:
        session.close()
