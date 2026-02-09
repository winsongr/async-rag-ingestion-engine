from uuid import UUID
from src.core.errors import AppError
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from src.domains.documents.repository import DocumentRepository
from src.domains.documents.models import DocumentStatus
from src.infra.queue.document_queue import DocumentQueue
from src.services.file_store import FileStore
from src.core.config.settings import settings
from src.domains.documents.errors import DocumentNotFound, ProcessingConflict


class UploadService:
    def __init__(self, session: AsyncSession, redis: Redis):
        self.session = session
        self.queue = DocumentQueue(redis)
        self.repo = DocumentRepository(session)
        self.file_store = FileStore()

    async def upload(self, document_id: UUID, file: UploadFile):
        """
        Upload a file for a document.
        Validates state, saves file, updates metadata, and enqueues for processing.
        """
        # 1. Backpressure Check
        queue_length = await self.queue.get_queue_length()
        if queue_length >= settings.QUEUE_MAX_LENGTH:
            raise AppError(
                f"Queue is full ({queue_length}/{settings.QUEUE_MAX_LENGTH})."
            )

        # 2. Save File (Mechanics - outside DB transaction)
        try:
            file_path = await self.file_store.save_file(file, document_id)
        except Exception as e:
            raise AppError(f"Failed to save file: {str(e)}") from e

        # 3. Transactional Update
        async with self.session.begin():
            doc = await self.repo.get_document_by_id(document_id)
            if not doc:
                raise DocumentNotFound(document_id)

            # Invariant Check - handle both string and enum status
            status_val = (
                doc.status.value if hasattr(doc.status, "value") else doc.status
            )
            if status_val in (
                DocumentStatus.PROCESSING.value,
                DocumentStatus.DONE.value,
            ):
                raise ProcessingConflict(document_id, status_val)

            # Update Metadata
            doc = await self.repo.update_file_path(document_id, file_path)

            # Enqueue
            await self.queue.enqueue(doc.id)

        return doc
