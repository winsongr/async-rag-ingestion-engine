from fastapi import FastAPI
from src.api.router import router as api_router
from src.core.config.settings import settings
from src.infra.lifecycle.app import lifespan
from src.api.exceptions import global_exception_handler


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Backend for document ingestion, async processing, vector embeddings, and RAG-based search.",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(api_router, prefix=settings.API_V1_STR)
    return app


app = create_app()
