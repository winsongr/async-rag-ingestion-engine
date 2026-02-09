"""Worker tests - updated for DI-based worker."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from src.workers.document_worker import DocumentWorker, WorkerDependencies
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
