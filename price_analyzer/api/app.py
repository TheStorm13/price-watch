from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .errors import ApiProblem, api_problem_handler, validation_error_handler
from .routes import cards_router, runs_router
from ..infrastructure.postgres import Database, MigrationRunner, PostgresPriceAnalyzerRepository


def create_app(
    database_url: str | None = None,
    repository: PostgresPriceAnalyzerRepository | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if repository is not None:
            app.state.repository = repository
            yield
            return
        url = database_url or os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("Задайте DATABASE_URL")
        database = Database(url).open()
        MigrationRunner(database).apply()
        app.state.repository = PostgresPriceAnalyzerRepository(database)
        try:
            yield
        finally:
            database.close()

    app = FastAPI(
        title="Marketplace Price Analyzer API",
        version="0.1.0",
        lifespan=lifespan,
    )
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
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-Request-ID"],
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
