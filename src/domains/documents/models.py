from enum import Enum
from sqlalchemy import Column, String, DateTime, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from src.domains.base import Base
import uuid


class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    FAILED = "FAILED"


MAX_RETRIES = 3


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String, nullable=False, unique=True, index=True)
    status = Column(String, nullable=False, default=DocumentStatus.PENDING)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    file_path = Column(String, nullable=True)
