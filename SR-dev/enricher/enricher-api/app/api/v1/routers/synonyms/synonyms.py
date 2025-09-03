from fastapi import APIRouter, Query, HTTPException, Request
import os
from typing import List, Optional, Optional, Dict, Any
import logging
import re
import traceback
from fastapi.responses import JSONResponse

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v1.models import ErrorResponse, Synonym
from app.api.v1.mlmodels import best_synonym_for_context
from app.api.v1.schemas.source import Source
from nltk.corpus import wordnet
import requests
from .synonyms_cache import get_cached_synonyms, set_cached_synonyms, SessionLocal, SynonymCache, InvalidSynonym, get_cache_stats, filter_invalid_synonyms
from sqlalchemy.orm import Session
import json

logger = logging.getLogger(__name__)

synonyms_router = APIRouter()

@synonyms_router.get("/synonyms",
    response_model=List[Synonym],
    responses={
        200: {"description": "Successful response", "model": List[Synonym]},
        400: {"description": "Bad Request", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Get a list of synonyms for a term",  
    description="This endpoint returns a list of synonyms for a term, filtered if needed by source",
    response_description="The response is a JSON object including list of synonyms with their source ")
async def synonyms(
    request: Request,
    term: str = Query(default=..., description="A word used as input to find synonyms."),
    sources : Optional[Source] = Query(None, description="If this value is not set, nltk has priority on datamuse, so if synonyms are not found in nltk, they will be searched in datamuse. If the value is set to all, the order by score is not maintained."),
    context: str = Query(default=None, description="A sentence that can be used to give a context and reorder the results."),
    max: int = Query(default=None, min=1, description="The maximum number of results.")
    ):

    try:
        config = request.app.state.config_synonyms
        altervista_endpoint = config['altervista']['endpoint']
        altervista_key = config['altervista']['key']
        altervista_language = config['altervista']['language']
        datamuse_endpoint = config['datamuse']['endpoint']
        datamuse_max_results = config['datamuse']['max_results']
        expiration_hours = config['cache']['expiration_hours']
        model_repo_id = config['model']["repo_id"]
        model_local_dir = config["model"]["local_dir"]
        logger.info(f"[SYNONYMS] model_repo_id: {model_repo_id}")
        logger.info(f"[SYNONYMS] model_local_dir: {model_local_dir}")

        resultList = []
        nltk_syns = {}
        altervista_syns = {}
        datamuse_syns = {}

        has_nltk_valid = False
        has_alt_valid = False
        # NLTK
        if sources in ("nltk", None, "all"):
            nltk_syns = get_nltk_synonyms(term, expiration_hours)
            raw_list = list(nltk_syns.keys())

            # Filter out invalid synonyms for this source
            nltk_syns_filtered = filter_invalid_synonyms(term, "nltk", raw_list)
            has_nltk_valid = bool(nltk_syns_filtered)
            # Compute removed invalid ones
            removed = set(raw_list) - set(nltk_syns_filtered)

            # ✅ Log everything
            logger.info(f"[SYNONYMS][nltk] Raw: {raw_list}")
            logger.info(f"[SYNONYMS][nltk] Filtered: {nltk_syns_filtered}")
            if removed:
                logger.info(f"[SYNONYMS][nltk] Invalidated synonyms for '{term}': {list(removed)}")

            for syn in nltk_syns_filtered:
                resultList.append(Synonym(term=syn, source="nltk", score=nltk_syns[syn]))

        # Altervista
        if sources in ("altervista", "all") or ((sources is None) and not has_nltk_valid):
            altervista_syns = get_altervista_synonyms(altervista_endpoint, term, altervista_key, expiration_hours, altervista_language)
            raw_list = list(altervista_syns.keys())

            # Filter out invalid synonyms for this source
            altervista_syns_filtered = filter_invalid_synonyms(term, "altervista", raw_list)
            has_alt_valid = bool(altervista_syns_filtered)
            # Compute removed invalid ones
            removed = set(raw_list) - set(altervista_syns_filtered)

            # ✅ Log everything
            logger.info(f"[SYNONYMS][altervista] Raw: {raw_list}")
            logger.info(f"[SYNONYMS][altervista] Filtered: {altervista_syns_filtered}")
            if removed:
                logger.info(f"[SYNONYMS][altervista] Invalidated synonyms for '{term}': {list(removed)}")

            for syn in altervista_syns_filtered:
                resultList.append(Synonym(term=syn, source="altervista", score=altervista_syns[syn]))

        # Datamuse
        if sources in ("datamuse", "all") or ((sources is None) and not has_nltk_valid and not has_alt_valid):
            datamuse_syns = get_datamuse_synonyms(datamuse_endpoint, term, expiration_hours, datamuse_max_results)
            raw_list = list(datamuse_syns.keys())

            # Filter out invalid synonyms for this source
            datamuse_syns_filtered = filter_invalid_synonyms(term, "datamuse", raw_list)

            # Compute removed invalid ones
            removed = set(raw_list) - set(datamuse_syns_filtered)

            # ✅ Log everything
            logger.info(f"[SYNONYMS][datamuse] Raw: {raw_list}")
            logger.info(f"[SYNONYMS][datamuse] Filtered: {datamuse_syns_filtered}")
            if removed:
                logger.info(f"[SYNONYMS][datamuse] Invalidated synonyms for '{term}': {list(removed)}")
                
            for syn in datamuse_syns_filtered:
                resultList.append(Synonym(term=syn, source="datamuse", score=datamuse_syns[syn]))

        if not nltk_syns and not altervista_syns and not datamuse_syns:
            logger.warning(f"[SYNONYMS] No synonyms found from any source for term '{term}'")
        # Context re-scoring
        if context:
            temp_list = [s.term for s in resultList]
            logger.info(f"[SYNONYMS] got synonyms: {temp_list}")
            logger.info(f"[SYNONYMS] Re-evaluating the synonyms given the context '{context}'")
            if temp_list:  # 🔒 guard here
                all_scores = best_synonym_for_context(context, temp_list, model_repo_id, model_local_dir, return_all=True)
                score_map = {word: score for word, score in all_scores}
                for s in resultList:
                    if s.term in score_map:
                        s.score = score_map[s.term]
                resultList.sort(key=lambda x: x.score, reverse=True)
            else:
                logger.warning("[SYNONYMS] No synonyms available, skipping re-evaluation")


        if max:
            resultList = resultList[:max]
        
        logger.info(f"[SYNONYMS] Found best synonyms for {term}: {resultList}")

        if not resultList:
            logger.warning(f"[SYNONYMS] No synonyms found for term '{term}'")
        else:
            logger.info(f"[SYNONYMS] Found best synonyms for {term}: {resultList}")     
        
        return resultList
    
    except ValueError as e:
        logger.error(f"[SYNONYMS] Invalid input | error={str(e)}")
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                detail=str(e),
                error="INVALID_INPUT"
            ).model_dump()
        )

    except Exception as e:
        logger.error(
            f"[SYNONYMS] Internal error | error={str(e)}\n"
            + traceback.format_exc()
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                detail=str(e),
                error="INTERNAL_ERROR"
            ).model_dump()
        )

