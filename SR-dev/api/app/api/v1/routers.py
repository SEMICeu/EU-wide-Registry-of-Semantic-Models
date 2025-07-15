from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from typing import Dict
import uuid
from datetime import datetime

from .models import (
    AnalysisRequest, AnalysisStartResponse, AnalysisStatus, AnalysisResult,
    AnalysisListResponse, AnalysisListItem, DeleteResponse, ErrorResponse,
    AnalysisStatusEnum
)
from app.analyzer import AsyncSemanticRegistryAnalyzer

# Create router
router = APIRouter(prefix="/api/v1", tags=["analysis"])

# In-memory storage for analysis results (in production, use a database)
analysis_results: Dict[str, AnalysisStatus] = {}

# Global analyzer instance
analyzer = AsyncSemanticRegistryAnalyzer()

async def get_analyzer():
    """Dependency to get the analyzer instance"""
    return analyzer

@router.post("/analyze", 
             response_model=AnalysisStartResponse,
             responses={
                 200: {"description": "Analysis started successfully"},
                 500: {"model": ErrorResponse, "description": "Internal server error"}
             })
async def start_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    analyzer: AsyncSemanticRegistryAnalyzer = Depends(get_analyzer)
):
    """
    Start a new semantic registry analysis.
    
    This endpoint initiates a background analysis of the semantic registry,
    calculating LOVRank metrics and establishing dependencies between ontologies.
    """
    analysis_id = str(uuid.uuid4())
    
    # Initialize analysis status
    analysis_results[analysis_id] = AnalysisStatus(
        analysis_id=analysis_id,
        status=AnalysisStatusEnum.STARTING,
        progress="Initializing...",
        created_at=datetime.now()
    )
    
    # Start background task
    background_tasks.add_task(run_analysis_task, analysis_id, analyzer)
    
    return AnalysisStartResponse(
        analysis_id=analysis_id,
        message="Analysis started successfully",
        status=AnalysisStatusEnum.STARTING
    )

async def run_analysis_task(analysis_id: str, analyzer: AsyncSemanticRegistryAnalyzer):
    """Background task to run the analysis."""
    try:
        # Update status to running
        analysis_results[analysis_id].status = AnalysisStatusEnum.RUNNING
        
        # Run the analysis
        result = await analyzer.run_analysis(analysis_id)
        
        # Update with completion time
        result.completed_at = datetime.now()
        
        # Update status
        analysis_results[analysis_id].status = AnalysisStatusEnum.COMPLETED
        analysis_results[analysis_id].result = result
        analysis_results[analysis_id].progress = "Analysis completed successfully"
        
    except Exception as e:
        analysis_results[analysis_id].status = AnalysisStatusEnum.FAILED
        analysis_results[analysis_id].error = str(e)
        analysis_results[analysis_id].progress = f"Analysis failed: {str(e)}"

@router.get("/analysis/{analysis_id}", 
            response_model=AnalysisStatus,
            responses={
                200: {"description": "Analysis status retrieved successfully"},
                404: {"model": ErrorResponse, "description": "Analysis not found"}
            })
async def get_analysis_status(analysis_id: str):
    """
    Get the current status of an analysis.
    
    Returns the current status, progress information, and results if completed.
    """
    if analysis_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return analysis_results[analysis_id]

@router.get("/analysis/{analysis_id}/result", 
            response_model=AnalysisResult,
            responses={
                200: {"description": "Analysis result retrieved successfully"},
                404: {"model": ErrorResponse, "description": "Analysis not found"},
                400: {"model": ErrorResponse, "description": "Analysis not completed"}
            })
async def get_analysis_result(analysis_id: str):
    """
    Get the result of a completed analysis.
    
    Only returns results for analyses that have completed successfully.
    """
    if analysis_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    status = analysis_results[analysis_id]
    if status.status != AnalysisStatusEnum.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Analysis is {status.status.value}. Results only available for completed analyses."
        )
    
    return status.result

@router.get("/analyses", 
            response_model=AnalysisListResponse,
            responses={
                200: {"description": "Analysis list retrieved successfully"}
            })
async def list_analyses():
    """
    List all analyses with their current status.
    
    Returns a summary of all analyses, including their status and basic information.
    """
    analyses = []
    for analysis_id, status in analysis_results.items():
        execution_time = None
        if status.result:
            execution_time = status.result.execution_time
            
        analyses.append(AnalysisListItem(
            analysis_id=analysis_id,
            status=status.status,
            progress=status.progress,
            created_at=status.created_at,
            execution_time=execution_time
        ))
    
    # Sort by creation time, newest first
    analyses.sort(key=lambda x: x.created_at, reverse=True)
    
    return AnalysisListResponse(
        analyses=analyses,
        total=len(analyses)
    )

@router.delete("/analysis/{analysis_id}", 
               response_model=DeleteResponse,
               responses={
                   200: {"description": "Analysis deleted successfully"},
                   404: {"model": ErrorResponse, "description": "Analysis not found"}
               })
async def delete_analysis(analysis_id: str):
    """
    Delete an analysis and its results.
    
    Removes the analysis from memory. Note: This does not delete log files.
    """
    if analysis_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    del analysis_results[analysis_id]
    return DeleteResponse(
        message="Analysis deleted successfully",
        analysis_id=analysis_id
    )

@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns basic health information about the API.
    """
    return {
        "status": "healthy",
        "service": "Semantic Registry Analysis API",
        "active_analyses": len([s for s in analysis_results.values() if s.status == AnalysisStatusEnum.RUNNING]),
        "total_analyses": len(analysis_results)
    }