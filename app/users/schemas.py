from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    """What the API exposes about a user — an allow-list, not the ORM row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_active: bool
