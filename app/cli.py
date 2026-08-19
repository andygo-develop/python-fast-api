"""Operational commands.

Registration is not exposed over the API, so this is how a user gets created:

    uv run python -m app.cli create-user <username>
    uv run python -m app.cli seed

Both call the same UserService a registration endpoint would, so adding that
endpoint later is wiring, not reimplementation.
"""

import argparse
import sys
from getpass import getpass

from app.core.config import get_settings
from app.db.seeds import SEED_PASSWORD, run_seeds
from app.db.session import SessionLocal
from app.users.repository import UserRepository
from app.users.service import UsernameAlreadyExistsError, UserService

# Seeding is permitted only in these environments. An allow-list, so an
# environment added to Settings later is refused by default rather than
# accidentally permitted.
SEEDABLE_ENVIRONMENTS = frozenset({"local", "test"})


def create_user_command(username: str) -> int:
    password = getpass("Password: ")
    if password != getpass("Confirm password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1
    if not password.strip():
        print("Password must not be blank.", file=sys.stderr)
        return 1

    session = SessionLocal()
    try:
        user = UserService(UserRepository(session)).create_user(username, password)
    except UsernameAlreadyExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        session.close()

    print(f"Created user {user.username!r} (id={user.id}).")
    return 0


def seed_command() -> int:
    environment = get_settings().environment
    if environment not in SEEDABLE_ENVIRONMENTS:
        # Checked before any write, so a refused seed cannot leave a partial
        # one behind. Seed users have a published password.
        print(
            f"Refusing to seed: ENVIRONMENT is {environment!r}. "
            f"Seeding is permitted only in {sorted(SEEDABLE_ENVIRONMENTS)}.",
            file=sys.stderr,
        )
        return 1

    session = SessionLocal()
    try:
        result = run_seeds(session)
    finally:
        session.close()

    if result.created:
        print(f"Created: {', '.join(result.created)} (password: {SEED_PASSWORD!r})")
    if result.skipped:
        print(f"Already present, unchanged: {', '.join(result.skipped)}")
    if not result.created:
        print("Nothing to do.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    subcommands = parser.add_subparsers(dest="command", required=True)
    create_user = subcommands.add_parser("create-user", help="Create a user")
    create_user.add_argument("username")
    subcommands.add_parser("seed", help="Create the development seed users")

    args = parser.parse_args(argv)
    if args.command == "create-user":
        return create_user_command(args.username)
    if args.command == "seed":
        return seed_command()
    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
