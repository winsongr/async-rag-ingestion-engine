from pydantic import BaseModel
from uuid import UUID
from src.domains.documents.models import DocumentStatus


class DocumentCreateRequest(BaseModel):
    source: str


class DocumentResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    source: str

    class Config:
        from_attributes = True
