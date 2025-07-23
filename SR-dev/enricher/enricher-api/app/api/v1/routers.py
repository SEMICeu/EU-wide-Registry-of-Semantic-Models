from fastapi import APIRouter, Query, HTTPException, Request
import os
from datetime import datetime
from typing import List, Optional, Annotated
import logging

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v1.models import ErrorResponse, Synonym, TranslationItem, TranslationResponse, DetectedLanguage, load_model, get_fasttext_model
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
    description="This endpoint returns a list of synoyms for a term, filtered if needed by source",
    response_description="The response is a JSON object including list of synonyms with their source ")
async def synonyms(
    request: Request,
    term: str = Query(default=...),
    sources : str = Query(default=None),
    max: int = Query(default=None, min=1)
    ):

    try:
        config = request.app.state.config
        # Process and print results
        datamuse_endpoint = config['datamuse_endpoint']

        resultList =[]
        if(sources == "nltk" or sources is None):
            synonyms = get_nltk_synonyms(term)
            for syn,score in synonyms.items():
                synonym = Synonym(
                    term=syn,
                    source="nltk",
                    score=score
                )
                resultList.append(synonym)
        # Check each item in the set
        if(sources == "datamuse" or ((sources is None) and len(synonyms) == 0)):
            synonyms = get_datamuse_synonyms(datamuse_endpoint, term)
            for syn,score in synonyms.items():
                synonym = Synonym(
                    term=syn,
                    source="datamuse",
                    score=score
                )
                resultList.append(synonym)
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
    return synonyms

def get_datamuse_synonyms(datamuse_endpoint, term):
    synonyms = {}
    response = requests.get(datamuse_endpoint+term)
    for word in response.json():
        found = word['word']
        score = word.get('score', 0)
        logger.info(f"adding {found} with score {score}")
        synonyms[found] = score
    return synonyms

@v1_router.get("/translate",
    response_model=List[TranslationResponse],
    responses={
        200: {"description": "Successful response", "model": List[TranslationResponse]},
        400: {"description": "Bad Request", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Get a list of translations for a term",  
    description="This endpoint returns a list of translations for a term",
    response_description="The response is a JSON object including list of translations with their target language.")
async def translates(
    request: Request,
    term: str = Query(default=..., min_length=1, description="the text to be translated"),
    source: Optional[str] = Query(default=None, description="Optional source language code; auto-detect if omitted"),
    target: List[str] = Query(default=..., description="one or more languages")
    ):

    try:
        lang_code, confidence = detect_language(term)
        detected = DetectedLanguage(
            language=lang_code,
            score=confidence
        )
        logger.info("detected " + lang_code)
        if source is None:
            source = lang_code
        resultList =[]
        for tgt in target:
            tokenizer, model = load_model(source, tgt)
            inputs = tokenizer(term, return_tensors="pt", padding=True)
            translated = model.generate(**inputs)
            output = tokenizer.decode(translated[0], skip_special_tokens=True)
            translation = TranslationItem(
                        term=output,
                        lang=tgt
            )
            resultList.append(translation)
        
        response = TranslationResponse(
            detectedLanguage=detected,
            translations=resultList
        )

        return [response]
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
    
def detect_language(text: str):
    model = get_fasttext_model()
    predictions = model.predict(text)
    lang_code = predictions[0][0].replace("__label__", "")
    confidence = predictions[1][0]
    return lang_code, confidence