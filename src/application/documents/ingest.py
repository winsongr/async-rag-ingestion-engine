import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from redis.asyncio import Redis

from src.domains.documents.repository import DocumentRepository
from src.infra.queue.document_queue import DocumentQueue
from src.core.config.settings import settings
from src.core.errors import AppError, InfraError
from src.domains.documents.schemas import DocumentCreateRequest
from src.domains.documents.models import DocumentStatus


logger = logging.getLogger("ingest_service")


class QueueFullError(AppError):
    def __init__(self, current, limit):
        super().__init__(f"Queue is full ({current}/{limit}). Please retry later.")


class IngestService:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.queue = DocumentQueue(redis)
        self.repo = DocumentRepository(session)

    async def ingest(self, request: DocumentCreateRequest):
        """
        Ingest a new document.

        Flow:
        1. Backpressure check
        2. Commit document to DB (with UNIQUE constraint handling)
        3. Enqueue AFTER commit (proper ordering)
        4. If enqueue fails -> mark FAILED in new transaction
        """
        # 1. Backpressure Check
        queue_length = await self.queue.get_queue_length()
        if queue_length >= settings.QUEUE_MAX_LENGTH:
            raise QueueFullError(queue_length, settings.QUEUE_MAX_LENGTH)

        # 2. Create document in DB (or return existing)
        doc = None
        try:
            async with self.session.begin():
                # Try to create - UNIQUE constraint will catch duplicates
                doc = await self.repo.create_document(request.source)
        except IntegrityError:
            # Duplicate source - fetch existing document (idempotent)
            await self.session.rollback()
            doc = await self.repo.get_document_by_source(request.source)
            if doc:
                logger.info(f"Returning existing document for source: {request.source}")
                return doc
            raise  # Re-raise if we can't find it (shouldn't happen)

        # DB COMMITTED HERE - document exists in database

        # 3. Enqueue AFTER commit
        try:
            await self.queue.enqueue(doc.id)
            logger.info(f"Enqueued document {doc.id}")
        except Exception as e:
            # Enqueue failed - mark document as FAILED in NEW transaction
            logger.error(f"Failed to enqueue document {doc.id}: {e}")
            try:
                async with self.session.begin():
                    await self.repo.update_status(doc.id, DocumentStatus.FAILED)
                logger.info(f"Marked document {doc.id} as FAILED after enqueue failure")
            except Exception as mark_error:
                logger.critical(f"Could not mark {doc.id} as FAILED: {mark_error}")
            raise InfraError(f"Failed to enqueue document: {str(e)}") from e

        return doc
