from fastapi import FastAPI, APIRouter
from app.api.v1.routers import v1_router
from app.api.v2.routers import v2_router
from app.api.v3.routers import v3_router
from contextlib import asynccontextmanager
from SPARQLWrapper import SPARQLWrapper, JSON
import yaml
import os
import logging

# Configure logging globally
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 App is starting up...")
    # Load config at startup
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        app.state.config = yaml.safe_load(f)
    
    endpoint = app.state.config["endpoint"]
    app.state.sparql = SPARQLWrapper(endpoint)
    app.state.sparql.setReturnFormat(JSON)
    yield  # serve requests

    # Optional cleanup
    logger.info("👋 App is shutting down...")

app = FastAPI( 
    title="PPDS REST API",
    description="REST API for extracting data from cellar.",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI path
    redoc_url="/redoc",     # ReDoc path
    openapi_url="/openapi.json",  # Raw OpenAPI JSON path
    lifespan=lifespan)

api_router= APIRouter(prefix="/api")
api_router.include_router(v1_router)
api_router.include_router(v2_router)
api_router.include_router(v3_router)
app.include_router(api_router)
