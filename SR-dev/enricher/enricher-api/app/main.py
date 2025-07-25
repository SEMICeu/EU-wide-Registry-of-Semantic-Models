from fastapi import FastAPI, APIRouter
from app.api.v1.routers.routers import v1_router
from contextlib import asynccontextmanager
import yaml
import os
import logging
import nltk

os.environ['HF_HUB_DISABLE_SSL_VERIFY'] = '1'
# Configure logging globally
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True
)
logger = logging.getLogger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 App is starting up...")
    # Load config at startup
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        app.state.config = yaml.safe_load(f)
    
    nltk.download('wordnet')
    yield  # serve requests

    # Optional cleanup
    logger.info("👋 App is shutting down...")

app = FastAPI( 
    title="Enricher REST API",
    description="REST API for Registry enricher",
    version="1.0.0",
    docs_url="/docs",       # Swagger UI path
    redoc_url="/redoc",     # ReDoc path
    openapi_url="/openapi.json",  # Raw OpenAPI JSON path
    lifespan=lifespan)


api_router= APIRouter(prefix="/api")
api_router.include_router(v1_router)
app.include_router(api_router)
