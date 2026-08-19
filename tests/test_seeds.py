"""Spec: data-seeding."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import cli
from app.core.config import Settings
from app.db.seeds import SEED_PASSWORD, SEED_USERS, run_seeds
from app.users.models import User


def _user_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(User))


def test_seeding_an_empty_database_creates_the_documented_users(
    db_session: Session,
) -> None:
    """Spec: Seeding an empty database."""
    result = run_seeds(db_session)

    assert set(result.created) == {seed.username for seed in SEED_USERS}
    assert result.skipped == ()
    assert _user_count(db_session) == len(SEED_USERS)


def test_seeded_users_can_sign_in(
    db_session: Session, client: TestClient
) -> None:
    """Spec: ...AND each seeded user can sign in with the documented password."""
    run_seeds(db_session)

    active = [seed for seed in SEED_USERS if seed.is_active]
    assert active, "expected at least one active seed user"
    for seed in active:
        response = client.post(
            "/auth/sign-in",
            json={"username": seed.username, "password": SEED_PASSWORD},
        )
        assert response.status_code == 200, seed.username
        assert response.json()["access_token"]


def test_seeding_twice_changes_nothing(db_session: Session) -> None:
    """Spec: Seeding twice."""
    run_seeds(db_session)
    count_after_first = _user_count(db_session)

    second = run_seeds(db_session)

    assert second.created == ()
    assert set(second.skipped) == {seed.username for seed in SEED_USERS}
    assert _user_count(db_session) == count_after_first


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_seeding_is_blocked_in_deployed_environments(
    db_session: Session, monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    """Spec: Seeding is blocked in a deployed environment."""
    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(environment=environment, auth_secret_key="s" * 64),
    )

    exit_code = cli.seed_command()

    assert exit_code != 0
    assert _user_count(db_session) == 0


@pytest.mark.parametrize("environment", ["local", "test"])
def test_seeding_is_permitted_in_development(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    """Spec: Seeding is permitted in development."""
    monkeypatch.setattr(
        cli,
        "get_settings",
        lambda: Settings(environment=environment, auth_secret_key="s" * 64),
    )

    assert cli.seed_command() == 0
