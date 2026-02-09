from contextlib import asynccontextmanager
from fastapi import FastAPI
from src.infra.db.postgres import engine
from src.infra.cache.redis import redis_client, close_redis_connection
from src.infra.vector.qdrant import qdrant_client, close_qdrant_connection
from src.infra.monitoring import check_all_infrastructure
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup checking
    logger.info("Starting up AI Data Platform...")

    # Store clients in app state
    app.state.redis = redis_client
    app.state.qdrant = qdrant_client

    # Unified Infrastructure Check
    logger.info("Verifying infrastructure connectivity...")
    infra_status = await check_all_infrastructure()

    failed_components = [k for k, v in infra_status.items() if v is not True]

    if failed_components:
        error_msg = f"Startup failed. Infrastructure unavailable: {failed_components}"
        logger.error(error_msg)
        # Log details
        for comp, err in infra_status.items():
            if err is not True:
                logger.error(f"{comp}: {err}")
        raise RuntimeError(error_msg)

    logger.info("All infrastructure operational.")

    yield

    # Shutdown cleanup
    logger.info("Shutting down AI Data Platform...")

    logger.info("Closing Database engine...")
    await engine.dispose()

    logger.info("Closing Redis connection...")
    await close_redis_connection()

    logger.info("Closing Qdrant connection...")
    await close_qdrant_connection()

    logger.info("Shutdown complete.")
