from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)

KEY = "k" * 64
OTHER_KEY = "o" * 64
ALGORITHM = "HS256"


def _token(subject: str = "42", minutes: int = 5, key: str = KEY) -> str:
    return create_access_token(
        subject,
        secret_key=key,
        algorithm=ALGORITHM,
        expires_delta=timedelta(minutes=minutes),
    )


def test_hash_is_not_the_plaintext_and_names_its_algorithm() -> None:
    hashed = hash_password("hunter2")

    assert hashed != "hunter2"
    assert "hunter2" not in hashed
    assert hashed.startswith("$argon2id$")


def test_same_password_hashes_to_different_values() -> None:
    assert hash_password("hunter2") != hash_password("hunter2")


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [("hunter2", True), ("hunter3", False), ("", False)],
)
def test_verify_password(candidate: str, expected: bool) -> None:
    assert verify_password(candidate, hash_password("hunter2")) is expected


def test_dummy_verification_always_fails() -> None:
    assert verify_dummy_password("anything at all") is False


def test_token_round_trips_to_its_subject() -> None:
    assert decode_access_token(_token("42"), secret_key=KEY, algorithm=ALGORITHM) == "42"


def test_token_signed_with_a_different_key_is_rejected() -> None:
    token = _token(key=OTHER_KEY)

    assert decode_access_token(token, secret_key=KEY, algorithm=ALGORITHM) is None


def test_expired_token_is_rejected() -> None:
    token = _token(minutes=-1)

    assert decode_access_token(token, secret_key=KEY, algorithm=ALGORITHM) is None


@pytest.mark.parametrize("token", ["", "not-a-token", "a.b.c", "x" * 40])
def test_malformed_token_is_rejected(token: str) -> None:
    assert decode_access_token(token, secret_key=KEY, algorithm=ALGORITHM) is None


def test_tampered_payload_is_rejected() -> None:
    header, payload, signature = _token("42").split(".")
    forged_payload = create_access_token(
        "99", secret_key=OTHER_KEY, algorithm=ALGORITHM, expires_delta=timedelta(minutes=5)
    ).split(".")[1]

    tampered = f"{header}.{forged_payload}.{signature}"

    assert decode_access_token(tampered, secret_key=KEY, algorithm=ALGORITHM) is None
