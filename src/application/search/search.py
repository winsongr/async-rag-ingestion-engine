from src.services.embeddings import EmbeddingService
from src.infra.vector.index import VectorIndexService
from src.services.llm import LLMService
from src.application.search.schemas import SearchResult


class SearchService:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_index_service: VectorIndexService,
        llm_service: LLMService,
    ):
        self.embedding_service = embedding_service
        self.vector_index_service = vector_index_service
        self.llm_service = llm_service

    async def search(
        self, query: str, limit: int = 5
    ) -> tuple[str, list[SearchResult]]:
        # 1. Embed the query
        query_vector = self.embedding_service.embed(query)

        # 2. Search Qdrant
        points = await self.vector_index_service.search(
            query_vector=query_vector, limit=limit
        )

        # 3. Map to SearchResult
        results = []
        contexts = []
        for point in points:
            text = point.payload.get("text", "")
            contexts.append(text)
            results.append(
                SearchResult(
                    text=text,
                    score=point.score,
                    document_id=point.payload.get("document_id", ""),
                    chunk_index=point.payload.get("chunk_index", -1),
                )
            )

        # 4. Generate Answer
        answer = self.llm_service.generate_answer(query, contexts)

        return answer, results
