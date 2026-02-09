import redis.asyncio as redis
from src.core.config.settings import settings
import logging

logger = logging.getLogger(__name__)

redis_client = redis.from_url(
    settings.REDIS_URI,
    encoding="utf-8",
    decode_responses=True,
    socket_timeout=5,
    retry_on_timeout=True,
    health_check_interval=30,
)


async def check_redis_connection():
    try:
        await redis_client.ping()
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise e


async def close_redis_connection():
    try:
        await redis_client.aclose()
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")
