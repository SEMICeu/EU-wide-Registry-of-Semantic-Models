from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from app.ranking_logic import run_ranking_process
from app.api.v1.models import RankingResponse, ErrorResponse
import logging

logger = logging.getLogger(__name__)

v1_router = APIRouter(prefix="/v1")

@v1_router.post(
    "/calculate-ranking",
    response_model=RankingResponse,
    responses={
        202: {"description": "Ranking process started"},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Start the semantic model ranking process",
    description="This endpoint triggers a background task to fetch semantic models, calculate their reuse rank, and update the triplestore.",
    response_description="Returns a confirmation that the process has started."
)
async def calculate_ranking(request: Request, background_tasks: BackgroundTasks):
    """
    Triggers the model ranking process as a background task.
    """
    try:
        logger.info("Received request to calculate model rankings.")
        config = request.app.state.config
        
        sparql_query_endpoint = config["sparql"]["sparql_query_endpoint"]
        sparql_update_endpoint = config["sparql"]["sparql_update_endpoint"]
        bypass_ssl = config["sparql"]["bypass_ssl"]
        
        queries = {
            "sparql_query": config["sparql_query"],
            "lovrank_update_query": config["lovrank_update_query"],
            "requires_update_query": config["requires_update_query"]
        }

        background_tasks.add_task(
            run_ranking_process, 
            sparql_query_endpoint, 
            sparql_update_endpoint, 
            bypass_ssl, 
            queries
        )

        return RankingResponse(
            status="accepted",
            models_processed=0,
            unique_models_ranked=0
        )
    except Exception as e:
        logger.error(f"Failed to start ranking process: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(detail=str(e), error="INTERNAL_ERROR").model_dump()
        )