"""Domain errors.

The front end's `ApiError` (`src/api/types.ts`) carries a message and a status.
`ApiError` here is its server-side twin: raised by services, rendered as
`{"detail": "<message>"}` so the HTTP client can rebuild it verbatim.
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.message})

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # FastAPI's default body is a list of error objects; the front end shows
        # `detail` directly to the user, so flatten it to one readable sentence.
        first = exc.errors()[0] if exc.errors() else None
        if first:
            field = ".".join(str(part) for part in first["loc"][1:]) or "request"
            message = f"{field}: {first['msg']}"
        else:
            message = "Invalid request."
        return JSONResponse(status_code=422, content={"detail": message})
