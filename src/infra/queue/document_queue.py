import json
import time
import logging
from uuid import UUID
from redis.asyncio import Redis

MAIN_QUEUE = "document_ingestion_queue"
PROCESSING_QUEUE = "document_processing_queue"
DEAD_LETTER_QUEUE = "document_dead_letter_queue"

logger = logging.getLogger("document_queue")


class DocumentQueue:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def enqueue(self, document_id: UUID):
        """Push document ID to the main queue."""
        payload = json.dumps({"document_id": str(document_id)})
        await self.redis.rpush(MAIN_QUEUE, payload)

    async def dequeue(self) -> tuple[UUID | None, bytes | None]:
        """
        Atomically move job from main queue to processing queue.
        Returns (document_id, raw_payload) or (None, None) if empty.

        Uses BRPOPLPUSH for at-least-once semantics:
        - Job stays in processing queue until acknowledged
        - On crash, job can be recovered from processing queue
        """
        result = await self.redis.brpoplpush(MAIN_QUEUE, PROCESSING_QUEUE, timeout=2)
        if not result:
            return None, None

        try:
            # Parse incoming payload (may or may not have started_at)
            incoming = json.loads(result)
            doc_id = UUID(incoming["document_id"])

            # Add visibility timestamp if not present, then update in processing queue
            if "started_at" not in incoming:
                enriched = {
                    "document_id": str(doc_id),
                    "started_at": time.time(),
                }
                enriched_payload = json.dumps(enriched)
                # Atomically replace: remove old, add enriched
                await self.redis.lrem(PROCESSING_QUEUE, 1, result)
                await self.redis.lpush(PROCESSING_QUEUE, enriched_payload)
                return doc_id, enriched_payload.encode()

            return doc_id, result
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
            # Malformed message - move to DLQ
            await self.move_to_dlq(result, f"Parse error: {str(e)}")
            # Remove from processing queue since it's in DLQ now
            await self.redis.lrem(PROCESSING_QUEUE, 1, result)
            return None, None

    async def acknowledge(self, raw_payload: bytes):
        """Remove successfully processed job from processing queue."""
        removed = await self.redis.lrem(PROCESSING_QUEUE, 1, raw_payload)
        if removed == 0:
            # Try legacy format without started_at
            try:
                payload = json.loads(raw_payload)
                legacy = json.dumps({"document_id": payload["document_id"]})
                removed = await self.redis.lrem(PROCESSING_QUEUE, 1, legacy)
            except Exception:
                pass
        if removed == 0:
            logger.warning(
                f"Job not found in processing queue during ack: {raw_payload[:100]}"
            )

    async def move_to_dlq(self, raw_message: bytes, reason: str):
        """Move malformed/failed message to dead letter queue with metadata."""
        try:
            msg_str = (
                raw_message.decode() if isinstance(raw_message, bytes) else raw_message
            )
        except Exception:
            msg_str = str(raw_message)

        entry = {
            "payload": msg_str,
            "reason": reason,
            "timestamp": time.time(),
        }
        await self.redis.rpush(DEAD_LETTER_QUEUE, json.dumps(entry))
        logger.error(f"Moved to DLQ: {reason} - {msg_str[:100]}")

    async def get_queue_length(self) -> int:
        """Get current main queue length for backpressure control."""
        return await self.redis.llen(MAIN_QUEUE)

    async def get_processing_queue_length(self) -> int:
        """Get current processing queue length (in-flight jobs)."""
        return await self.redis.llen(PROCESSING_QUEUE)

    async def get_dlq_length(self) -> int:
        """Get dead letter queue length."""
        return await self.redis.llen(DEAD_LETTER_QUEUE)

    async def requeue_stale_jobs(
        self, max_age_seconds: float = 300, max_retries: int = 3
    ):
        """
        Sweep processing queue for stale jobs and requeue those exceeding visibility timeout.

        Only requeues jobs where:
        - started_at timestamp exists AND
        - (current_time - started_at) > max_age_seconds

        Jobs without timestamps are skipped (they're actively being enriched).
        Jobs exceeding max_retries go to DLQ instead of being requeued.
        """
        now = time.time()
        items = await self.redis.lrange(PROCESSING_QUEUE, 0, -1)
        requeued = 0
        moved_to_dlq = 0
        skipped = 0

        for item in items:
            try:
                payload = json.loads(item)
                started_at = payload.get("started_at")
                retry_count = payload.get("retry_count", 0)

                # Skip jobs without timestamps (freshly dequeued, being enriched)
                if started_at is None:
                    skipped += 1
                    continue

                # Skip jobs that haven't exceeded visibility timeout
                age = now - started_at
                if age < max_age_seconds:
                    skipped += 1
                    continue

                # Remove from processing queue
                await self.redis.lrem(PROCESSING_QUEUE, 1, item)

                # Check retry limit
                if retry_count >= max_retries:
                    await self.move_to_dlq(
                        item, f"Exceeded {max_retries} retries after {age:.0f}s"
                    )
                    moved_to_dlq += 1
                    continue

                # Requeue with incremented retry count (strip started_at for fresh processing)
                requeue_payload = {
                    "document_id": payload["document_id"],
                    "retry_count": retry_count + 1,
                }
                await self.redis.lpush(MAIN_QUEUE, json.dumps(requeue_payload))
                requeued += 1
                logger.info(
                    f"Requeued stale job {payload['document_id']} (retry {retry_count + 1}, was {age:.0f}s old)"
                )

            except (json.JSONDecodeError, KeyError) as e:
                # Malformed - move to DLQ
                await self.redis.lrem(PROCESSING_QUEUE, 1, item)
                await self.move_to_dlq(item, f"Malformed in processing queue: {e}")
                moved_to_dlq += 1

        if requeued > 0 or moved_to_dlq > 0:
            logger.info(
                f"Stale job sweep: requeued={requeued}, dlq={moved_to_dlq}, skipped={skipped}"
            )

        return {"requeued": requeued, "moved_to_dlq": moved_to_dlq, "skipped": skipped}
