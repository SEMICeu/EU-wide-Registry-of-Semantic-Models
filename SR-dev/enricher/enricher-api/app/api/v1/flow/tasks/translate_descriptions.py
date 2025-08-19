from prefect import task
from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON, POST, URLENCODED
import requests
import re

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_descriptions_to_translate(
    endpoint: str = "https://health.semic.eu/virtuoso/sparql",
    graph_uri: str = "http://semic.registry.eu",
    languages=None
    ):

    logger = get_run_logger()
    logger.info(f"Fetching data for translation from {endpoint}")

    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)

    if languages is None:
        languages = ['en']
    logger.info("Translating in languages: " + str(languages))
    results_by_standard = {}

    for lang in languages:
        query = f"""
        PREFIX dct: <http://purl.org/dc/terms/>
        SELECT DISTINCT ?standard ?existingLang
        FROM <{graph_uri}>
        WHERE {{
            ?standard a dct:Standard .
            ?standard dct:description ?existingDesc .
            BIND(lang(?existingDesc) AS ?existingLang)

            FILTER NOT EXISTS {{
                ?standard dct:description ?missingDesc .
                FILTER (lang(?missingDesc) = "{lang}")
            }}
        }}
        """

        sparql.setQuery(query)
        response = sparql.query().convert()

        for result in response["results"]["bindings"]:
            standard_uri = result["standard"]["value"]
            existing_lang = result["existingLang"]["value"]

            std_entry = results_by_standard.setdefault(standard_uri, {"existing": set(), "missing": set()})
            std_entry["existing"].add(existing_lang)
            std_entry["missing"].add(lang)

    # Convert sets to lists
    for entry in results_by_standard.values():
        entry["existing"] = list(entry["existing"])
        entry["missing"] = list(entry["missing"])

    logger.info(results_by_standard)
    return results_by_standard

@task
def translate(source_endpoint, graph_uri, translate_api, results_by_standard):
    logger = get_run_logger()
    logger.info("Running translation...")

    TRANSLATE_API = translate_api
    sparql = SPARQLWrapper(source_endpoint)
    sparql.setReturnFormat(JSON)

    translations = {}

    for standard_uri, lang_map in results_by_standard.items():
        existing_langs = lang_map.get("existing", [])
        missing_langs = lang_map.get("missing", [])

        if not existing_langs or not missing_langs:
            continue

        source_lang = existing_langs[0]  # pick one source language
        logger.info(f"Using {source_lang} as source for translating {standard_uri} to {missing_langs}")

        # Get the description in source_lang
        sparql.setQuery(f"""
            PREFIX dct: <http://purl.org/dc/terms/>
            SELECT ?description
            FROM <{graph_uri}>
            WHERE {{
                <{standard_uri}> dct:description ?description .
                FILTER(lang(?description) = "{source_lang}")
            }}
            LIMIT 1
        """)

        try:
            response = sparql.query().convert()
            bindings = response["results"]["bindings"]
            if not bindings:
                logger.warning(f"No description found for {standard_uri} in {source_lang}")
                continue

            source_text = bindings[0]["description"]["value"]
            clean_text = re.sub(r'[\x00-\x1f\x7f]', ' ', source_text).strip()

            params = [
                ("term", clean_text),
                ("source", source_lang),
            ] + [("target", lang) for lang in missing_langs]

            api_response = requests.get(TRANSLATE_API, params=params)

            if api_response.status_code == 200:
                api_json = api_response.json()
                for translation in api_json[0]["translations"]:
                    target_lang = translation["lang"]
                    translated_text = translation["term"]

                    translations.setdefault(standard_uri, {})[target_lang] = {
                        "term": translated_text,
                        "source": source_lang
                    }

                    logger.info(f"✔ Translated {standard_uri} ({source_lang} → {target_lang}): {translated_text}")
            else:
                logger.error(f"❌ API error {api_response.status_code} for {standard_uri}: {api_response.text}")

        except Exception as e:
            logger.error(f"❌ Error processing {standard_uri}: {e}")

    return {"translated": translations}

