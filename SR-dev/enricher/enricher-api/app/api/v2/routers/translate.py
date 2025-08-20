from fastapi import APIRouter, Query, HTTPException, Request
import os
from typing import List, Optional, Tuple
import logging
import re

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v2.models import ErrorResponse, TranslationItem, TranslationResponse, DetectedLanguage 
from app.api.v2.mlmodels import load_model_translate, get_fasttext_model, list_pairs, list_opus_pairs
from app.api.v2.schemas.language import Language

logger = logging.getLogger(__name__)

translate_router = APIRouter()

def detect_language(text: str):
    model = get_fasttext_model()
    predictions = model.predict(text)
    lang_code = predictions[0][0].replace("__label__", "")
    confidence = predictions[1][0]
    return lang_code, confidence

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
async def translates2(
    request: Request,
    term: str = Query(default=..., min_length=1, description="the text to be translated"),
    source: Optional[Language] = Query(default=None, description="Optional source language code; auto-detect if omitted"),
    target: List[Language] = Query(default=..., description="one or more languages")
    ):

    def split_into_sentences(text: str) -> list[str]:
        """
        Split text into sentences based on punctuation.
        Example:
          "Hello world. This is a test!" → ["Hello world.", "This is a test!"]
        """
        parts = re.split(r'(?<=[.!?])\s+', text)
        return [p.strip() for p in parts if p.strip()]

    def split_by_length(text: str, max_chars: int = 400) -> list[str]:
        """
        Fallback: split long text into smaller chunks by character length.
        """
        return [text[i:i+max_chars] for i in range(0, len(text), max_chars)]

    async def translate_text(term: str, source: str, target_value: str) -> str:
        """Translate text by sentence-splitting, fallback to length-based chunking if needed."""
        tokenizer, model = load_model_translate(source, target_value)

        sentences = split_into_sentences(term)
        outputs = []

        logger.info(f"Splitting into {len(sentences)} sentences for {source}->{target_value}")

        for i, sent in enumerate(sentences, 1):
            try:
                inputs = tokenizer(sent, return_tensors="pt", padding=True, truncation=True)
                translated = model.generate(**inputs, max_length=512)
                out = tokenizer.decode(translated[0], skip_special_tokens=True)
                logger.debug(f"[{i}/{len(sentences)}] {source}->{target_value}: {sent[:50]} → {out[:50]}")
                outputs.append(out)

            except Exception as e:
                logger.warning(f"Sentence too long or failed ({source}->{target_value}): {sent[:50]}... Fallback to chunking. Error: {e}")

                # fallback: split sentence into length-based chunks
                chunks = split_by_length(sent, max_chars=400)
                for j, chunk in enumerate(chunks, 1):
                    inputs = tokenizer(chunk, return_tensors="pt", padding=True, truncation=True)
                    translated = model.generate(**inputs, max_length=512)
                    out = tokenizer.decode(translated[0], skip_special_tokens=True)
                    logger.debug(f"   Fallback [{j}/{len(chunks)}] {source}->{target_value}: {chunk[:50]} → {out[:50]}")
                    outputs.append(out)

        return " ".join(outputs)

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

        resultList = []
        sorted_pairs = list_opus_pairs()
        found = 0

        for tgt in target:
            target_value = tgt.value
            if (source, target_value) in sorted_pairs:
                logger.info(f"valid pair: {source}-{target_value}")
                found += 1

                output = await translate_text(term, source, target_value)

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