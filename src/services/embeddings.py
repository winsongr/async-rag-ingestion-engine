"""
Mock embedding service for testing.

Mocked on purpose so we can test:
- The full pipeline flow (chunking → embedding → indexing)
- Idempotency with deterministic IDs
- Error handling

Swap in OpenAI for production.
"""

from abc import ABC, abstractmethod


class EmbeddingService(ABC):
    """Abstract interface for embedding services."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        pass


class MockEmbeddingService(EmbeddingService):
    """
    Returns fake 1536-dim vectors.

    Mock on purpose - real embeddings add cost and API rate limits
    that get in the way when testing the pipeline.
    """

    def __init__(self, use_openai: bool = False):
        self.use_openai = use_openai
        # In a real scenario, we'd initialize OpenAI client here

    def embed(self, text: str) -> list[float]:
        """
        Embed a single string.
        Returns a 1536-dimensional vector (simulating OpenAI text-embedding-3-small).
        """
        if self.use_openai:
            # TODO: Implement actual OpenAI call
            # from openai import OpenAI
            # client = OpenAI()
            # return client.embeddings.create(input=text, model="text-embedding-3-small").data[0].embedding
            pass

        # Returns a deterministic-ish mock vector based on text length hashing to keep things stable
        # or just random for pure flow testing.
        import random

        random.seed(len(text))
        return [random.random() for _ in range(1536)]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings."""
        return [self.embed(t) for t in texts]
