"""
OGC API - Processes exception responses.

Every error of the OGC sub-app is answered with the OGC exception body
(``type``, ``title``, ``status``, ``detail``; RFC 7807). Invalid execute
inputs are ``400 Bad Request`` instead of FastAPI's ``422``, with an
``errors`` list naming each failing input.
"""

from http import HTTPStatus
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .user_messages import INVALID_INPUT_MESSAGE

OGC_EXCEPTION_BASE = "http://www.opengis.net/def/exceptions/ogcapi-processes-1/1.0/"
NO_SUCH_PROCESS = OGC_EXCEPTION_BASE + "no-such-process"
RESULT_NOT_READY = OGC_EXCEPTION_BASE + "result-not-ready"
#: RFC 7807 type for errors without a more specific OGC exception type.
UNTYPED = "about:blank"


class OgcHTTPException(HTTPException):
    """``HTTPException`` with an OGC exception type, e.g. :data:`NO_SUCH_PROCESS`."""

    def __init__(self, status_code: int, exception_type: str, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.exception_type = exception_type


def _ogc_exception_response(
    status_code: int,
    exception_type: str,
    detail: Any,
    errors: Optional[List[Dict[str, str]]] = None,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    """JSON response with the OGC exception body."""
    content: Dict[str, Any] = {
        "type": exception_type,
        "title": HTTPStatus(status_code).phrase,
        "status": status_code,
        "detail": detail,
    }
    if errors is not None:
        content["errors"] = errors
    return JSONResponse(status_code=status_code, content=content, headers=headers)


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return _ogc_exception_response(
        exc.status_code,
        getattr(exc, "exception_type", UNTYPED),
        exc.detail,
        headers=getattr(exc, "headers", None),
    )


def _input_name(location: tuple) -> str:
    """``("body", "inputs", "bbox", "min_x")`` → ``"bbox.min_x"``; ``"inputs"`` for the whole object."""
    path = [str(part) for part in location[1:] if part != "inputs"] if location[:1] == ("body",) else []
    return ".".join(path) or "inputs"


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = [
        {"input": _input_name(tuple(error["loc"])), "message": error["msg"]}
        for error in exc.errors()
    ]
    return _ogc_exception_response(
        HTTPStatus.BAD_REQUEST, UNTYPED, INVALID_INPUT_MESSAGE, errors=errors
    )


def register_ogc_exception_handlers(app: FastAPI) -> None:
    """Answer every error of ``app`` with the OGC exception body."""
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
