import asyncio
from contextlib import asynccontextmanager
import os
import secrets

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .errors import ApiProblem, api_problem_handler, validation_error_handler
from .routes import cards_router, runs_router
from ..infrastructure.postgres import AsyncDatabase, Database, MigrationRunner, PostgresPriceAnalyzerRepository


def create_app(
    database_url: str | None = None,
    repository: PostgresPriceAnalyzerRepository | None = None,
    api_token: str | None = None,
) -> FastAPI:
    expected_token = api_token if api_token is not None else os.environ.get("PRICE_WATCH_API_TOKEN")
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if repository is not None:
            app.state.repository = repository
            yield
            return
        url = database_url or os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("Задайте DATABASE_URL")
        def migrate() -> None:
            with Database(url) as migration_database:
                MigrationRunner(migration_database).apply()

        await asyncio.to_thread(migrate)
        database = await AsyncDatabase(url).open()
        app.state.repository = PostgresPriceAnalyzerRepository(database)
        try:
            yield
        finally:
            await database.close()

    app = FastAPI(
        title="Marketplace Price Analyzer API",
        version="0.1.0",
        lifespan=lifespan,
    )
    @app.middleware("http")
    async def require_desktop_token(request: Request, call_next):
        if expected_token and request.method != "OPTIONS":
            actual_token = request.headers.get("x-price-watch-token", "")
            if not secrets.compare_digest(actual_token, expected_token):
                return JSONResponse(
                    status_code=401,
                    content={"error": {"code": "unauthorized", "message": "Нет доступа к API"}},
                )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:1420",
            "http://tauri.localhost",
            "https://tauri.localhost",
            "tauri://localhost",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Request-ID", "X-Price-Watch-Token"],
    )
    app.add_exception_handler(ApiProblem, api_problem_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(cards_router, prefix="/api")
    app.include_router(runs_router, prefix="/api")

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