@task
def add_translations_to_graph(source_endpoint, graph_uri, translations):
    logger = get_run_logger()
    logger.info("Running SPARQL update to insert translations...")

    sparql = SPARQLWrapper(source_endpoint)
    sparql.setMethod(POST)
    sparql.setRequestMethod(URLENCODED)

    for standard_uri, langs in translations["translated"].items():
        triples = []

        for target_lang, data in langs.items():
            translated_text = data["term"]
            source_lang = data["source"]

            lang_tag = f"{target_lang}-t-{source_lang}-t0-mtec"
            final_text = f"test-{translated_text}"

            # Escape quotes
            safe_text = final_text.replace('"', '\\"')

            triple = f'<{standard_uri}> <http://purl.org/dc/terms/description> "{safe_text}"@{lang_tag} .'
            triples.append(triple)

        if not triples:
            continue

        update_query = f"""
        INSERT DATA {{
            GRAPH <{graph_uri}> {{
                {' '.join(triples)}
            }}
        }}
        """

        try:
            sparql.setQuery(update_query)
            sparql.query()
            logger.info(f"✔ Inserted translations for {standard_uri}")
        except Exception as e:
            logger.error(f"❌ Failed to insert translations for {standard_uri}: {e}")

@task
def add_translations_to_graph_batch(endpoint, graph_uri, translations):
    logger = get_run_logger()
    logger.info("Running SPARQL update to insert translations...")

    sparql = SPARQLWrapper(endpoint)
    sparql.setMethod(POST)
    sparql.setRequestMethod(URLENCODED)

    successful_inserts = 0
    failed_inserts = 0
    errors = []

    for standard_uri, langs in translations.items():  # no ["translated"]
        triples = []

        for target_lang, data in langs.items():
            translated_text = data["text"]
            source_lang = data["source_lang"]

            lang_tag = f"{target_lang}-t-{source_lang}-t0-mtec"
            final_text = f"test-{translated_text}"

            safe_text = final_text.replace('"', '\\"')
            triple = f'<{standard_uri}> <http://purl.org/dc/terms/description> "{safe_text}"@{lang_tag} .'
            triples.append(triple)

        if not triples:
            continue

        update_query = f"""
        INSERT DATA {{
            GRAPH <{graph_uri}> {{
                {' '.join(triples)}
            }}
        }}
        """

        try:
            logger.info(f"Query {update_query}")
            sparql.setQuery(update_query)
            result = sparql.query()
            logger.info(f"✔ Inserted translations for {standard_uri}")
            successful_inserts += 1
        except Exception as e:
            error_msg = f"Failed to insert translations for {standard_uri}: {e}"
            logger.error(f"❌ {error_msg}")
            errors.append(error_msg)
            failed_inserts += 1

    # Summary logging
    logger.info(f"Translation insertion summary: {successful_inserts} successful, {failed_inserts} failed")
    
    # Fail the task if any insertions failed
    if failed_inserts > 0:
        error_summary = f"Translation insertion failed for {failed_inserts} items. Errors: {'; '.join(errors)}"
        logger.error(error_summary)
        raise Exception(error_summary)
    
    return {
        "successful_inserts": successful_inserts,
        "failed_inserts": failed_inserts,
        "total_processed": successful_inserts + failed_inserts
    }

from math import ceil

def chunk_dict(data, chunk_size):
    """Split dict into chunks of size chunk_size."""
    items = list(data.items())
    for i in range(0, len(items), chunk_size):
        yield dict(items[i:i+chunk_size])

@task
def make_batches(results_by_standard, batch_size=4):
    return list(chunk_dict(results_by_standard, batch_size))

