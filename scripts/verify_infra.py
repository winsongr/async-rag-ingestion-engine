import asyncio
import logging
import sys
from src.infra.monitoring import check_all_infrastructure
from src.infra.db.postgres import engine
from src.infra.cache.redis import close_redis_connection
from src.infra.vector.qdrant import close_qdrant_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("verify_infra")


async def verify():
    logger.info("Starting infrastructure verification...")

    infra_status = await check_all_infrastructure()
    errors = []

    for comp, result in infra_status.items():
        if result is True:
            logger.info(f"✅ {comp.capitalize()} connection: OK")
        else:
            logger.error(f"❌ {comp.capitalize()} connection: FAILED ({result})")
            errors.append(comp)

    # Cleanup
    await engine.dispose()
    await close_redis_connection()
    await close_qdrant_connection()

    if errors:
        logger.error(f"Verification FAILED for: {', '.join(errors)}")
        sys.exit(1)

    logger.info("All systems operational. 🚀")


if __name__ == "__main__":
    try:
        asyncio.run(verify())
    except KeyboardInterrupt:
        pass
