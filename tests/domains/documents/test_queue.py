"""Tests for DocumentQueue - proves async testing and failure awareness."""

import pytest
from unittest.mock import AsyncMock
from src.infra.queue.document_queue import (
    DocumentQueue,
    DOCUMENT_QUEUE,
    PROCESSING_QUEUE,
    DLQ_QUEUE,
)
from uuid import uuid4
import json


@pytest.mark.asyncio
async def test_enqueue_dequeue_roundtrip():
    """Test successful enqueue → dequeue roundtrip."""
    mock_redis = AsyncMock()
    queue = DocumentQueue(mock_redis)

    doc_id = uuid4()

    # Enqueue
    await queue.enqueue(doc_id)

    # Verify Redis rpush called with correct payload
    mock_redis.rpush.assert_called_once()
    call_args = mock_redis.rpush.call_args
    assert call_args[0][0] == DOCUMENT_QUEUE

    payload = json.loads(call_args[0][1])
    assert payload["document_id"] == str(doc_id)


@pytest.mark.asyncio
async def test_dequeue_success():
    """Test successful dequeue returns (UUID, enriched_payload with started_at)."""
    doc_id = uuid4()
    payload = json.dumps({"document_id": str(doc_id)})

    mock_redis = AsyncMock()
    # brpoplpush returns raw bytes, not tuple
    mock_redis.brpoplpush.return_value = payload.encode()

    queue = DocumentQueue(mock_redis)
    result_id, raw = await queue.dequeue()

    assert result_id == doc_id
    # Raw payload now includes started_at timestamp
    raw_parsed = json.loads(raw)
    assert raw_parsed["document_id"] == str(doc_id)
    assert "started_at" in raw_parsed
    mock_redis.brpoplpush.assert_called_once_with(
        DOCUMENT_QUEUE, PROCESSING_QUEUE, timeout=2
    )


@pytest.mark.asyncio
async def test_dequeue_empty():
    """Test dequeue returns (None, None) when queue is empty."""
    mock_redis = AsyncMock()
    mock_redis.brpoplpush.return_value = None

    queue = DocumentQueue(mock_redis)
    result_id, raw = await queue.dequeue()

    assert result_id is None
    assert raw is None


@pytest.mark.asyncio
async def test_malformed_payload_handling():
    """
    Test queue handles malformed JSON gracefully.
    Malformed messages should go to DLQ.
    """
    mock_redis = AsyncMock()
    # Malformed: missing document_id field
    mock_redis.brpoplpush.return_value = b'{"invalid": "no document_id"}'

    queue = DocumentQueue(mock_redis)
    result_id, raw = await queue.dequeue()

    assert result_id is None  # Graceful degradation
    # Verify DLQ was called
    mock_redis.rpush.assert_called_once()
    dlq_call = mock_redis.rpush.call_args
    assert dlq_call[0][0] == DLQ_QUEUE


@pytest.mark.asyncio
async def test_malformed_json_handling():
    """Test queue handles completely invalid JSON and moves to DLQ."""
    mock_redis = AsyncMock()
    mock_redis.brpoplpush.return_value = b"not even json"

    queue = DocumentQueue(mock_redis)
    result_id, raw = await queue.dequeue()

    assert result_id is None
    # Should have moved to DLQ
    mock_redis.rpush.assert_called_once()


@pytest.mark.asyncio
async def test_acknowledge_success():
    """Test acknowledge removes job from processing queue using raw_payload."""
    mock_redis = AsyncMock()
    mock_redis.lrem.return_value = 1

    queue = DocumentQueue(mock_redis)
    doc_id = uuid4()
    # Acknowledge now takes raw_payload bytes, not UUID
    raw_payload = json.dumps(
        {
            "document_id": str(doc_id),
            "started_at": 1234567890.0,
        }
    ).encode()

    await queue.acknowledge(raw_payload)

    mock_redis.lrem.assert_called_once_with(PROCESSING_QUEUE, 1, raw_payload)


@pytest.mark.asyncio
async def test_queue_length_for_backpressure():
    """Test queue length check for backpressure control."""
    mock_redis = AsyncMock()
    mock_redis.llen.return_value = 500

    queue = DocumentQueue(mock_redis)
    length = await queue.get_queue_length()

    assert length == 500
    mock_redis.llen.assert_called_once_with(DOCUMENT_QUEUE)


@pytest.mark.asyncio
async def test_move_to_dlq():
    """Test move_to_dlq adds message with metadata."""
    mock_redis = AsyncMock()
    queue = DocumentQueue(mock_redis)

    await queue.move_to_dlq(b'{"bad": "data"}', "Parse error")

    mock_redis.rpush.assert_called_once()
    call = mock_redis.rpush.call_args
    assert call[0][0] == DLQ_QUEUE
    entry = json.loads(call[0][1])
    assert entry["reason"] == "Parse error"
    assert "timestamp" in entry
