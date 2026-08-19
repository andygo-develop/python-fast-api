"""Development seed data.

Seeding goes through UserService, the same path the CLI and any future
registration endpoint use, so seeded users are hashed identically to real ones
and there is no second creation path to drift.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.users.repository import UserRepository
from app.users.service import UserService

# Published, development-only credential. The seed command refuses to run
# outside local/test precisely because this is public knowledge.
SEED_PASSWORD = "password"


@dataclass(frozen=True)
class SeedUser:
    username: str
    password: str = SEED_PASSWORD
    is_active: bool = True


SEED_USERS: tuple[SeedUser, ...] = (
    SeedUser(username="alice"),
    SeedUser(username="bob"),
    SeedUser(username="carol", is_active=False),
)


@dataclass(frozen=True)
class SeedResult:
    created: tuple[str, ...]
    skipped: tuple[str, ...]


def run_seeds(session: Session) -> SeedResult:
    """Create the seed users that do not exist yet.

    Idempotent by lookup rather than by database-level conflict handling, so it
    behaves identically on SQLite and PostgreSQL and can report precisely what
    it did.
    """
    users = UserRepository(session)
    service = UserService(users)

    created: list[str] = []
    skipped: list[str] = []

    for seed in SEED_USERS:
        if users.get_by_username(seed.username) is not None:
            skipped.append(seed.username)
            continue
        user = service.create_user(seed.username, seed.password)
        if not seed.is_active:
            user.is_active = False
            session.commit()
        created.append(seed.username)

    return SeedResult(created=tuple(created), skipped=tuple(skipped))
