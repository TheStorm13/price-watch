"""Private schemas for historical migrations in the disposable test database."""
import os
from contextlib import contextmanager
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import make_url

from price_watch.infrastructure.postgres import Database, MigrationRunner


@contextmanager
def migration_schema(revision):
    name = 'migration_' + uuid4().hex
    base = Database(os.environ['TEST_DATABASE_URL'])
    db = None
    try:
        with base.engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {name}'))
        try:
            url = make_url(base.url).update_query_dict({'options': '-csearch_path=' + name})
            db = Database(url.render_as_string(hide_password=False))
            config = MigrationRunner(db)._config()
            with patch('logging.config.fileConfig'):
                command.upgrade(config, revision)
            yield db, config
        finally:
            if db is not None:
                db.close()
            with base.engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA {name} CASCADE'))
    finally:
        base.close()
