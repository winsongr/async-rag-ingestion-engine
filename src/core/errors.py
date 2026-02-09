class AppError(Exception):
    """Base class for all application errors."""

    pass


class DomainError(AppError):
    """Base class for domain logic errors."""

    pass


class InfraError(AppError):
    """Base class for infrastructure errors."""

    pass
