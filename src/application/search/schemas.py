from pydantic import BaseModel


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class SearchResult(BaseModel):
    text: str
    score: float
    document_id: str
    chunk_index: int


class SearchResponse(BaseModel):
    answer: str
    results: list[SearchResult]
