from fastapi import APIRouter, Query, HTTPException, Request
import os
from datetime import datetime
from typing import List, Optional, Annotated
import logging

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v1.models import ErrorResponse, Synonym
from nltk.corpus import wordnet
import requests

logger = logging.getLogger(__name__)


v1_router = APIRouter(prefix="/v1")

@v1_router.get("/synonyms",
    response_model=List[Synonym],
    responses={
        200: {"description": "Successful response", "model": List[Synonym]},
        400: {"description": "Bad Request", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Get a list of synoyms for a term",  
    description="This endpoint returns a list of procedures for indicator1, filtered if needed, retrieved from Cellar. V2 provides a different response.",
    response_description="The response is a JSON object including list of procedures ")
async def sparql_query(
    request: Request,
    term: str = Query(default=...),
    sources : str = Query(default=None)
    ):

    try:
        config = request.app.state.config
        # Process and print results
        datamuse_endpoint = config['datamuse_endpoint']

        resultList =[]
        if(sources == "nltk" or sources is None):
            synonyms = get_nltk_synonyms(term)
            for syn in synonyms:
                synonym = Synonym(
                    term=syn,
                    source="nltk"
                )
                resultList.append(synonym)
        # Check each item in the set
        if(sources == "datamuse" or ((sources is None) and len(synonyms) == 0)):
            synonyms = get_datamuse_synonyms(datamuse_endpoint, term)
            for syn in synonyms:
                synonym = Synonym(
                    term=syn,
                    source="datamuse"
                )
                resultList.append(synonym) 
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
    synonyms = set()
    for syn in wordnet.synsets(term):
        for lemma in syn.lemmas():
            if lemma.name() != term:
                logger.info("adding " + lemma.name())
                synonyms.add(lemma.name())
    return synonyms

def get_datamuse_synonyms(datamuse_endpoint, term):
    synonyms = set()
    response = requests.get(datamuse_endpoint+term)
    for word in response.json():
        found = word['word']
        logger.info("adding " + found)
        synonyms.add(found )
    return synonyms