"""Spec: Stored credential is not reversible / Identical passwords hash differently."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import PASSWORD


def test_stored_credential_is_a_hash_not_the_password(create_user, db_session: Session) -> None:
    user = create_user(username="ada", password=PASSWORD)

    stored = db_session.execute(
        text("SELECT hashed_password FROM users WHERE id = :id"), {"id": user.id}
    ).scalar_one()

    assert stored != PASSWORD
    assert PASSWORD not in stored
    # The encoded hash names its algorithm and parameters.
    assert stored.startswith("$argon2id$")
    assert "m=" in stored and "t=" in stored and "p=" in stored


def test_two_users_with_the_same_password_store_different_hashes(create_user) -> None:
    ada = create_user(username="ada", password=PASSWORD)
    grace = create_user(username="grace", password=PASSWORD)

    assert ada.hashed_password != grace.hashed_password
