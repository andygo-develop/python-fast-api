"""HTTP behaviour of GET /users/me and the token it requires."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.users.models import User
from tests.conftest import PASSWORD


def test_valid_token_resolves_to_its_user(
    client: TestClient, create_user, signed_in_token: str
) -> None:
    """Spec: Valid token resolves to its user."""
    response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {signed_in_token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "ada"
    assert body["is_active"] is True
    assert set(body) == {"id", "username", "is_active"}
    # No password material under any field name.
    assert "password" not in response.text.lower()
    assert "argon2" not in response.text


def test_missing_authorization_header_is_refused(client: TestClient) -> None:
    """Spec: No token supplied."""
    response = client.get("/users/me")

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("not-a-token", id="not-a-jwt"),
        pytest.param("a.b.c", id="wrong-shape"),
        pytest.param("", id="empty"),
    ],
)
def test_malformed_token_is_refused(client: TestClient, token: str) -> None:
    """Spec: Malformed or tampered token."""
    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_token_signed_with_a_foreign_key_is_refused(
    client: TestClient, create_user
) -> None:
    """Spec: Malformed or tampered token."""
    user = create_user()
    forged = create_access_token(
        str(user.id),
        secret_key="f" * 64,
        algorithm="HS256",
        expires_delta=timedelta(minutes=30),
    )

    response = client.get("/users/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert "signature" not in response.text.lower()


def test_tampered_payload_is_refused(
    client: TestClient, create_user, signed_in_token: str
) -> None:
    """Spec: Malformed or tampered token."""
    other = create_user(username="mallory")
    header, _, signature = signed_in_token.split(".")
    forged_payload = create_access_token(
        str(other.id),
        secret_key="f" * 64,
        algorithm="HS256",
        expires_delta=timedelta(minutes=30),
    ).split(".")[1]

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {header}.{forged_payload}.{signature}"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize("expired_by", [timedelta(seconds=-1), timedelta(days=-1)])
def test_expired_token_is_refused(
    client: TestClient, create_user, settings, expired_by: timedelta
) -> None:
    """Spec: Expired token — refused no matter how recently it expired."""
    user = create_user()
    expired = create_access_token(
        str(user.id),
        secret_key=settings.auth_secret_key,
        algorithm=settings.auth_algorithm,
        expires_delta=expired_by,
    )

    response = client.get("/users/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_token_for_a_deleted_user_is_refused(
    client: TestClient, db_session: Session, signed_in_token: str
) -> None:
    """Spec: Token for a user that no longer exists or is inactive."""
    headers = {"Authorization": f"Bearer {signed_in_token}"}
    assert client.get("/users/me", headers=headers).status_code == 200

    db_session.execute(delete(User).where(User.username == "ada"))
    db_session.commit()

    assert client.get("/users/me", headers=headers).status_code == 401
    # Refused on every subsequent request, not just the first.
    assert client.get("/users/me", headers=headers).status_code == 401


def test_token_for_a_deactivated_user_is_refused(
    client: TestClient, create_user, db_session: Session, settings
) -> None:
    """Spec: Token for a user that no longer exists or is inactive."""
    user = create_user()
    token = create_access_token(
        str(user.id),
        secret_key=settings.auth_secret_key,
        algorithm=settings.auth_algorithm,
        expires_delta=timedelta(minutes=30),
    )
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/users/me", headers=headers).status_code == 200

    user.is_active = False
    db_session.commit()

    assert client.get("/users/me", headers=headers).status_code == 401
    assert client.get("/users/me", headers=headers).status_code == 401
