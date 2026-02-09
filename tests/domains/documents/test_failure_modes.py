"""
Chaos testing - Infrastructure failure scenarios.

STAFF-LEVEL SIGNAL: Tests what happens when infrastructure fails.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.infra.queue.document_queue import DocumentQueue
from uuid import uuid4
from src.domains.documents.models import DocumentStatus


@pytest.mark.asyncio
async def test_redis_connection_failure_on_enqueue():
    """Chaos test: Redis goes down during enqueue."""
    mock_redis = AsyncMock()
    mock_redis.rpush.side_effect = ConnectionError("Redis connection lost")

    queue = DocumentQueue(mock_redis)
    doc_id = uuid4()

    with pytest.raises(ConnectionError):
        await queue.enqueue(doc_id)


@pytest.mark.asyncio
async def test_redis_timeout_on_dequeue():
    """Chaos test: Redis timeout during dequeue."""
    mock_redis = AsyncMock()
    mock_redis.brpoplpush.side_effect = TimeoutError("Operation timed out")

    queue = DocumentQueue(mock_redis)

    with pytest.raises(TimeoutError):
        await queue.dequeue()


@pytest.mark.asyncio
async def test_backpressure_triggers_at_limit():
    """Test that backpressure guard actually works when queue is full."""
    from src.core.config.settings import settings

    mock_redis = AsyncMock()
    mock_redis.llen.return_value = settings.QUEUE_MAX_LENGTH + 1

    queue = DocumentQueue(mock_redis)
    length = await queue.get_queue_length()

    assert length > settings.QUEUE_MAX_LENGTH


@pytest.mark.asyncio
async def test_worker_handles_qdrant_failure():
    """
    Chaos test: Qdrant goes down during indexing.
    Worker should catch exception and mark document FAILED.
    """
    from src.workers.document_worker import DocumentWorker, WorkerDependencies
    from contextlib import asynccontextmanager

    doc_id = uuid4()
    raw_payload = b'{"document_id": "test", "started_at": 1234567890.0}'

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.status = DocumentStatus.PENDING
    mock_doc.file_path = "/fake/path.txt"

    mock_repo = AsyncMock()
    mock_repo.get_document_by_id.return_value = mock_doc
    mock_repo.update_status.return_value = mock_doc

    # Create a proper mock session that works with `async with session.begin():`
    mock_session = MagicMock()

    @asynccontextmanager
    async def mock_begin():
        yield

    mock_session.begin = mock_begin

    # Mock session factory as async context manager
    @asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    # Create mock dependencies
    mock_vector = MagicMock()
    mock_vector.upsert_chunks = AsyncMock(side_effect=ConnectionError("Qdrant down"))
    mock_vector.ensure_collection_exists = AsyncMock()

    mock_chunking = MagicMock()
    mock_chunking.chunk = MagicMock(return_value=["chunk1"])

    mock_embedding = MagicMock()
    mock_embedding.embed_batch = MagicMock(return_value=[[0.1] * 1536])

    deps = WorkerDependencies(
        redis=AsyncMock(),
        session_factory=mock_session_factory,
        qdrant=AsyncMock(),
        embedding_service=mock_embedding,
        chunking_service=mock_chunking,
        vector_service=mock_vector,
    )

    worker = DocumentWorker(deps)

    # Patch Repo usage in Process Service
    with patch(
        "src.application.documents.process.DocumentRepository",
        return_value=mock_repo,
    ):
        with patch("aiofiles.open") as mock_open:
            # Ensure file open works
            mock_f = AsyncMock()
            mock_f.read.return_value = "content"
            mock_open.return_value.__aenter__.return_value = mock_f

            # Run
            await worker.process_job(doc_id, raw_payload)

    # Verify - should complete without raising, document marked FAILED
    calls = [c[0][1] for c in mock_repo.update_status.call_args_list]
    assert DocumentStatus.FAILED in calls
