from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Values that mean "nobody has set a real signing key yet". Starting a
# non-local environment with any of these is refused rather than tolerated:
# a predictable key lets anyone mint tokens for any user.
PLACEHOLDER_SECRETS = frozenset(
    {"", "change-me", "changeme", "secret", "string", "your-secret-key"}
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["local", "test", "staging", "production"] = "local"

    auth_secret_key: str = "change-me"
    auth_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    database_url: str = "sqlite:///./app.db"

    @model_validator(mode="after")
    def _reject_placeholder_secret(self) -> "Settings":
        if self.environment == "local":
            return self
        if self.auth_secret_key.strip() in PLACEHOLDER_SECRETS:
            raise ValueError(
                "AUTH_SECRET_KEY is missing or still set to a placeholder value, "
                f"which is not allowed when ENVIRONMENT is {self.environment!r}. "
                "Generate one with: openssl rand -hex 32"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
