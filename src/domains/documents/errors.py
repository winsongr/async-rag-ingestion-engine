from src.core.errors import DomainError


class DocumentError(DomainError):
    """Base document error."""

    pass


class DocumentNotFound(DocumentError):
    def __init__(self, doc_id):
        super().__init__(f"Document with ID {doc_id} not found.")


class InvalidStateTransition(DocumentError):
    def __init__(self, current_status, target_status):
        super().__init__(
            f"Cannot transition document from {current_status} to {target_status}."
        )


class DuplicateDocument(DocumentError):
    def __init__(self, source):
        super().__init__(f"Document with source {source} already exists.")


class ProcessingConflict(DocumentError):
    def __init__(self, doc_id, status):
        super().__init__(
            f"Document {doc_id} is already in state {status} and cannot be re-processed."
        )


class MaxRetriesExceeded(DocumentError):
    def __init__(self, doc_id, retry_count):
        super().__init__(f"Document {doc_id} has exceeded max retries ({retry_count}).")