def get_nltk_synonyms(term, expiration_hours):
    cached = get_cached_synonyms(term, "nltk", expiration_hours)
    if cached:
        return cached

    synonyms = {}
    for syn in wordnet.synsets(term):
        for lemma in syn.lemmas():
            if lemma.name() != term:
                frequency = lemma.count()
                clean_name = lemma.name().replace("_", " ")
                synonyms[clean_name] = frequency

    synonyms = dict(sorted(synonyms.items(), key=lambda x: x[1], reverse=True))

    # ✅ Only cache if we actually have results
    if synonyms:
        set_cached_synonyms(term, "nltk", synonyms)

    return synonyms

def clean_altervista_term(term: str) -> str:
    # Remove anything in parentheses and strip whitespace
    return re.sub(r"\s*\(.*?\)", "", term).strip()

def get_altervista_synonyms(altervista_endpoint, term, api_key, expiration_hours, language):
    logger.info(f"[ALTERVISTA] Request for term: '{term}'")
    
    cached = get_cached_synonyms(term, "altervista", expiration_hours)
    if cached is not None:
        logger.info(f"[ALTERVISTA] Cache HIT for '{term}', returning: {cached}")
        return cached

    logger.info(f"[ALTERVISTA] Cache MISS for '{term}', calling API")

    url = f"{altervista_endpoint}word={term}&language={language}&key={api_key}&output=json"
    synonyms = {}
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        for item in data.get("response", []):
            words = item["list"]["synonyms"].split("|")
            logger.info(f"found altervista synonyms: {words}")
            for w in words:
                w_clean = clean_altervista_term(w)
                if w_clean and w_clean != term:
                    synonyms[w_clean] = synonyms.get(w_clean, 1)

        # ✅ Only cache if not empty
            if synonyms:
                logger.info(f"[ALTERVISTA] Caching {len(synonyms)} synonyms for '{term}': {synonyms}")
                set_cached_synonyms(term, "altervista", synonyms)
            else:
                logger.info(f"[ALTERVISTA] No synonyms found for '{term}', skipping cache")

        return synonyms
    except Exception as e:
        logger.error(f"[ALTERVISTA] error: {e}")
        return {}

