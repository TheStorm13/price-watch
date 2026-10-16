"""SQLAlchemy engine and session factory for PostgreSQL."""

from types import TracebackType
from typing import Optional, Type

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(
        self,
        database_url: str,
        pool_size: int = 5,
        max_overflow: int = 5,
    ):
        if not database_url.strip():
            raise ValueError("Не задан DATABASE_URL")
        self.url = self._normalize_url(database_url.strip())
        self.engine: Engine = create_engine(
            self.url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_pre_ping=True,
        )
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    @staticmethod
    def _normalize_url(value: str) -> str:
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    def open(self) -> "Database":
        with self.engine.connect() as connection:
            connection.exec_driver_sql("select 1")
        return self

    def close(self) -> None:
        self.engine.dispose()

    def session(self) -> Session:
        return self.session_factory()

    def __enter__(self) -> "Database":
        return self.open()

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.close()


class AsyncDatabase:
    """Nonblocking PostgreSQL sessions for API, worker, and collection."""

    def __init__(self, database_url: str, pool_size: int = 5, max_overflow: int = 5):
        if not database_url.strip():
            raise ValueError("Не задан DATABASE_URL")
        self.url = Database._normalize_url(database_url.strip()).replace(
            "postgresql+psycopg://", "postgresql+psycopg_async://", 1
        )
        self.engine = create_async_engine(
            self.url, pool_size=pool_size, max_overflow=max_overflow, pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False,
        )

    async def open(self) -> "AsyncDatabase":
        async with self.engine.connect() as connection:
            await connection.exec_driver_sql("select 1")
        return self

    async def close(self) -> None:
        await self.engine.dispose()

    def session(self) -> AsyncSession:
        return self.session_factory()
