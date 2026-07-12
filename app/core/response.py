from __future__ import annotations

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def success_response(message: str, data: object | None = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=jsonable_encoder({"success": True, "message": message, "data": data}))


def error_response(message: str, status_code: int = 400, details: object | None = None) -> JSONResponse:
    payload: dict[str, object] = {"success": False, "message": message}
    if details is not None:
        payload["details"] = details
    return JSONResponse(status_code=status_code, content=jsonable_encoder(payload))


def validation_error_to_details(exc: RequestValidationError) -> list[dict[str, object]]:
    return [
        {
            "field": ".".join(str(part) for part in item.get("loc", []) if part != "body"),
            "message": item.get("msg"),
            "type": item.get("type"),
        }
        for item in exc.errors()
    ]


async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response("Invalid request.", status_code=422, details=validation_error_to_details(exc))


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    return error_response(str(exc.detail), status_code=exc.status_code)


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response("Internal server error.", status_code=500)