@task(tags=["translate", "enrich"], retries=3, retry_delay_seconds=120, retry_jitter_factor=0.2)
def translate_batch(source_endpoint, graph_uri, translate_api, batch_data):
    from SPARQLWrapper import SPARQLWrapper, JSON
    import requests, re
    from prefect import get_run_logger

    logger = get_run_logger()
    TRANSLATE_API = translate_api
    sparql = SPARQLWrapper(source_endpoint)
    sparql.setReturnFormat(JSON)

    translations = {}

    for standard_uri, lang_map in batch_data.items():
        existing_langs = lang_map.get("existing", [])
        missing_langs = lang_map.get("missing", [])

        if not existing_langs or not missing_langs:
            continue

        source_lang = existing_langs[0]  # pick one source language
        logger.info(f"[Batch] Using {source_lang} for {standard_uri} → {missing_langs}")

        # Fetch source description
        sparql.setQuery(f"""
            PREFIX dct: <http://purl.org/dc/terms/>
            SELECT ?description
            FROM <{graph_uri}>
            WHERE {{
                <{standard_uri}> dct:description ?description .
                FILTER(lang(?description) = "{source_lang}")
            }}
            LIMIT 1
        """)
        try:
            resp = sparql.query().convert()
            bindings = resp["results"]["bindings"]
            if not bindings:
                continue

            source_text = re.sub(r'[\x00-\x1f\x7f]', ' ', bindings[0]["description"]["value"]).strip()

            # Call translation API once for multiple targets
            params = [("term", source_text), ("source", source_lang)] + [
                ("target", lang) for lang in missing_langs
            ]
            api_resp = requests.get(TRANSLATE_API, params=params)
            #logger.info("translate api:" + TRANSLATE_API)
            #logger.info("params:" + str(params))
            if api_resp.status_code == 200:
                for t in api_resp.json()[0]["translations"]:
                    translations.setdefault(standard_uri, {})[t["lang"]] = {
                        "text": t["term"],
                        "source_lang": source_lang
                    }
            else:
                logger.error(f"API error {api_resp.status_code} for {standard_uri}")

        except Exception as e:
            logger.error(f"Error processing {standard_uri}: {e}")

    return translations

from collections import defaultdict
import threading, time
# Global lock store (per (source, target) pair)
# Per-(source,target) lock
_model_locks = defaultdict(threading.Lock)

HUB_LANGUAGES = ["en", "fr", "de", "it", "sv", "el"]

def select_source_language(existing_langs):
    """
    Selects the best source language based on priority hubs.
    Falls back to the first available language if no hub is present.
    """
    for hub in HUB_LANGUAGES:
        if hub in existing_langs:
            return hub
    return existing_langs[0] if existing_langs else None

@task(tags=["translate", "enrich"], retries=3, retry_delay_seconds=120, retry_jitter_factor=0.2)
def translate_batch_lock(endpoint, graph_uri, translate_api, batch_data):
    logger = get_run_logger()
    TRANSLATE_API = translate_api
    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)

    translations = {}

    for standard_uri, lang_map in batch_data.items():
        existing_langs = lang_map.get("existing", [])
        missing_langs = lang_map.get("missing", [])

        if not existing_langs or not missing_langs:
            continue

        source_lang = select_source_language(existing_langs)
        if not source_lang:
            continue  # No source language available, skip
        logger.info(f"[Batch] Using {source_lang} for {standard_uri} → {missing_langs}")

        # Get source text
        sparql.setQuery(f"""
            PREFIX dct: <http://purl.org/dc/terms/>
            SELECT ?description
            FROM <{graph_uri}>
            WHERE {{
                <{standard_uri}> dct:description ?description .
                FILTER(lang(?description) = "{source_lang}")
            }}
            LIMIT 1
        """)
        try:
            resp = sparql.query().convert()
            bindings = resp["results"]["bindings"]
            if not bindings:
                continue

            source_text = re.sub(r'[\x00-\x1f\x7f]', ' ', bindings[0]["description"]["value"]).strip()

            for target_lang in missing_langs:
                lock_key = (source_lang, target_lang)
                with _model_locks[lock_key]:
                    # Keep trying until API works
                    while True:
                        params = [("term", source_text), ("source", source_lang), ("target", target_lang)]
                        api_resp = requests.get(TRANSLATE_API, params=params)

                        if api_resp.status_code == 200:
                            data = api_resp.json()
                            if not data or "translations" not in data[0] or not data[0]["translations"]:
                                logger.warning(f"No translations for {standard_uri} {source_lang}→{target_lang}, response: {data}")
                                break
                            t = data[0]["translations"][0]
                            translations.setdefault(standard_uri, {})[t["lang"]] = {
                                "text": t["term"],
                                "source_lang": source_lang
                            }
                            break  # Success → leave lock
                        else:
                            logger.warning(
                                f"API error {api_resp.status_code} for {standard_uri} ({source_lang}→{target_lang}), retrying in 5s"
                            )
                            time.sleep(5)  # Wait and retry until ready

        except Exception as e:
            logger.error(f"Error processing {standard_uri}: {e}")

    return translations

