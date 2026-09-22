from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiProblem(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        field: str | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field


async def api_problem_handler(request: Request, exc: ApiProblem) -> JSONResponse:
    error = {"code": exc.code, "message": exc.message}
    if exc.field:
        error["field"] = exc.field
    request_id = request.headers.get("x-request-id")
    if request_id:
        error["requestId"] = request_id
    return JSONResponse(status_code=exc.status_code, content={"error": error})


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = first.get("loc", ())
    field = str(location[-1]) if len(location) > 1 else None
    error = {
        "code": "validation_error",
        "message": str(first.get("msg") or "Некорректные данные"),
    }
    if field:
        error["field"] = field
    request_id = request.headers.get("x-request-id")
    if request_id:
        error["requestId"] = request_id
    return JSONResponse(status_code=422, content={"error": error})
