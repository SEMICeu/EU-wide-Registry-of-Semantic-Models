from prefect import task
from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON, POST, URLENCODED
from ..util_sparql import execute_sparql_delete, execute_sparql_select, execute_sparql_update
import requests
import re
from string import Template

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def delete_descriptions(
        endpoint: str, 
        source_graph: str,
        target_graph: str, 
        delete_source_descriptions_query: str,
        delete_target_descriptions_query: str,
        auth_dict: dict
    ) :

    logger = get_run_logger()
    logger.info(f"deleting translations from {endpoint}")

    graph_uri = ""
    template = None
    if (target_graph != source_graph):
        graph_uri = target_graph
        template = Template(delete_target_descriptions_query)
    else:
        graph_uri = source_graph
        template = Template(delete_source_descriptions_query)
    
    params = {
        "graph_uri" : graph_uri
    }
    query = template.substitute(params)
    logger.info(f"[SPARQL] Deleting Query: {query}")

    result = ""
    sparql_result = execute_sparql_delete(endpoint, query.encode('utf-8'), auth_dict["username"], auth_dict["password"])
    if(sparql_result['http_code'] == 200):
        results = sparql_result['message']

    # Virtuoso returns plain text like "Delete from <...>, 403 triples"
    response = results

    # Extract number of triples if present
    deleted_count = 0
    if "triples" in response:
        try:
            deleted_count = int(response.split(",")[-1].strip().split()[0])
        except Exception:
            pass
    logger.info("translations deleted: " + str(deleted_count))
    return deleted_count

@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_descriptions_to_translate(
    endpoint: str,
    graph_uri: str,
    languages: dict,
    fetch_descriptions_query: str,
    auth_dict: dict
    ):

    logger = get_run_logger()
    logger.info(f"Fetching data for translation from {endpoint}")

    if languages is None:
        languages = ['en']
    logger.info("Translating in languages: " + str(languages))
    results_by_standard = {}

    for lang in languages:
        template = Template(fetch_descriptions_query)
        params = {
            "graph_uri" : graph_uri,
            "lang": lang
        }
        query = template.substitute(params)
        logger.info(f"[SPARQL] Fetching query: {query}")

        #sparql = SPARQLWrapper(endpoint)
        #sparql.setReturnFormat(JSON)
        #sparql.setQuery(query)
        #response = sparql.query().convert()

        sparql_result = execute_sparql_select(endpoint, query, "JSON", auth_dict["username"], auth_dict["password"])
        if(sparql_result['http_code'] == 200):
            results = sparql_result['data']

        for result in results["results"]["bindings"]:
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
def add_translations_to_graph_batch(
        endpoint: str, 
        graph_uri: str, 
        translations: str, 
        triple_template: str, 
        insert_query: str,
        auth_dict: dict
    ):

    logger = get_run_logger()
    logger.info("Running SPARQL update to insert translations...")

    successful_inserts = 0
    failed_inserts = 0
    errors = []

    for standard_uri, langs in translations.items():  # no ["translated"]
        triples = []

        for target_lang, data in langs.items():
            translated_text = data["text"]
            source_lang = data["source_lang"]

            #lang_tag = f"{target_lang}-t-{source_lang}-t0-mtec"
            final_text = f"test-{translated_text}"

            safe_text = final_text.replace('"', '\\"')

            template = Template(triple_template)
            params = {
                "standard_uri" : standard_uri,
                "safe_text" : safe_text,
                "target_lang" : target_lang,
                "source_lang" : source_lang
            }
            triple = template.substitute(params)



            #triple = f'<{standard_uri}> <http://purl.org/dc/terms/description> "{safe_text}"@{lang_tag} .'
            triples.append(triple)

        if not triples:
            continue

        #update_query = f"""
        #INSERT DATA {{
        #    GRAPH <{graph_uri}> {{
        #        {' '.join(triples)}
        #    }}
        #}}
        #"""

        template = Template(insert_query)
        params = {
                "graph_uri" : graph_uri,
                "triples" : ' '.join(triples),
            }
        update_query = template.substitute(params)
        

        try:
            logger.info(f"[SPARQL] Query {update_query}")

            #sparql = SPARQLWrapper(endpoint)
            #sparql.setMethod(POST)
            #sparql.setRequestMethod(URLENCODED)
            #sparql.setQuery(update_query)
            #result = sparql.query()

            sparql_result = execute_sparql_update(endpoint, update_query.encode('utf-8'), auth_dict["username"], auth_dict["password"])
            if (sparql_result['http_code'] == 200):
                logger.info(f"✔ Inserted translations for {standard_uri}")
                successful_inserts += 1
            else:
                error_msg = f"[SPARQL] update failed with status {sparql_result['http_code'] }: {sparql_result['message'] }"
                logger.error(error_msg)
                raise Exception(error_msg)
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
    logger = get_run_logger()
    batches = list(chunk_dict(results_by_standard, batch_size))
    logger.info(f"Creating {len(batches)} batches of size {batch_size}")
    return batches

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

