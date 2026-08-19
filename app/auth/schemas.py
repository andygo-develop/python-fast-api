from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class SignInRequest(BaseModel):
    """The complete accepted input for sign-in: a JSON body, nothing else.

    extra="forbid" makes the published schema the whole contract. The OAuth2
    password-flow parameters this endpoint never read (grant_type, scope,
    client_id, client_secret) are rejected rather than silently ignored, so the
    documented properties are exactly the accepted ones.

    min_length=1 rejects blank credentials as invalid input (422) rather than as
    a failed sign-in (401): an empty username is a malformed request, not a
    wrong guess, and must not be answered by the credential-hiding 401.
    """

    model_config = ConfigDict(extra="forbid")

    username: Annotated[str, Field(min_length=1)]
    password: Annotated[str, Field(min_length=1)]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
