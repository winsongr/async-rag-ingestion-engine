from src.infra.db.postgres import check_database_connection
from src.infra.cache.redis import check_redis_connection
from src.infra.vector.qdrant import check_qdrant_connection
import logging

logger = logging.getLogger(__name__)


async def check_all_infrastructure() -> dict[str, bool | str]:
    """
    Checks all infrastructure components.
    Returns a dict mapping component name to status (True for OK, error string for failure).
    """
    status = {}

    # 1. Postgres
    try:
        await check_database_connection()
        status["postgres"] = True
    except Exception as e:
        logger.error(f"Health check failed (Postgres): {e}")
        status["postgres"] = str(e)

    # 2. Redis
    try:
        await check_redis_connection()
        status["redis"] = True
    except Exception as e:
        logger.error(f"Health check failed (Redis): {e}")
        status["redis"] = str(e)

    # 3. Qdrant
    try:
        await check_qdrant_connection()
        status["qdrant"] = True
    except Exception as e:
        logger.error(f"Health check failed (Qdrant): {e}")
        status["qdrant"] = str(e)

    return status
