"""Spec: Signing key configuration."""

from datetime import datetime, timezone

import jwt
import pytest
from pydantic import ValidationError

from app.auth.service import AuthService
from app.core.config import Settings
from app.users.models import User

REAL_KEY = "r" * 64


@pytest.mark.parametrize("environment", ["test", "staging", "production"])
@pytest.mark.parametrize("secret", ["", "change-me", "changeme", "secret", "   "])
def test_placeholder_secret_is_refused_outside_local(
    environment: str, secret: str
) -> None:
    """Spec: Missing signing key outside local development."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(environment=environment, auth_secret_key=secret)

    # The error names the offending setting so the failure is actionable.
    assert "AUTH_SECRET_KEY" in str(exc_info.value)


@pytest.mark.parametrize("secret", ["", "change-me"])
def test_placeholder_secret_is_permitted_in_local(secret: str) -> None:
    assert Settings(environment="local", auth_secret_key=secret).environment == "local"


@pytest.mark.parametrize("environment", ["local", "test", "staging", "production"])
def test_real_secret_is_accepted_everywhere(environment: str) -> None:
    settings = Settings(environment=environment, auth_secret_key=REAL_KEY)

    assert settings.auth_secret_key == REAL_KEY


def test_token_lifetime_follows_configuration() -> None:
    """Spec: Token lifetime is configurable."""
    lifetimes = {}
    for minutes in (5, 120):
        settings = Settings(
            environment="test",
            auth_secret_key=REAL_KEY,
            access_token_expire_minutes=minutes,
        )
        token = AuthService(users=None, settings=settings).issue_access_token(
            User(id=1, username="ada", hashed_password="x", is_active=True)
        )
        claims = jwt.decode(token, REAL_KEY, algorithms=["HS256"])
        lifetimes[minutes] = claims["exp"] - claims["iat"]

    assert lifetimes[5] == 5 * 60
    assert lifetimes[120] == 120 * 60


def test_issued_token_expiry_is_in_the_future() -> None:
    settings = Settings(
        environment="test", auth_secret_key=REAL_KEY, access_token_expire_minutes=30
    )
    token = AuthService(users=None, settings=settings).issue_access_token(
        User(id=1, username="ada", hashed_password="x", is_active=True)
    )

    claims = jwt.decode(token, REAL_KEY, algorithms=["HS256"])

    assert claims["sub"] == "1"
    assert claims["exp"] > datetime.now(timezone.utc).timestamp()
