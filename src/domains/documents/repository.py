from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.domains.documents.models import Document, DocumentStatus, MAX_RETRIES
from src.domains.documents.errors import (
    DocumentNotFound,
    InvalidStateTransition,
    MaxRetriesExceeded,
)
from uuid import UUID


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_document(self, source: str) -> Document:
        """Create a new document with PENDING status."""
        document = Document(source=source, status=DocumentStatus.PENDING)
        self.session.add(document)
        await self.session.flush()  # Flush to get the ID
        return document

    async def get_document_by_id(self, document_id: UUID) -> Document | None:
        """Get a document by its ID."""
        query = select(Document).where(Document.id == document_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_document_by_id_for_update(self, document_id: UUID) -> Document | None:
        """Get a document by its ID with row lock (SELECT FOR UPDATE)."""
        query = select(Document).where(Document.id == document_id).with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_document_by_source(self, source: str) -> Document | None:
        """Get a document by its source (for idempotency)."""
        query = select(Document).where(Document.source == source)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self, document_id: UUID, status: DocumentStatus
    ) -> Document:
        """
        Update a document's status with strict state machine enforcement.
        Uses SELECT FOR UPDATE to prevent concurrent modifications.
        """
        document = await self.get_document_by_id_for_update(document_id)
        if not document:
            raise DocumentNotFound(document_id)

        current = DocumentStatus(document.status)
        target = status

        # Terminal states check (DONE is always terminal)
        if current == DocumentStatus.DONE:
            raise InvalidStateTransition(current.value, target.value)

        # FAILED can transition to PENDING (retry) if under max retries
        if current == DocumentStatus.FAILED:
            if target == DocumentStatus.PENDING:
                if document.retry_count >= MAX_RETRIES:
                    raise MaxRetriesExceeded(document_id, document.retry_count)
                # Allow retry - count is incremented in retry_document()
            else:
                raise InvalidStateTransition(current.value, target.value)

        # Invalid transitions
        if current == DocumentStatus.PENDING and target == DocumentStatus.DONE:
            raise InvalidStateTransition(current.value, target.value)

        document.status = status
        await self.session.flush()
        return document

    async def retry_document(self, document_id: UUID) -> Document:
        """
        Retry a failed document by transitioning FAILED -> PENDING.
        Increments retry_count and checks against MAX_RETRIES.
        """
        document = await self.get_document_by_id_for_update(document_id)
        if not document:
            raise DocumentNotFound(document_id)

        if DocumentStatus(document.status) != DocumentStatus.FAILED:
            raise InvalidStateTransition(document.status, DocumentStatus.PENDING.value)

        if document.retry_count >= MAX_RETRIES:
            raise MaxRetriesExceeded(document_id, document.retry_count)

        document.retry_count += 1
        document.status = DocumentStatus.PENDING
        await self.session.flush()
        return document

    async def update_file_path(self, document_id: UUID, file_path: str) -> Document:
        """Update a document's file_path."""
        document = await self.get_document_by_id(document_id)
        if not document:
            raise DocumentNotFound(document_id)

        document.file_path = file_path
        await self.session.flush()
        return document

    async def clear_file_path(self, document_id: UUID) -> Document:
        """Clear file_path after processing (cleanup)."""
        document = await self.get_document_by_id(document_id)
        if not document:
            raise DocumentNotFound(document_id)

        document.file_path = None
        await self.session.flush()
        return document
