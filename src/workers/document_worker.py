import asyncio
import logging
import signal
from uuid import UUID
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from qdrant_client import AsyncQdrantClient

from src.infra.queue.document_queue import DocumentQueue
from src.application.documents.process import DocumentProcessor
from src.services.chunking import ChunkingService
from src.services.embeddings import MockEmbeddingService
from src.infra.vector.index import VectorIndexService
from src.infra.queue.document_queue import (
    DLQ_QUEUE,
    MAX_RETRIES,
    RETRY_KEY_PREFIX,
)
from src.infra.monitoring import DOCUMENTS_PROCESSED

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("document_worker")


@dataclass
class WorkerDependencies:
    """
    Dependency container for worker - mirrors API lifecycle pattern.
    All dependencies are injected rather than imported directly.
    """

    redis: Redis
    session_factory: async_sessionmaker[AsyncSession]
    qdrant: AsyncQdrantClient
    embedding_service: MockEmbeddingService
    chunking_service: ChunkingService
    vector_service: VectorIndexService


class DocumentWorker:
    """
    Document processing worker with dependency injection.

    Usage:
        deps = WorkerDependencies(...)  # or use create_worker_dependencies()
        worker = DocumentWorker(deps)
        await worker.run()
    """

    def __init__(self, deps: WorkerDependencies):
        self.running = True
        self.deps = deps
        self.queue = DocumentQueue(deps.redis)
        logger.info("Worker initialized with injected dependencies.")

    async def _retry_key(self, doc_id: str) -> str:
        return f"{RETRY_KEY_PREFIX}{doc_id}"

    async def run(self):
        logger.info("Worker starting... Waiting for jobs.")

        # Ensure collection exists once at startup
        await self.deps.vector_service.ensure_collection_exists()

        job_count = 0

        while self.running:
            try:
                # Heartbeat
                if job_count > 0 and job_count % 10 == 0:
                    logger.info(f"worker_alive: processed={job_count}")

                # 1. Blocking Dequeue (RPOPLPUSH - at-least-once)
                doc_id, raw_payload = await self.queue.dequeue()
                if not doc_id:
                    await asyncio.sleep(1)
                    continue

                logger.info(f"Received job for document: {doc_id}")

                try:
                    # Process with retry wrapper
                    await self.process(str(doc_id), raw_payload)

                    # On success (no raise), acknowledge
                    await self.queue.acknowledge(raw_payload)
                    logger.info(f"Acknowledged job for document: {doc_id}")
                except Exception:
                    # On failure (process raised), loop handles it
                    # Job stays in processing queue until staleness check or manual intervention
                    pass

                job_count += 1

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(5)

    async def process(self, document_id: str, raw_payload: bytes):
        """
        Process a document with retry logic and DLQ handling.
        """
        retry_key = await self._retry_key(document_id)
        retry_count = int(await self.deps.redis.get(retry_key) or 0)

        if retry_count >= MAX_RETRIES:
            await self.deps.redis.lpush(DLQ_QUEUE, document_id)

            # Mark failed in DB
            async with self.deps.session_factory() as session:
                from src.application.documents.process import DocumentProcessor

                processor = DocumentProcessor(
                    session=session,
                    chunking_service=self.deps.chunking_service,
                    embedding_service=self.deps.embedding_service,
                    vector_service=self.deps.vector_service,
                )
                await processor.mark_failed(
                    UUID(document_id), reason="max_retries_exceeded"
                )

            DOCUMENTS_PROCESSED.labels(status="dlq").inc()

            logger.error(
                "document.moved_to_dlq",
                extra={
                    "document_id": document_id,
                    "retries": retry_count,
                },
            )

            # Acknowledge to remove from processing queue (prevent zombie)
            await self.queue.acknowledge(raw_payload)
            return

        try:
            # Pass dummy payload as it's not used by process_job currently
            # We strictly cast document_id to UUID as process_job expects it
            success = await self.process_job(UUID(document_id), b"")
            if not success:
                raise Exception("Processing returned False")

            # Success
            await self.deps.redis.delete(retry_key)
            DOCUMENTS_PROCESSED.labels(status="success").inc()

        except Exception as e:
            await self.deps.redis.incr(retry_key)
            logger.warning(
                "document.retry_scheduled",
                extra={
                    "document_id": document_id,
                    "retry": retry_count + 1,
                },
            )
            raise e

    async def process_job(self, doc_id: UUID, raw_payload: bytes) -> bool:
        """
        Process a job. Returns True on success, False on failure.
        On failure, document is marked FAILED but job stays in processing queue.
        """
        async with self.deps.session_factory() as session:
            processor = DocumentProcessor(
                session=session,
                chunking_service=self.deps.chunking_service,
                embedding_service=self.deps.embedding_service,
                vector_service=self.deps.vector_service,
            )

            try:
                await processor.process(doc_id)
                logger.info(f"Successfully processed document {doc_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to process document {doc_id}: {e}")
                try:
                    await processor.mark_failed(doc_id)
                except Exception as mark_failed_error:
                    logger.critical(
                        f"Could not mark document {doc_id} as FAILED: {mark_failed_error}"
                    )
                return False

    async def shutdown(self):
        """Clean shutdown of resources."""
        logger.info("Shutting down worker services...")
        await self.deps.qdrant.close()
        logger.info("Worker services shut down.")

    def stop(self):
        self.running = False
        logger.info("Worker stopping...")


async def create_worker_dependencies() -> WorkerDependencies:
    """
    Factory function to create worker dependencies.
    Mirrors the API lifecycle pattern but for standalone worker process.
    """
    from src.infra.cache.redis import redis_client
    from src.infra.db.postgres import SessionLocal
    from src.core.config.settings import settings

    qdrant = AsyncQdrantClient(url=str(settings.QDRANT_URI))
    embedding_service = MockEmbeddingService()
    chunking_service = ChunkingService()
    vector_service = VectorIndexService(qdrant)

    return WorkerDependencies(
        redis=redis_client,
        session_factory=SessionLocal,
        qdrant=qdrant,
        embedding_service=embedding_service,
        chunking_service=chunking_service,
        vector_service=vector_service,
    )


async def main():
    deps = await create_worker_dependencies()
    worker = DocumentWorker(deps)

    # Graceful Shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop)

    try:
        await worker.run()
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
