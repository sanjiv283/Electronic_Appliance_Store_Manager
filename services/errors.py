"""Application errors. Every message is safe to show to the user."""


class AppError(Exception):
    status_code = 500


class ValidationError(AppError):
    status_code = 400


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class InsufficientStockError(ConflictError):
    pass


class DatabaseUnavailableError(AppError):
    status_code = 503