# Locks per (source, target) pair
_model_locks = defaultdict(threading.Lock)

@task(tags=["translate", "enrich"], retries=3, retry_delay_seconds=120, retry_jitter_factor=0.2)
def translate_batch_lock2(source_endpoint, graph_uri, batch_data):
    logger = get_run_logger()
    TRANSLATE_API = "http://127.0.0.1:8000/enricher-api/v1/translate"
    sparql = SPARQLWrapper(source_endpoint)
    sparql.setReturnFormat(JSON)

    translations = {}

    for standard_uri, lang_map in batch_data.items():
        existing_langs = lang_map.get("existing", [])
        missing_langs = lang_map.get("missing", [])

        if not existing_langs or not missing_langs:
            continue

        source_lang = existing_langs[0]
        logger.info(f"[Batch] Using {source_lang} for {standard_uri} → {missing_langs}")

        # Get source text
        sparql.setQuery(f"""
            PREFIX dct: <http://purl.org/dc/terms/>
            SELECT ?description
            FROM <{graph_uri}>
            WHERE {{
                <{standard_uri}> dct:description ?description .
                FILTER(lang(?description) = "{source_lang}")
            }}
            LIMIT 1
        """)
        try:
            resp = sparql.query().convert()
            bindings = resp["results"]["bindings"]
            if not bindings:
                continue

            source_text = re.sub(r'[\x00-\x1f\x7f]', ' ', bindings[0]["description"]["value"]).strip()

            # Sort targets by lock acquisition order to avoid deadlocks
            sorted_targets = sorted(missing_langs)

            # Acquire all necessary locks for this batch of translations
            locks_to_release = []
            try:
                for target_lang in sorted_targets:
                    lock_key = (source_lang, target_lang)
                    _model_locks[lock_key].acquire()
                    locks_to_release.append(_model_locks[lock_key])

                # While holding locks, keep retrying until API succeeds for all targets
                while True:
                    params = [("term", source_text), ("source", source_lang)] + [
                        ("target", lang) for lang in sorted_targets
                    ]
                    api_resp = requests.get(TRANSLATE_API, params=params)

                    if api_resp.status_code == 200:
                        for t in api_resp.json()[0]["translations"]:
                            translations.setdefault(standard_uri, {})[t["lang"]] = {
                                "text": t["term"],
                                "source_lang": source_lang
                            }
                        break  # Success
                    else:
                        logger.warning(
                            f"API error {api_resp.status_code} for {standard_uri} ({source_lang}→{sorted_targets}), retrying in 5s"
                        )
                        time.sleep(5)

            finally:
                # Always release locks
                for lock in locks_to_release:
                    lock.release()

        except Exception as e:
            logger.error(f"Error processing {standard_uri}: {e}")

    return translations