"""Spec: schema-migrations.

The suite builds its own schema from model metadata (a deliberate choice for
speed), so these tests are the one place migrations are actually executed.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings
from app.db.base import Base

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def scratch_db(tmp_path: Path):
    """A database that only the migrations touch.

    env.py resolves the URL through get_settings(), which is lru_cached, so the
    cache must be cleared on the way in and out or the migration would target
    the suite's own database.
    """
    url = f"sqlite:///{tmp_path / 'migrated.db'}"
    previous = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()

    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    try:
        yield config, url
    finally:
        os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def test_applying_migrations_builds_the_expected_schema(scratch_db) -> None:
    """Spec: Applying migrations builds the schema."""
    config, url = scratch_db

    command.upgrade(config, "head")

    inspector = inspect(create_engine(url))
    assert "users" in inspector.get_table_names()

    migrated = {column["name"] for column in inspector.get_columns("users")}
    declared = {column.name for column in Base.metadata.tables["users"].columns}
    assert migrated == declared, "migration schema has drifted from the model"

    indexed = {tuple(i["column_names"]) for i in inspector.get_indexes("users")}
    assert ("username",) in indexed


def test_migrations_can_be_reverted(scratch_db) -> None:
    """Spec: A migration can be reverted."""
    config, url = scratch_db
    command.upgrade(config, "head")

    command.downgrade(config, "base")

    assert "users" not in inspect(create_engine(url)).get_table_names()


def test_applying_migrations_twice_is_safe(scratch_db) -> None:
    """Spec: Applying migrations twice is safe."""
    config, url = scratch_db
    command.upgrade(config, "head")

    command.upgrade(config, "head")

    assert "users" in inspect(create_engine(url)).get_table_names()


def test_migrations_honour_the_configured_database(scratch_db) -> None:
    """Spec: Migrations honour the configured database."""
    config, url = scratch_db

    command.upgrade(config, "head")

    # Built where DATABASE_URL pointed, not in any default location.
    assert Path(url.removeprefix("sqlite:///")).exists()
    assert not (PROJECT_ROOT / "app.db").exists()
