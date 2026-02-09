"""Tests for DocumentRepository - proves DB correctness and transaction thinking."""

import pytest
from src.domains.documents.repository import DocumentRepository
from src.domains.documents.models import DocumentStatus


@pytest.mark.asyncio
async def test_create_document(db_session):
    """Test document creation with PENDING status."""
    repo = DocumentRepository(db_session)

    async with db_session.begin():
        doc = await repo.create_document("https://example.com/test")

    assert doc.source == "https://example.com/test"
    assert doc.status == DocumentStatus.PENDING
    assert doc.id is not None


@pytest.mark.asyncio
async def test_idempotency_via_source(db_session):
    """Test get_document_by_source enables idempotency."""
    repo = DocumentRepository(db_session)

    async with db_session.begin():
        doc1 = await repo.create_document("https://example.com/same")

    # Second call - should find existing
    doc2 = await repo.get_document_by_source("https://example.com/same")

    assert doc1.id == doc2.id


@pytest.mark.asyncio
async def test_status_transitions(db_session):
    """Test valid status transitions."""
    repo = DocumentRepository(db_session)

    async with db_session.begin():
        doc = await repo.create_document("https://example.com/lifecycle")

        # PENDING → PROCESSING
        updated = await repo.update_status(doc.id, DocumentStatus.PROCESSING)
        assert updated.status == DocumentStatus.PROCESSING

        # PROCESSING → DONE
        updated = await repo.update_status(doc.id, DocumentStatus.DONE)
        assert updated.status == DocumentStatus.DONE


@pytest.mark.asyncio
async def test_update_file_path(db_session):
    """Test file path update."""
    repo = DocumentRepository(db_session)

    async with db_session.begin():
        doc = await repo.create_document("https://example.com/file-test")

        updated = await repo.update_file_path(doc.id, "/tmp/test_file.txt")
        assert updated.file_path == "/tmp/test_file.txt"