#HUB_LANGUAGES = ["en", "fr", "de", "it", "sv", "el"]

def select_source_language(existing_langs):
    """
    Selects the best source language based on priority hubs.
    Falls back to the first available language if no hub is present.
    """
    HUB_LANGUAGES = ["en", "fr", "de", "it", "sv", "el"]
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

from app.api.v1.mlmodels import list_opus_pairs

@task(tags=["translate", "enrich"], retries=3, retry_delay_seconds=120, retry_jitter_factor=0.2)
def translate_batch_lock3(
        endpoint: str, 
        graph_uri: str, 
        translate_api: str, 
        batch_data: dict, 
        hub_languages: dict, 
        translate_batch_query: dict, 
        auth_dict: dict, 
        multi_target: bool = True,
        preferred_pivot_for_target: dict = None ):
    """
    Batch translation task with optional multi-target support.

    Args:
        endpoint: SPARQL endpoint
        graph_uri: Graph where descriptions are stored
        translate_api: Translation API URL
        batch_data: Dict like
            {
                "http://example/standard1": {
                    "existing": ["en", "fr"],
                    "missing": ["de", "pl"]
                },
                ...
            }
        multi_target (bool): 
            If True → combine multiple targets into one API call.
            If False → translate each target separately.

    Examples:
        - Direct multi-target (multi_target=True):
            en → [fr, de, it]  (1 call instead of 3)

        - Pivot single-target (multi_target=False):
            it → fr (1 call)
            fr → pl (1 call)

        - Pivot multi-target (multi_target=True):
            it → fr
            fr → [pl, el, sv]  (1 call)
    """
    logger = get_run_logger()
    TRANSLATE_API = translate_api

    translations = {}
    SUPPORTED_PAIRS = list_opus_pairs()
    logger.info(f"[Init] Loaded {len(SUPPORTED_PAIRS)} OPUS translation pairs")
    logger.info(f"[Init] hub_languages={hub_languages}, multi_target={multi_target}")

    def select_source_language(existing_langs):
        for hub in hub_languages:
            if hub in existing_langs:
                return hub
        return existing_langs[0] if existing_langs else None

    def safe_translate(text, src, tgt, context):
        """Single target translation call."""
        params = [("term", text), ("source", src), ("target", tgt)]
        api_resp = requests.get(TRANSLATE_API, params=params)
        if api_resp.status_code != 200:
            logger.warning(f"[API] {context}: {src}→{tgt} failed ({api_resp.status_code})")
            return None
        data = api_resp.json()
        if not data or "translations" not in data[0] or not data[0]["translations"]:
            logger.warning(f"[API] {context}: empty response for {src}→{tgt}: {data}")
            return None
        t = data[0]["translations"][0]
        result = t.get("term")
        logger.info(f"[OK] {context}: {src}→{tgt} = {result[:40]}...")
        return result

    def safe_translate_multi(text, src, targets, context):
        """Multi-target translation in one API call."""
        if not targets:
            return {}
        params = [("term", text), ("source", src)] + [("target", t) for t in targets]
        api_resp = requests.get(TRANSLATE_API, params=params)
        if api_resp.status_code != 200:
            logger.warning(f"[API] {context}: {src}→{targets} failed ({api_resp.status_code})")
            return {}
        data = api_resp.json()
        if not data or "translations" not in data[0]:
            logger.warning(f"[API] {context}: empty response for {src}→{targets}: {data}")
            return {}
        out = {}
        for t in data[0]["translations"]:
            tgt = t.get("lang")
            term = t.get("term")
            if tgt and term:
                logger.info(f"[OK] {context}: {src}→{tgt} = {term[:40]}...")
                out[tgt] = term
        return out

    def find_pivot(source, target):
        """Find a pivot hub language if no direct pair exists."""
        for hub in hub_languages:
            if (source, hub) in SUPPORTED_PAIRS and (hub, target) in SUPPORTED_PAIRS:
                logger.info(f"[Pivot] found pivot hub language {hub}")
                return hub
        return None

    def find_pivot2(source, target, preferred_pivot_for_target):
        """
        Find a pivot hub language using preferences if provided,
        otherwise fallback to hub_languages.
        """
        # First try the preferred pivot (if it exists and is supported)
        preferred = preferred_pivot_for_target.get(target)
        if preferred and (source, preferred) in SUPPORTED_PAIRS and (preferred, target) in SUPPORTED_PAIRS:
            logger.info(f"[Pivot] using preferred pivot {preferred} for {target}")
            return preferred

        # Fallback to default hub search
        for hub in hub_languages:
            if (source, hub) in SUPPORTED_PAIRS and (hub, target) in SUPPORTED_PAIRS:
                logger.info(f"[Pivot] fallback pivot {hub} for {target}")
                return hub

        return None

    for standard_uri, lang_map in batch_data.items():
        existing_langs = lang_map.get("existing", [])
        missing_langs = lang_map.get("missing", [])

        source_lang = select_source_language(existing_langs)
        if not source_lang or not missing_langs:
            logger.info(f"[Skip] {standard_uri}: no valid source or targets")
            continue

        logger.info(f"[Batch] {standard_uri}: source={source_lang}, missing={missing_langs}")

        template = Template(translate_batch_query)
        params = {
            "graph_uri" : graph_uri,
            "standard_uri" : standard_uri,
            "source_lang" : source_lang
        }
        query = template.substitute(params)
        logger.info(f"[Batch] Get description to be translated query: {query}")

        # fetch source text
        #sparql = SPARQLWrapper(endpoint)
        #sparql.setReturnFormat(JSON)
        #sparql.setQuery(query)
        #results = sparql.query().convert()

        sparql_result = execute_sparql_select(endpoint, query, "JSON", auth_dict["username"], auth_dict["password"])
        if(sparql_result['http_code'] == 200):
            results = sparql_result['data']

        bindings = results["results"]["bindings"]
        if not bindings:
            logger.warning(f"[Skip] {standard_uri}: no source text for {source_lang}")
            continue

        source_text = re.sub(r'[\x00-\x1f\x7f]', ' ', bindings[0]["description"]["value"]).strip()

        # --- Direct translations ---
        direct_targets = [t for t in missing_langs if (source_lang, t) in SUPPORTED_PAIRS]
        if direct_targets:
            logger.info(f"[Direct] {standard_uri}: {source_lang}→{direct_targets}")

        if multi_target:
            results = safe_translate_multi(source_text, source_lang, direct_targets, f"{standard_uri}")
            for out_lang, term in results.items():
                translations.setdefault(standard_uri, {})[out_lang] = {
                    "text": term,
                    "source_lang": source_lang
                }
        else:
            for tgt in direct_targets:
                term = safe_translate(source_text, source_lang, tgt, f"{standard_uri}")
                if term:
                    translations.setdefault(standard_uri, {})[tgt] = {
                        "text": term,
                        "source_lang": source_lang
                    }

        # --- Pivot translations ---
        for target_lang in [t for t in missing_langs if t not in translations.get(standard_uri, {})]:
            pivot = find_pivot2(source_lang, target_lang, preferred_pivot_for_target)
            if not pivot:
                logger.warning(f"[Pivot] {standard_uri}: no route {source_lang}→{target_lang}")
                continue

            logger.info(f"[Pivot] {standard_uri}: {source_lang}→{pivot}→{target_lang}")

            if multi_target:
                # Step 1: source → pivot
                pivot_res = safe_translate_multi(source_text, source_lang, [pivot], f"{standard_uri} (pivot)")
                if not pivot_res or pivot not in pivot_res:
                    continue
                mid_text = pivot_res[pivot]

                # Step 2: pivot → target
                final_res = safe_translate_multi(mid_text, pivot, [target_lang], f"{standard_uri} (via {pivot})")
                if final_res and target_lang in final_res:
                    translations.setdefault(standard_uri, {})[target_lang] = {
                        "text": final_res[target_lang],
                        "source_lang": pivot
                    }
            else:
                mid_text = safe_translate(source_text, source_lang, pivot, f"{standard_uri} (pivot)")
                if not mid_text:
                    continue
                term = safe_translate(mid_text, pivot, target_lang, f"{standard_uri} (via {pivot})")
                if term:
                    translations.setdefault(standard_uri, {})[target_lang] = {
                        "text": term,
                        "source_lang": pivot
                    }

    return translations