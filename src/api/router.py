from src.api.health import router as health_router
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

router.include_router(health_router)
