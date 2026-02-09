from functools import lru_cache
from src.services.embeddings import MockEmbeddingService
from src.services.llm import MockLLMService
from src.application.search.search import SearchService
from src.infra.vector.index import VectorIndexService
from fastapi import Depends
from fastapi import Request
from redis.asyncio import Redis
from qdrant_client import AsyncQdrantClient


async def get_redis_client(request: Request) -> Redis:
    """
    Get the Redis client from app state.
    Use this in routes instead of importing the global client directly.
    """
    return request.app.state.redis


async def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    """
    Get the Qdrant client from app state.
    Use this in routes instead of importing the global client directly.
    """
    return request.app.state.qdrant


# Moved from src/domains/search/dependencies.py


@lru_cache()
def get_embedding_service() -> MockEmbeddingService:
    """Singleton embedding service."""
    return MockEmbeddingService()


@lru_cache()
def get_llm_service() -> MockLLMService:
    """Singleton LLM service."""
    return MockLLMService()


def get_vector_service(
    qdrant: AsyncQdrantClient = Depends(get_qdrant_client),
) -> VectorIndexService:
    """Vector service with injected Qdrant client."""
    return VectorIndexService(qdrant)


def get_search_service(
    embedding_service: MockEmbeddingService = Depends(get_embedding_service),
    vector_service: VectorIndexService = Depends(get_vector_service),
    llm_service: MockLLMService = Depends(get_llm_service),
) -> SearchService:
    """Search service with all dependencies injected."""
    return SearchService(embedding_service, vector_service, llm_service)
