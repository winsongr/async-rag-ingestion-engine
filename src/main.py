from fastapi import FastAPI
from src.api.router import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Data Platform",
        version="0.1.0",
        description="A production-grade backend system for ingesting large documents, processing them asynchronously, generating vector embeddings, and serving low-latency semantic search and Retrieval-Augmented Generation (RAG) APIs.",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(api_router)
    return app


app = create_app()
