from fastapi import APIRouter, Depends
from src.application.search.schemas import SearchRequest, SearchResponse
from src.application.search.search import SearchService
from src.infra.lifecycle.dependencies import get_search_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    search_service: SearchService = Depends(get_search_service),
):
    """
    Search for relevant documents.
    """
    answer, results = await search_service.search(request.query, request.limit)
    return SearchResponse(answer=answer, results=results)
