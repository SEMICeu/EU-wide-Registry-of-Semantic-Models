import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

# Import your modules
from app.analyzer import AsyncSemanticRegistryAnalyzer
from app.api.v1.models import AnalysisResult, ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Semantic Registry Analysis API",
    description="""
    A FastAPI application for analyzing semantic registries and calculating LOVRank metrics.
    
    This API analyzes ontologies and calculates LOVRank metrics based on their reuse patterns
    and establishes dependency relationships between ontologies.
    """,
    version="1.0.0",
    contact={
        "name": "SEMIC",
        "email": "DIGIT-SEMIC-TEAM@ec.europa.eu",
    },
    license_info={
        "name": "CC-BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/deed.en",
    },
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            error_type="HTTPException"
        ).dict()
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle request validation errors"""
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail=str(exc),
            error_type="ValidationError"
        ).dict()
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions"""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="Internal server error",
            error_type="InternalError"
        ).dict()
    )

# Initialize analyzer
analyzer = AsyncSemanticRegistryAnalyzer()

@app.get("/", tags=["root"])
async def root():
    """Root endpoint providing basic API information."""
    return {
        "message": "Semantic Registry Analysis API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_check": "/health"
    }

@app.post("/analyze", 
          response_model=AnalysisResult,
          responses={
              200: {"description": "Analysis completed successfully"},
              500: {"model": ErrorResponse, "description": "Analysis failed"}
          })
async def analyze_registry():
    """
    Analyze the semantic registry and return results.
    
    This endpoint performs a complete analysis of the semantic registry,
    calculating LOVRank metrics and establishing dependencies between ontologies.
    Returns the complete analysis results including metrics for all ontologies.
    """
    try:
        logger.info("Starting semantic registry analysis...")
        
        # Generate a simple analysis ID for logging purposes
        import uuid
        analysis_id = str(uuid.uuid4())
        
        # Run the analysis
        result = await analyzer.run_analysis(analysis_id)
        
        logger.info(f"Analysis completed successfully. Processed {result.total_ontologies} ontologies in {result.execution_time:.2f} seconds")
        
        return result
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Semantic Registry Analysis API"
    }

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    logger.info("Starting Semantic Registry Analysis API...")
    
    # Verify config file exists (should be in same directory as analyzer.py)
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if not os.path.exists(config_path):
        logger.error(f"Config file not found at {config_path}")
        raise FileNotFoundError(f"Config file not found at {config_path}")
    
    logger.info("API started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Semantic Registry Analysis API...")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Set to False in production
        log_level="info"
    )