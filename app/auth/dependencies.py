from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.service import AuthService
from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.users.models import User
from app.users.repository import UserRepository

# A plain bearer scheme rather than OAuth2PasswordBearer: sign-in no longer
# accepts the OAuth2 password-flow fields, so advertising that flow would offer
# /docs an Authorize dialog that cannot work. This one takes the access token
# directly. It answers a missing or non-bearer Authorization header with 401
# and WWW-Authenticate: Bearer, which is what the spec requires.
bearer_scheme = HTTPBearer()

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_user_repository(
    session: Annotated[Session, Depends(get_db_session)],
) -> UserRepository:
    return UserRepository(session)


def get_auth_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(users, settings)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    subject = decode_access_token(
        credentials.credentials,
        secret_key=settings.auth_secret_key,
        algorithm=settings.auth_algorithm,
    )
    if subject is None:
        raise CREDENTIALS_EXCEPTION
    try:
        user_id = int(subject)
    except ValueError:
        raise CREDENTIALS_EXCEPTION from None

    user = users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_EXCEPTION
    return user
