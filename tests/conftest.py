"""Test fixtures.

Environment variables are set before any app module is imported: the engine in
app.db.session is built at import time from Settings, so a late override would
bind the real database instead of a throwaway one.
"""

import os
import tempfile

_TMP_DIR = tempfile.mkdtemp(prefix="fast-api-tests-")
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTH_SECRET_KEY"] = "t" * 64
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DIR}/test.db"

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine, get_db_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.users.models import User  # noqa: E402
from app.users.repository import UserRepository  # noqa: E402
from app.users.service import UserService  # noqa: E402

PASSWORD = "correct horse battery staple"


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.execute(delete(User))
        session.commit()
    finally:
        session.close()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def app(db_session: Session) -> FastAPI:
    application = create_app()
    # The request handler must see the same session the test wrote through,
    # so rows created in the test are visible to the endpoint.
    application.dependency_overrides[get_db_session] = lambda: db_session
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def create_user(db_session: Session):
    def _create_user(
        username: str = "ada",
        password: str = PASSWORD,
        is_active: bool = True,
    ) -> User:
        user = UserService(UserRepository(db_session)).create_user(username, password)
        if not is_active:
            user.is_active = False
            db_session.commit()
            db_session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def signed_in_token(client: TestClient, create_user) -> str:
    create_user()
    response = client.post(
        "/auth/sign-in", json={"username": "ada", "password": PASSWORD}
    )
    return response.json()["access_token"]
