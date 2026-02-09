from qdrant_client import AsyncQdrantClient
from src.core.config.settings import settings
import logging

logger = logging.getLogger(__name__)

qdrant_client = AsyncQdrantClient(
    url=settings.QDRANT_URI,
    api_key=settings.QDRANT_API_KEY,
    timeout=10,
)


async def check_qdrant_connection():
    try:
        await qdrant_client.get_collections()
    except Exception as e:
        logger.error(f"Qdrant connection failed: {e}")
        raise e


async def close_qdrant_connection():
    try:
        await qdrant_client.close()
    except Exception as e:
        logger.error(f"Error closing Qdrant connection: {e}")
