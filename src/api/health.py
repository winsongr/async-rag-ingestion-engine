from fastapi import APIRouter, Response, status
from src.infra.monitoring import check_all_infrastructure
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health/live")
async def health_live():
    """
    K8s liveness probe. Returns 200 if the app is running.
    Does NOT check upstream dependencies.
    """
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(response: Response):
    """
    K8s readiness probe. Checks connectivity to all upstream services.
    Returns 503 if any critical service is unavailable.
    """
    infra_status = await check_all_infrastructure()

    status_dict = {}
    all_healthy = True

    for comp, result in infra_status.items():
        if result is True:
            status_dict[comp] = "ok"
        else:
            status_dict[comp] = "error"
            all_healthy = False

    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return status_dict
