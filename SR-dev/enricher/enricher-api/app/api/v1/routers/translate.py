from fastapi import APIRouter, Query, HTTPException, Request
import os
from typing import List, Optional, Tuple
import logging

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v1.models import ErrorResponse, TranslationItem, TranslationResponse, DetectedLanguage 
from app.api.v1.mlmodels import load_model_translate, get_fasttext_model, list_pairs, list_opus_pairs
from app.schemas.language import Language

logger = logging.getLogger(__name__)

translate_router = APIRouter()

@translate_router.get("/translate",
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
    source: Optional[Language] = Query(default=None, description="Optional source language code; auto-detect if omitted"),
    target: List[Language] = Query(default=..., description="one or more languages")
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
        else:
            source = source.value
        resultList =[]

        sorted_pairs = list_opus_pairs()
        found = 0
        for tgt in target:
            target_value = tgt.value
            if (source,target_value) in sorted_pairs:
                logger.info("valid pair:" + source + "-" + target_value)
                found +=1

                tokenizer, model = load_model_translate(source, target_value)
                inputs = tokenizer(term, return_tensors="pt", padding=True)
                translated = model.generate(**inputs)
                output = tokenizer.decode(translated[0], skip_special_tokens=True)
                translation = TranslationItem(
                            term=output,
                            lang=target_value
                )
                resultList.append(translation)
        logger.info("found " + str(found))

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


@translate_router.get("/translate/pairs", response_model=List[Tuple[str, str]])
def get_translation_pairs():
    return list_opus_pairs()

@translate_router.post("/translate/pairs/refresh")
def refresh_translation_pairs():
    list_opus_pairs.cache_clear()   # clear cache
    updated = list_opus_pairs()     # fetch again
    return {
        "refreshed": True,
        "count": len(updated),
        "sample": list(updated)[:5]  # show just a few pairs as preview
    }
