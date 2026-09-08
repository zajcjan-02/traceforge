import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://traceforge:traceforge@127.0.0.1:5433/traceforge_test",
)

from traceforge.database import engine


@pytest.fixture(scope="session", autouse=True)
def migrate_database():
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
def clear_database():
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE traces, services RESTART IDENTITY CASCADE"))
