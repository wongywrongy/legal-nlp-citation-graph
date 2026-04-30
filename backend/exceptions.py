"""
Structured error responses. Imported by main.py to register handlers.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    code: str = "app_error"
    status_code: int = 500

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail


class NotFoundError(AppError):
    code = "not_found"
    status_code = 404


class DuplicateError(AppError):
    code = "duplicate"
    status_code = 409


class BadInputError(AppError):
    code = "bad_input"
    status_code = 400


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(_request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "detail": exc.detail},
        )

    @app.exception_handler(FileNotFoundError)
    async def _fnf_handler(_request: Request, exc: FileNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"code": "file_not_found", "message": str(exc), "detail": None},
        )

    @app.exception_handler(ValueError)
    async def _value_error_handler(_request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"code": "bad_input", "message": str(exc), "detail": None},
        )
