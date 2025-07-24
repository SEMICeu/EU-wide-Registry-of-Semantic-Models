from fastapi import APIRouter, Query, HTTPException, Request
import os
from datetime import datetime
from typing import List, Optional, Annotated
import logging

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v1.models import ErrorResponse, Synonym, TranslationItem, TranslationResponse, DetectedLanguage 
from app.api.v1.mlmodels import load_model, get_fasttext_model, best_synonym_for_context
from app.schemas.source import Source
from nltk.corpus import wordnet
import requests

logger = logging.getLogger(__name__)

synonyms_router = APIRouter()

@synonyms_router.get("/synonyms",
    response_model=List[Synonym],
    responses={
        200: {"description": "Successful response", "model": List[Synonym]},
        400: {"description": "Bad Request", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Get a list of synoyms for a term",  
    description="This endpoint returns a list of synoyms for a term, filtered if needed by source",
    response_description="The response is a JSON object including list of synonyms with their source ")
async def synonyms(
    request: Request,
    term: str = Query(default=...),
    sources : Optional[Source] = Query(None),
    context: str = Query(default=None),
    max: int = Query(default=None, min=1)
    ):

    try:
        config = request.app.state.config
        # Process and print results
        datamuse_endpoint = config['datamuse_endpoint']

        resultList =[]
        if(sources == "nltk" or sources is None or sources =="all"):
            synonyms = get_nltk_synonyms(term)
            for syn,score in synonyms.items():
                synonym = Synonym(
                    term=syn,
                    source="nltk",
                    score=score
                )
                resultList.append(synonym)
        # Check each item in the set
        if(sources == "datamuse" or ((sources is None) and len(synonyms) == 0)) or sources=="all":
            synonyms = get_datamuse_synonyms(datamuse_endpoint, term)
            for syn,score in synonyms.items():
                synonym = Synonym(
                    term=syn,
                    source="datamuse",
                    score=score
                )
                resultList.append(synonym)

        if context is not None:
            temp_list = []
            for synonym in resultList:
                temp_list.append(synonym.term)
            all_scores = best_synonym_for_context(context, temp_list, return_all=True)
            for synonym in resultList:
                logger.info(f"{synonym.term}: {synonym.score}")
            logger.info("***new scores***")
            for word, score in all_scores:
                logger.info(f"{word}: {score:.4f}")
            for word, score in all_scores:
                for synonym in resultList:
                    if synonym.term == word:
                        synonym.score = score
            resultList.sort(key=lambda x: x.score, reverse=True)

        if max is not None:
            resultList = resultList[:max] 
        return resultList
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

def get_nltk_synonyms(term):
    synonyms = {}
    for syn in wordnet.synsets(term):
        for lemma in syn.lemmas():
            if lemma.name() != term:
                frequency = lemma.count()  # Get the frequency count
                logger.info(f"adding {lemma.name()} with frequency {frequency}")
                synonyms[lemma.name()] = frequency  # Set score to 1
    return dict(sorted(synonyms.items(), key=lambda x: x[1], reverse=True))

def get_datamuse_synonyms(datamuse_endpoint, term):
    synonyms = {}
    response = requests.get(datamuse_endpoint+term)
    for word in response.json():
        found = word['word']
        score = word.get('score', 0)
        logger.info(f"adding {found} with score {score}")
        synonyms[found] = score
    return synonyms
