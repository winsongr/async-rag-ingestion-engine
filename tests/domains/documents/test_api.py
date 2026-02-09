import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from src.main import app
from src.domains.documents.models import DocumentStatus, Document
from uuid import uuid4

client = TestClient(app)


@pytest.mark.asyncio
async def test_duplicate_enqueue_protection():
    """
    Test that uploading to a PROCESSING document triggers 409 Conflict.
    """
    doc_id = uuid4()
    mock_doc = Document(id=doc_id, status=DocumentStatus.PROCESSING, source="src")

    mock_repo = AsyncMock()
    mock_repo.get_document_by_id.return_value = mock_doc

    # Mock session
    mock_session = AsyncMock()
    mock_session.begin = MagicMock(return_value=AsyncMock())

    # Override dependencies
    from src.infra.db.dependencies import get_db_session
    from src.infra.lifecycle.dependencies import get_redis_client

    async def override_get_db_session():
        yield mock_session

    async def override_get_redis():
        yield AsyncMock()

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_redis_client] = override_get_redis

    # Mock internal components
    with (
        patch("src.application.documents.upload.DocumentRepository") as MockRepoClass,
        patch("src.application.documents.upload.DocumentQueue") as MockQueueClass,
    ):
        mock_repo_instance = MockRepoClass.return_value
        mock_repo_instance.get_document_by_id = AsyncMock(return_value=mock_doc)

        mock_queue = MockQueueClass.return_value
        mock_queue.get_queue_length = AsyncMock(return_value=0)

        mock_queue.enqueue = AsyncMock()

        # Perform Request
        files = {"file": ("test.txt", b"content", "text/plain")}
        response = client.post(f"/api/v1/documents/{doc_id}/upload", files=files)

        assert response.status_code == 409
        # The new error message is slightly different, check for key terms
        assert "already in state" in response.json()["detail"]
        assert "PROCESSING" in response.json()["detail"]

    # Cleanup overrides
    app.dependency_overrides = {}
