"""Alembic migration facade with one-time adoption of the legacy schema."""

from pathlib import Path
from typing import List

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from .database import Database


PROJECT_DIR = Path(__file__).resolve().parents[3]


class MigrationRunner:
    def __init__(self, database: Database):
        self._database = database

    def _config(self) -> Config:
        config = Config(str(PROJECT_DIR / "alembic.ini"))
        config.set_main_option(
            "script_location", str(Path(__file__).with_name("alembic"))
        )
        config.set_main_option(
            "sqlalchemy.url", self._database.url.replace("%", "%%")
        )
        return config

    def apply(self) -> List[str]:
        inspector = inspect(self._database.engine)
        tables = set(inspector.get_table_names())
        config = self._config()
        with self._database.engine.connect() as connection:
            before = MigrationContext.configure(connection).get_current_revision()

        # The original SQL runner produced the schema represented by revision 0001.
        if "marketplace_cards" in tables and "alembic_version" not in tables:
            command.stamp(config, "0001_initial")

        command.upgrade(config, "head")
        with self._database.engine.connect() as connection:
            after = MigrationContext.configure(connection).get_current_revision()
        return [after] if after and after != before else []
