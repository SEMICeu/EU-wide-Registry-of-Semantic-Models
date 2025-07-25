from fastapi import APIRouter, Query, HTTPException, Request
import os
from typing import List, Optional
import logging

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v1.models import ErrorResponse, Theme
from app.api.v1.mlmodels import rank_theme_codes_by_context
from nltk.corpus import wordnet
import requests

logger = logging.getLogger(__name__)

classify_router = APIRouter()

@classify_router.get("/classify",
    response_model=List[Theme],
    responses={
        200: {"description": "Successful response", "model": List[Theme]},
        400: {"description": "Bad Request", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Rank the data themes for a text",  
    description="This endpoint returns a list of data themes for a text",
    response_description="The response is a JSON object including list of data themes ranked by score")
async def classify(
    request: Request,
    context: str = Query(default=..., description="A sentence that can be used to give a context and reorder the results."),
    max: int = Query(default=None, min=1, description="The maximum number of results.")
    ):

    try:
        config = request.app.state.config
        # Process and print results
        data_themes = config['themes']

        resultList =[]

        all_scores = rank_theme_codes_by_context(context, data_themes, return_all=True)
        for code,score in all_scores:
                theme = Theme(
                    term=code,
                    score=score
                )
                resultList.append(theme)

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
