from fastapi import FastAPI, APIRouter
from app.api.v1.routers.routers import v1_router
from app.api.v2.routers.routers import v2_router
from app.api.v1.routers.synonyms.synonyms_cache import reset_cache_stats
from app.api.v1.mlmodels import list_opus_pairs
from contextlib import asynccontextmanager
import yaml
import os
import logging
import logging.config
import nltk

# 🔧 Force Uvicorn to use our logging config
LOG_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "log_config.yaml")
if os.path.exists(LOG_CONFIG_PATH):
    import logging.config
    import yaml
    with open(LOG_CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
        logging.config.dictConfig(config)

logger = logging.getLogger("app")  # ✅ Matches "app" logger in YAML

os.environ['HF_HUB_DISABLE_SSL_VERIFY'] = '1'

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 App is starting up...")
    # Load config at startup
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, "r") as f:
        app.state.config = yaml.safe_load(f)
    
    nltk.download('wordnet')

    reset_cache_stats()

    try:
        # Preload the translation pairs cache at startup
        list_opus_pairs()
        logger.info("Translation pairs cached at startup")
    except Exception as e:
        logger.error(f"Failed to preload translation pairs: {e}")

    yield  # serve requests

    # Optional cleanup
    logger.info("👋 App is shutting down...")

app = FastAPI(
    title="Enricher REST API",
    description="REST API for Registry enricher",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

api_router = APIRouter(prefix="/enricher-api")
api_router.include_router(v1_router)
api_router.include_router(v2_router)
app.include_router(api_router)
