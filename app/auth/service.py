from datetime import timedelta

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    verify_dummy_password,
    verify_password,
)
from app.users.models import User
from app.users.repository import UserRepository


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    def authenticate(self, username: str, password: str) -> User | None:
        """Return the user for these credentials, or None.

        Every rejection path costs one Argon2 verification, so an unknown
        username is not distinguishable from a wrong password by response time.
        The caller must not report *why* it failed.
        """
        user = self._users.get_by_username(username)
        if user is None:
            verify_dummy_password(password)
            return None
        if not verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    def issue_access_token(self, user: User) -> str:
        return create_access_token(
            str(user.id),
            secret_key=self._settings.auth_secret_key,
            algorithm=self._settings.auth_algorithm,
            expires_delta=timedelta(
                minutes=self._settings.access_token_expire_minutes
            ),
        )
