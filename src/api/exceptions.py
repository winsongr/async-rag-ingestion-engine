from fastapi import Request, status
from fastapi.responses import JSONResponse
import logging
from uuid import uuid4

logger = logging.getLogger(__name__)


async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to catch unhandled exceptions and return a standard JSON response.
    Secure: Does not leak exception details to the client.

    ARCHITECTURAL NOTE:
    - Domain Exceptions (e.g. DocumentNotFound) should be caught in the API layer and mapped to 4xx.
    - This handler is the safety net for truly unexpected 500s.
    """
    error_id = uuid4()
    logger.error(f"Unhandled exception {error_id}: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal Server Error",
            "error_id": str(error_id),
            "message": "An unexpected error occurred. Please contact support with the error_id.",
        },
    )
