"""HTTP behaviour of POST /auth/sign-in."""

import pytest
from fastapi.testclient import TestClient

from app.core.security import decode_access_token
from tests.conftest import PASSWORD


def test_valid_credentials_are_exchanged_for_a_token(
    client: TestClient, create_user, settings
) -> None:
    """Spec: Valid credentials are exchanged for a token."""
    user = create_user(username="ada", password=PASSWORD)

    response = client.post(
        "/auth/sign-in", json={"username": "ada", "password": PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert (
        decode_access_token(
            body["access_token"],
            secret_key=settings.auth_secret_key,
            algorithm=settings.auth_algorithm,
        )
        == str(user.id)
    )


def test_issued_token_is_accepted_by_a_protected_endpoint(
    client: TestClient, create_user
) -> None:
    """Spec: ...AND the returned token is accepted by endpoints requiring authentication."""
    create_user(username="ada", password=PASSWORD)

    token = client.post(
        "/auth/sign-in", json={"username": "ada", "password": PASSWORD}
    ).json()["access_token"]

    assert (
        client.get("/users/me", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )


def test_wrong_password_and_unknown_username_are_indistinguishable(
    client: TestClient, create_user
) -> None:
    """Spec: Wrong password / Unknown username."""
    create_user(username="ada", password=PASSWORD)

    wrong_password = client.post(
        "/auth/sign-in", json={"username": "ada", "password": "not the password"}
    )
    unknown_user = client.post(
        "/auth/sign-in", json={"username": "nobody", "password": "not the password"}
    )

    assert wrong_password.status_code == 401
    assert unknown_user.status_code == 401
    # Byte-identical bodies: the endpoint must not reveal which usernames exist.
    assert wrong_password.content == unknown_user.content
    assert wrong_password.headers.get("www-authenticate") == "Bearer"
    assert unknown_user.headers.get("www-authenticate") == "Bearer"
    assert "access_token" not in wrong_password.json()
    assert "access_token" not in unknown_user.json()


def test_inactive_user_cannot_sign_in(client: TestClient, create_user) -> None:
    create_user(username="ada", password=PASSWORD, is_active=False)

    response = client.post(
        "/auth/sign-in", json={"username": "ada", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert "access_token" not in response.json()


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"password": PASSWORD}, id="missing-username"),
        pytest.param({"username": "ada"}, id="missing-password"),
        pytest.param({"username": "", "password": PASSWORD}, id="empty-username"),
        pytest.param({"username": "ada", "password": ""}, id="empty-password"),
        pytest.param({"username": "", "password": ""}, id="both-empty"),
    ],
)
def test_missing_or_empty_credential_fields_are_rejected_as_invalid_input(
    client: TestClient, create_user, payload: dict[str, str]
) -> None:
    """Spec: Missing credential fields."""
    create_user(username="ada", password=PASSWORD)

    response = client.post("/auth/sign-in", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "access_token" not in body
    # The response describes which fields were wrong.
    assert body["detail"]
    reported = {tuple(error["loc"]) for error in body["detail"]}
    assert reported


@pytest.mark.parametrize(
    ("username", "password"),
    [("ada", PASSWORD), ("ada", "wrong password"), ("nobody", "wrong password")],
)
def test_credentials_are_never_echoed_back(
    client: TestClient, create_user, username: str, password: str
) -> None:
    """Spec: Credentials are never echoed back."""
    user = create_user(username="ada", password=PASSWORD)

    response = client.post(
        "/auth/sign-in", json={"username": username, "password": password}
    )

    haystack = response.text + repr(dict(response.headers))
    assert password not in haystack
    assert user.hashed_password not in haystack
