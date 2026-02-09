from fastapi import APIRouter
from src.api.health import router as health_router
from src.api.documents.router import router as documents_router
from src.api.search.router import router as search_router

router = APIRouter()
router.include_router(health_router)
router.include_router(documents_router)
router.include_router(search_router)