def get_datamuse_synonyms(datamuse_endpoint, term, expiration_hours, max_results):
    cached = get_cached_synonyms(term, "datamuse", expiration_hours)
    if cached:
        logger.info(f"[DATAMUSE] Cache HIT for '{term}', returning: {cached}")
        return cached

    synonyms = {}
    url = f"{datamuse_endpoint}rel_syn={term}&max={max_results}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        for word in response.json():
            found = word['word']
            score = word.get('score', 0)
            synonyms[found] = score

        # ✅ Only cache if not empty
        if synonyms:
            logger.info(f"[DATAMUSE] Caching {len(synonyms)} synonyms for '{term}': {synonyms}")
            set_cached_synonyms(term, "datamuse", synonyms)
        else:
            logger.info(f"[DATAMUSE] No synonyms found for '{term}', skipping cache")
        return synonyms
    except Exception as e:
        logger.error(f"[DATAMUSE] error: {e}")
        return {}

@synonyms_router.get("/synonyms/cache",
    summary="Get cached synonyms",
    description="Returns all cached synonyms, optionally filtered by source."
)
def list_cache(source: Optional[Source] = Query(None, description="Filter by source (nltk, altervista, datamuse)")):
    session: Session = SessionLocal()
    try:
        query = session.query(SynonymCache)
        if source:
            query = query.filter(SynonymCache.source == source)
        rows = query.all()
        result: Dict[str, Any] = {}
        for row in rows:
            src = row.source
            if src not in result:
                result[src] = []
            result[src].append({
                "term": row.term,
                "synonyms": json.loads(row.synonyms),
                "timestamp": row.timestamp
            })
        return result
    finally:
        session.close()

@synonyms_router.delete("/synonyms/cache",
    summary="Delete cached synonyms",
    description="Deletes cached synonyms. You can delete all or filter by source."
)
def clear_cache(source: Optional[str] = Query(None, description="Filter by source to delete only that source's cache")):
    session: Session = SessionLocal()
    try:
        if source:
            deleted = session.query(SynonymCache).filter(SynonymCache.source == source).delete()
        else:
            deleted = session.query(SynonymCache).delete()
        session.commit()
        return {"deleted": deleted, "source": source or "all"}
    finally:
        session.close()

@synonyms_router.get("/synonyms/cache/stats",
    summary="Get cache hit/miss stats",
    description="Returns the number of cache hits and misses per source."
)
def cache_stats_endpoint():
    return get_cache_stats()

@synonyms_router.post("/synonyms/cache/invalidate/")
def add_invalid_synonym(term: str, source: str, synonym: str):
    session: Session = SessionLocal()
    try:
        inv = InvalidSynonym(term=term, source=source, synonym=synonym)
        session.merge(inv)  # upsert
        session.commit()
        return {"message": f"Synonym '{synonym}' invalidated for term '{term}' (source={source})"}
    finally:
        session.close()

@synonyms_router.delete("/synonyms/cache/invalidate/item/")
def remove_invalid_synonym(term: str, source: str, synonym: str):
    session: Session = SessionLocal()
    try:
        deleted = (
            session.query(InvalidSynonym)
            .filter_by(term=term, source=source, synonym=synonym)
            .delete()
        )
        session.commit()
        return {
            "message": f"Synonym '{synonym}' revalidated for term '{term}' (source={source})",
            "deleted": deleted,
        }
    finally:
        session.close()

@synonyms_router.get("/synonyms/cache/invalidate/{term}/{source}")
def list_invalid_synonyms(term: str, source: str):
    session: Session = SessionLocal()
    try:
        rows = session.query(InvalidSynonym).filter_by(term=term, source=source).all()
        return {"term": term, "source": source, "invalid_synonyms": [r.synonym for r in rows]}
    finally:
        session.close()

@synonyms_router.delete("/synonyms/cache/invalidate/")
def clear_invalid_synonyms():
    session: Session = SessionLocal()
    try:
        deleted = session.query(InvalidSynonym).delete()
        session.commit()
        return {"message": f"Deleted {deleted} invalid synonym entries"}
    finally:
        session.close()

# List ALL invalid synonyms (all terms and sources)
@synonyms_router.get("/synonyms/cache/invalidate/")
def list_all_invalid_synonyms():
    session: Session = SessionLocal()
    try:
        rows = session.query(InvalidSynonym).all()
        return {
            "invalid_synonyms": [
                {"term": r.term, "source": r.source, "synonym": r.synonym}
                for r in rows
            ]
        }
    finally:
        session.close()
