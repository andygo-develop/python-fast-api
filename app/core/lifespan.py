from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup and shutdown.

    Deliberately does not touch the database schema. Migrations are the only
    authority for schema (`alembic upgrade head`); creating tables here would
    let a forgotten migration pass unnoticed in one environment and fail in
    another. An unmigrated database is meant to fail loudly at the first query.

    Kept as the place resources with a startup/shutdown lifetime will be wired.
    """
    yield
