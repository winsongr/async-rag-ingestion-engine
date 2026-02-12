"""Worker tests - updated for DI-based worker."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.workers.document_worker import DocumentWorker, WorkerDependencies
from src.infra.queue.document_queue import DLQ_QUEUE, MAX_RETRIES
from uuid import uuid4


def create_mock_deps() -> WorkerDependencies:
    """Create mock dependencies for testing."""
    return WorkerDependencies(
        redis=AsyncMock(),
        session_factory=MagicMock(),
        qdrant=AsyncMock(),
        embedding_service=MagicMock(),
        chunking_service=MagicMock(),
        vector_service=MagicMock(),
    )


@pytest.mark.asyncio
async def test_process_document_success():
    """
    Test worker processes document successfully.

    Verifies that the worker:
    1. Instantiates DocumentProcessor correctly
    2. Calls process() with correct ID
    """
    deps = create_mock_deps()
    worker = DocumentWorker(deps)
    doc_id = uuid4()
    raw_payload = b'{"document_id": "test", "started_at": 1234567890.0}'

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = AsyncMock()
    mock_session.__aexit__.return_value = AsyncMock()
    deps.session_factory.return_value = mock_session

    # Mock DocumentProcessor class
    with patch("src.workers.document_worker.DocumentProcessor") as MockProcessorClass:
        mock_processor_instance = AsyncMock()
        MockProcessorClass.return_value = mock_processor_instance

        result = await worker.process_job(doc_id, raw_payload)

        # Verification
        assert result is True
        MockProcessorClass.assert_called_once()
        mock_processor_instance.process.assert_called_once_with(doc_id)


@pytest.mark.asyncio
async def test_worker_marks_failed_on_processing_exception():
    """
    Test that worker marks document as failed if processing raises.
    """
    deps = create_mock_deps()
    worker = DocumentWorker(deps)
    doc_id = uuid4()
    raw_payload = b'{"document_id": "test", "started_at": 1234567890.0}'

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = AsyncMock()
    mock_session.__aexit__.return_value = AsyncMock()
    deps.session_factory.return_value = mock_session

    with patch("src.workers.document_worker.DocumentProcessor") as MockProcessorClass:
        mock_processor_instance = AsyncMock()
        # process() raises exception
        mock_processor_instance.process.side_effect = Exception("Boom")
        MockProcessorClass.return_value = mock_processor_instance

        result = await worker.process_job(doc_id, raw_payload)

        # Verification
        assert result is False
        mock_processor_instance.process.assert_called_once_with(doc_id)
        mock_processor_instance.mark_failed.assert_called_once_with(doc_id)


@pytest.mark.asyncio
async def test_worker_lifecycle():
    """Test worker initialized and shut down."""
    deps = create_mock_deps()
    worker = DocumentWorker(deps)

    assert worker.deps.embedding_service is not None

    await worker.shutdown()
    deps.qdrant.close.assert_called_once()


@pytest.mark.asyncio
async def test_worker_skips_processing_if_queue_empty():
    """Test queue behavior (lightweight check)."""
    # This logic is in run(), not process_job. We can skip for now or test run() loop.
    pass


# Fakeredis implementation for testing
class FakeRedis:
    def __init__(self):
        self.data = {}
        self.lists = {}

    async def get(self, key):
        return self.data.get(key)

    async def incr(self, key):
        val = int(self.data.get(key, 0)) + 1
        self.data[key] = str(val)
        return val

    async def delete(self, key):
        if key in self.data:
            del self.data[key]

    async def lpush(self, key, value):
        if key not in self.lists:
            self.lists[key] = []
        self.lists[key].insert(0, value)

    async def lrange(self, key, start, end):
        lst = self.lists.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start : end + 1]

    async def lrem(self, key, count, value):
        """Remove elements from list (simplified for testing)."""
        if key not in self.lists:
            return 0
        try:
            self.lists[key].remove(value)
            return 1
        except ValueError:
            return 0


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.mark.asyncio
async def test_document_moves_to_dlq_after_max_retries(fake_redis):
    # Setup worker with fake redis
    deps = create_mock_deps()

    # Mock Session Setup (Critical for DocumentProcessor transaction context)
    mock_session = AsyncMock()
    # begin() is synchronous in SQLAlchemy AsyncSession, so we must use MagicMock
    mock_session.begin = MagicMock()
    mock_session.begin.return_value.__aenter__.return_value = AsyncMock()
    mock_session.begin.return_value.__aexit__.return_value = None

    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    deps.session_factory.return_value = mock_session

    deps.redis = fake_redis
    worker = DocumentWorker(deps)

    doc_id = str(uuid4())
    raw_payload = b'{"document_id": "' + doc_id.encode() + b'"}'

    # force failure
    for _ in range(MAX_RETRIES):
        with pytest.raises(Exception):
            with patch.object(worker, "process_job", side_effect=Exception("Fail")):
                await worker.process(doc_id, raw_payload)

    # 4th attempt: sees MAX_RETRIES reached, moves to DLQ
    # Patch mark_failed to avoid deep async mocking
    with patch(
        "src.application.documents.process.DocumentProcessor.mark_failed",
        new_callable=AsyncMock,
    ):
        await worker.process(doc_id, raw_payload)

    dlq = await fake_redis.lrange(DLQ_QUEUE, 0, -1)
    assert doc_id in dlq
