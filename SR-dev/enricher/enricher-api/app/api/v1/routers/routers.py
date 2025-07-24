import logging
from fastapi import APIRouter
from .synonyms import synonyms_router
from .translate import translate_router
from .classifier import classify_router

logger = logging.getLogger(__name__)

v1_router = APIRouter(prefix="/v1")

v1_router.include_router(synonyms_router)
v1_router.include_router(translate_router)
v1_router.include_router(classify_router)