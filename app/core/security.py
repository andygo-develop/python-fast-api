"""Password hashing and access-token primitives.

Deliberately free of FastAPI, SQLAlchemy and settings imports: everything it
needs arrives as an argument, so it can be tested without an app or a database.
"""

import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

# Argon2id at the library's recommended parameters. The encoded hash carries
# its own algorithm, parameters and per-hash salt, so no separate salt column
# is needed and two equal passwords never produce equal stored values.
_password_hash = PasswordHash.recommended()

# Verifying an unknown username against this costs the same as verifying a real
# one, which keeps sign-in from leaking which usernames exist via response time
# (design.md, Decision 4). The input is random per process and never matches.
_DUMMY_HASH = _password_hash.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _password_hash.verify(password, hashed_password)


def verify_dummy_password(password: str) -> bool:
    """Burn one verification against a throwaway hash. Always False."""
    return _password_hash.verify(password, _DUMMY_HASH)


def create_access_token(
    subject: str,
    *,
    secret_key: str,
    algorithm: str,
    expires_delta: timedelta,
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def decode_access_token(token: str, *, secret_key: str, algorithm: str) -> str | None:
    """Return the token's subject, or None if it is unusable for any reason.

    Bad signature, malformed structure and expiry all collapse to None on
    purpose: callers must not be able to tell them apart, and neither must the
    clients they answer.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
    except InvalidTokenError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        return None
    return subject
