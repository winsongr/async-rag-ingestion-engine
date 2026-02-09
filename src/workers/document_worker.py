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
                success = await self.process_job(doc_id, raw_payload)

                if success:
                    # Acknowledge job only on success (using raw_payload for exact match)
                    await self.queue.acknowledge(raw_payload)
                    logger.info(f"Acknowledged job for document: {doc_id}")
                # On failure, job stays in processing queue for requeue sweeper

                job_count += 1

            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(5)

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
