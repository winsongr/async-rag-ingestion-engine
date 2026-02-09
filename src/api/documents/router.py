from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from src.infra.db.dependencies import get_db_session
from src.infra.lifecycle.dependencies import get_redis_client
from src.domains.documents.schemas import DocumentCreateRequest, DocumentResponse
from src.application.documents.ingest import IngestService, QueueFullError
from src.application.documents.upload import UploadService
from src.core.errors import AppError, DomainError

router = APIRouter(prefix="/documents", tags=["documents"])


def get_ingest_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> IngestService:
    return IngestService(session, redis)


def get_upload_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis_client)],
) -> UploadService:
    return UploadService(session, redis)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_document(
    request: DocumentCreateRequest,
    service: Annotated[IngestService, Depends(get_ingest_service)],
):
    """
    Ingest a new document.
    """
    try:
        doc = await service.ingest(request)
        return doc
    except QueueFullError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e)
        )
    except (AppError, DomainError) as e:
        # We could rely on global handler, but mapping to status codes here is nice API layer responsibility
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{document_id}/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    document_id: str,
    service: Annotated[UploadService, Depends(get_upload_service)],
    file: UploadFile = File(...),
):
    """
    Upload a file for a document.
    """
    try:
        # Validate UUID format at API boundary
        try:
            doc_uuid = UUID(document_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid UUID")

        doc = await service.upload(doc_uuid, file)
        return doc
    except DomainError as e:
        # Map specific domain errors to HTTP status
        # In a real app, maybe use a middleware or exception handler registry
        # But here explicit is fine.
        from src.domains.documents.errors import DocumentNotFound, ProcessingConflict

        if isinstance(e, DocumentNotFound):
            raise HTTPException(status_code=404, detail=str(e))
        if isinstance(e, ProcessingConflict):
            raise HTTPException(status_code=409, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except AppError as e:
        raise HTTPException(status_code=500, detail=str(e))
