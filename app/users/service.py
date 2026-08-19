from app.core.security import hash_password
from app.users.models import User
from app.users.repository import UserRepository


class UsernameAlreadyExistsError(Exception):
    def __init__(self, username: str) -> None:
        super().__init__(f"username {username!r} is already taken")
        self.username = username


class UserService:
    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def create_user(self, username: str, password: str) -> User:
        if self._users.get_by_username(username) is not None:
            raise UsernameAlreadyExistsError(username)
        return self._users.add(
            User(username=username, hashed_password=hash_password(password))
        )
