from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EntityNotFoundError(DomainError):
    status_code = 404


class InvalidInputError(DomainError):
    status_code = 422


class AuthenticationError(DomainError):
    status_code = 401


class ServiceUnavailableError(DomainError):
    status_code = 503


class DownstreamServiceError(DomainError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def register_domain_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.message},
        )
