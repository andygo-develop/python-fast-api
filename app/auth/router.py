from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_auth_service
from app.auth.schemas import SignInRequest, Token
from app.auth.service import AuthService

router = APIRouter()


@router.post("/sign-in", response_model=Token)
def sign_in(
    credentials: SignInRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> Token:
    user = auth_service.authenticate(credentials.username, credentials.password)
    if user is None:
        # Identical for an unknown username and a wrong password: the response
        # must not tell an attacker which usernames exist.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=auth_service.issue_access_token(user))
