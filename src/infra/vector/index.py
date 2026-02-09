from uuid import UUID, uuid5, NAMESPACE_DNS
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models


class VectorIndexService:
    def __init__(self, client: AsyncQdrantClient):
        self.client = client
        self.collection_name = "documents"
        self.vector_size = 1536

    async def ensure_collection_exists(self):
        """Ensure the Qdrant collection exists."""
        collections = await self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)

        if not exists:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size, distance=models.Distance.COSINE
                ),
            )

    async def upsert_chunks(
        self, document_id: UUID, chunks: list[str], embeddings: list[list[float]]
    ):
        """Upsert chunks and embeddings into Qdrant."""
        if not chunks:
            return

        points = []
        for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
            # Generate a deterministic ID for idempotency: doc_id + chunk_index
            # We use uuid5 with a namespace
            chunk_id = str(uuid5(NAMESPACE_DNS, f"{document_id}_{i}"))

            payload = {
                "document_id": str(document_id),
                "chunk_index": i,
                "text": chunk,
            }

            points.append(
                models.PointStruct(id=chunk_id, vector=vector, payload=payload)
            )

        await self.client.upsert(collection_name=self.collection_name, points=points)

    async def search(self, query_vector: list[float], limit: int = 5):
        """Search for similar vectors."""
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
        )
        return result.points
