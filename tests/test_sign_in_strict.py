"""Spec: Rejection of unrecognized sign-in fields."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.conftest import PASSWORD


def test_an_unrecognized_field_is_rejected(client: TestClient, create_user) -> None:
    """Spec: An unrecognized field is rejected."""
    create_user(username="ada", password=PASSWORD)

    response = client.post(
        "/auth/sign-in",
        json={"username": "ada", "password": PASSWORD, "surprise": "value"},
    )

    assert response.status_code == 422
    body = response.json()
    # The offending field is named.
    assert any("surprise" in error["loc"] for error in body["detail"])
    # Correct credentials are not enough to get a token through a bad request.
    assert "access_token" not in body


@pytest.mark.parametrize(
    "field", ["grant_type", "scope", "client_id", "client_secret"]
)
def test_previously_tolerated_oauth2_parameters_are_rejected(
    client: TestClient, create_user, field: str
) -> None:
    """Spec: Previously tolerated OAuth2 parameters are rejected."""
    create_user(username="ada", password=PASSWORD)

    response = client.post(
        "/auth/sign-in",
        json={"username": "ada", "password": PASSWORD, field: "password"},
    )

    assert response.status_code == 422
    assert any(field in error["loc"] for error in response.json()["detail"])


def test_only_the_two_credential_fields_are_published(app: FastAPI) -> None:
    """Spec: Only the two credential fields are published."""
    schema = app.openapi()
    body = schema["paths"]["/auth/sign-in"]["post"]["requestBody"]
    ref = body["content"]["application/json"]["schema"]["$ref"]
    model = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]

    assert set(model["properties"]) == {"username", "password"}
    assert model["additionalProperties"] is False


def test_exactly_the_two_fields_still_succeed(client: TestClient, create_user) -> None:
    """Spec: Exactly the two credential fields still succeed."""
    create_user(username="ada", password=PASSWORD)

    response = client.post(
        "/auth/sign-in", json={"username": "ada", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["token_type"] == "bearer"
