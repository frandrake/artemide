"""Standardised JSON error envelope."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..services.exceptions import (
    ConflictError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError as ServiceValidationError,
)


def _envelope(error: str, message: str | None = None, **extra) -> dict:
    body = {"error": error}
    if message is not None:
        body["message"] = message
    if extra:
        body.update(extra)
    return body


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_envelope("not_found", str(exc)),
        )

    @app.exception_handler(ConflictError)
    async def _conflict(_: Request, exc: ConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_envelope("conflict", str(exc)),
        )

    @app.exception_handler(InvalidStateTransitionError)
    async def _rule(_: Request, exc: InvalidStateTransitionError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope("rule_violation", str(exc)),
        )

    @app.exception_handler(ServiceValidationError)
    async def _service_validation(_: Request, exc: ServiceValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_envelope("validation_error", str(exc)),
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_envelope("validation_error", "invalid request body", details=exc.errors()),
        )

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException):
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            return JSONResponse(status_code=401, content=_envelope("unauthorized"))
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return JSONResponse(
                status_code=404, content=_envelope("not_found", str(exc.detail))
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("error", str(exc.detail)),
        )
