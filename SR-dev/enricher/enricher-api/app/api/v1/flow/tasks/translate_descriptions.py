from prefect import task
from prefect.logging import get_run_logger
from SPARQLWrapper import SPARQLWrapper, JSON, POST, URLENCODED
import requests
import re


@task(retries=3, retry_delay_seconds=20, retry_jitter_factor=0.2)
def fetch_descriptions_to_translate(
    source_endpoint: str = "http://63.32.50.253:81/sparql",
    graph_uri: str = "http://semic.registry.eu"
):
    logger = get_run_logger()
    logger.info(f"Fetching data for translation from {source_endpoint}")

    sparql = SPARQLWrapper(source_endpoint)
    sparql.setReturnFormat(JSON)

    languages = ["en", "fr", "it"]
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
def add_translations_to_graph_batch(source_endpoint, graph_uri, translations):
    logger = get_run_logger()
    logger.info("Running SPARQL update to insert translations...")

    sparql = SPARQLWrapper(source_endpoint)
    sparql.setMethod(POST)
    sparql.setRequestMethod(URLENCODED)

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
            sparql.query()
            logger.info(f"✔ Inserted translations for {standard_uri}")
        except Exception as e:
            logger.error(f"❌ Failed to insert translations for {standard_uri}: {e}")

from math import ceil

def chunk_dict(data, chunk_size):
    """Split dict into chunks of size chunk_size."""
    items = list(data.items())
    for i in range(0, len(items), chunk_size):
        yield dict(items[i:i+chunk_size])

@task
def make_batches(results_by_standard, batch_size=4):
    return list(chunk_dict(results_by_standard, batch_size))

@task(tags=["translate", "enrich"])
def translate_batch(source_endpoint, graph_uri, batch_data):
    from SPARQLWrapper import SPARQLWrapper, JSON
    import requests, re
    from prefect import get_run_logger

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
