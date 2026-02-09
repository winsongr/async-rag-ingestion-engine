import os
import logging
import aiofiles
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.documents.repository import DocumentRepository
from src.domains.documents.models import DocumentStatus
from src.core.errors import AppError
from src.domains.documents.errors import DocumentNotFound, ProcessingConflict

logger = logging.getLogger("process_service")


class DocumentProcessor:
    def __init__(
        self,
        session: AsyncSession,
        chunking_service,
        embedding_service,
        vector_service,
    ):
        self.session = session
        self.repo = DocumentRepository(session)
        self.chunking_service = chunking_service
        self.embedding_service = embedding_service
        self.vector_service = vector_service

    async def process(self, doc_id: UUID):
        """
        Orchestrates the document processing pipeline.
        Transaction boundary handled here for status updates.
        File is deleted after processing (success or failure).
        """
        file_path = None

        async with self.session.begin():
            # 1. Fetch & Validate (with row lock)
            doc = await self.repo.get_document_by_id_for_update(doc_id)
            if not doc:
                raise DocumentNotFound(doc_id)

            if doc.status in (DocumentStatus.DONE, DocumentStatus.PROCESSING):
                # Idempotency: If already processing/done, raise specific error.
                raise ProcessingConflict(doc_id, doc.status)

            file_path = doc.file_path

            # 2. Mark PROCESSING (within same transaction with lock)
            await self.repo.update_status(doc_id, DocumentStatus.PROCESSING)

        # Transaction committed. Now safe to proceed with heavy lifting.

        try:
            # 3. Heavy Lifting (outside DB transaction)
            if file_path:
                content = await self._read_file(file_path)
                chunks = self.chunking_service.chunk(content)

                if chunks:
                    embeddings = self.embedding_service.embed_batch(chunks)
                    await self.vector_service.upsert_chunks(doc_id, chunks, embeddings)

            # 4. Mark DONE (new transaction)
            async with self.session.begin():
                await self.repo.update_status(doc_id, DocumentStatus.DONE)
                # Clear file_path reference in DB
                await self.repo.clear_file_path(doc_id)

            # 5. Delete file after successful processing
            if file_path:
                await self._delete_file(file_path)

        except Exception as e:
            # Cleanup file even on failure
            if file_path:
                await self._delete_file(file_path)
            # Propagate error so worker can handle retries/failure marking
            raise AppError(f"Processing failed: {str(e)}") from e

    async def mark_failed(self, doc_id: UUID):
        """Helper to mark document as failed and cleanup file."""
        async with self.session.begin():
            doc = await self.repo.get_document_by_id(doc_id)
            if doc and doc.file_path:
                await self._delete_file(doc.file_path)
                await self.repo.clear_file_path(doc_id)
            await self.repo.update_status(doc_id, DocumentStatus.FAILED)

    async def _read_file(self, file_path: str) -> str:
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                return await f.read()
        except Exception as e:
            raise AppError(f"File read error: {str(e)}") from e

    async def _delete_file(self, file_path: str):
        """Delete file from disk to prevent storage leakage."""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted processed file: {file_path}")
        except Exception as e:
            # Log but don't fail processing for cleanup errors
            logger.warning(f"Failed to delete file {file_path}: {e}")
