from fastapi import APIRouter, Query, HTTPException, Request
import os
from typing import List, Optional
import logging
import traceback

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.api.v1.models import ErrorResponse, Theme
from app.api.v1.schemas.classification import Classification
from app.api.v1.mlmodels import rank_theme_codes_by_context

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
    classification: Classification = Query(..., description="the classification list"),
    max: int = Query(default=None, min=1, description="The maximum number of results.")
    ):

    try:
        config = request.app.state.config_classify
        # Process and print results
        listofterms = config[classification]
        model_repo_id = config["model"]["repo_id"]
        model_local_dir = config["model"]["local_dir"]
        logger.info(f"[CLASSIFY] Loaded {len(listofterms)} terms for classification")
        logger.info(f"[CLASSIFY] model_repo_id: {model_repo_id}")
        logger.info(f"[CLASSIFY] model_local_dir: {model_local_dir}")

        resultList =[]
        logger.info("[CLASSIFY] Context:" + context)
        #for code, data in listofterms.items():
        #    logger.info(f"{data['label']}. {data['definition']}")

        all_scores = rank_theme_codes_by_context(context, listofterms, model_repo_id, model_local_dir, return_all=True)
        for code,score in all_scores:
                theme = Theme(
                    term=code,
                    score=score
                )
                resultList.append(theme)

        if max is not None:
            resultList = resultList[:max] 
        
        logger.info(f"[CLASSIFY] Success | results={resultList}")
        return resultList
    except ValueError as e:
        logger.error(f"[CLASSIFY] Invalid input | error={str(e)}")
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(detail=str(e), error="INVALID_INPUT").model_dump()
        )
    except Exception as e:
        logger.error(
            f"[CLASSIFY] Internal error | error={str(e)}\n"
            + traceback.format_exc()
        )
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(detail=str(e), error="INTERNAL_ERROR").model_dump()
        )
