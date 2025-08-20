import logging
from fastapi import APIRouter
from .translate import translate_router

logger = logging.getLogger(__name__)

v2_router = APIRouter(prefix="/v2")

v2_router.include_router(translate_router)