# fast-api

A FastAPI service with username/password authentication: clients exchange credentials for a
short-lived JWT access token and use it as a bearer token on protected endpoints.

Built on Python 3.14, FastAPI 0.141, Pydantic v2, and SQLAlchemy 2.0 (sync).

## Quick start

```bash
uv sync                                    # install dependencies from uv.lock
cp .env.example .env                       # then edit .env — see Configuration
uv run alembic upgrade head                # create the schema (required before first run)
uv run python -m app.cli seed              # create the development users
uv run fastapi dev main.py                 # http://127.0.0.1:8000
```

The app does not create tables on startup — migrations are the only authority for schema. An
unmigrated database fails at the first query rather than being repaired at boot.

Interactive docs at http://127.0.0.1:8000/docs. Get a token from `POST /auth/sign-in` — in the docs
page or with `curl` — then click **Authorize** and paste it in. Protected endpoints use a plain
bearer scheme, not the OAuth2 password flow, so Authorize just takes the token directly.

Everything is run through `uv run` — the virtualenv is not assumed to be activated.

## API

### `POST /auth/sign-in`

Takes a **JSON** body with `username` and `password` — no other content type is accepted:

```bash
curl -X POST http://127.0.0.1:8000/auth/sign-in \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "<password>"}'
```

```json
{ "access_token": "eyJhbGciOiJIUzI1NiIs...", "token_type": "bearer" }
```

| Outcome | Status |
|---|---|
| Valid credentials | `200` with the token |
| Wrong password, unknown user, or inactive account | `401` — identical response for all three |
| Missing or blank `username`/`password` | `422` naming the offending fields |
| **Any other field**, including `grant_type`, `scope`, `client_id`, `client_secret` | `422 extra_forbidden` naming the field |
| Form-encoded, malformed, or absent body | `422` |

`username` and `password` are the complete accepted input. The endpoint is deliberately not a
conformant OAuth2 token endpoint: the password-flow parameters it never read are now rejected rather
than silently ignored, so the published schema is the whole contract.

Failed sign-ins are deliberately indistinguishable: same status, same body, and the server performs
a password hash verification even when the username does not exist, so response time does not reveal
which usernames are registered.

### `GET /users/me`

```bash
curl http://127.0.0.1:8000/users/me -H "Authorization: Bearer $TOKEN"
```

```json
{ "id": 1, "username": "alice", "is_active": true }
```

Returns `401` with a `WWW-Authenticate: Bearer` header when the token is absent, malformed,
tampered with, expired, or belongs to a user who has since been deleted or deactivated. A valid
signature is never sufficient on its own — the user is always reloaded and re-checked.

## Configuration

Settings are read from environment variables or a `.env` file. Defaults suit local development.

| Variable | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `local` | One of `local`, `test`, `staging`, `production` |
| `AUTH_SECRET_KEY` | `change-me` | JWT signing key. Generate with `openssl rand -hex 32` |
| `AUTH_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `DATABASE_URL` | `sqlite:///./app.db` | Any SQLAlchemy URL. Development uses PostgreSQL via `.env`; the test suite always uses SQLite |

**Outside `ENVIRONMENT=local`, the app refuses to start** if `AUTH_SECRET_KEY` is missing or left at
a placeholder value. This fails at startup rather than at the first sign-in, so a misconfigured
deployment cannot quietly run with a predictable signing key.

Even in local development, generate a real key: HS256 keys shorter than 32 bytes produce an
`InsecureKeyLengthWarning` from PyJWT, and `change-me` is well under that.

## Creating users

There is no registration endpoint. Users come from the command line.

**Seed the development users** — idempotent, so re-running it changes nothing:

```bash
uv run python -m app.cli seed
```

| User | Password | Notes |
|---|---|---|
| `alice` | `password` | active |
| `bob` | `password` | active |
| `carol` | `password` | inactive — useful for testing refusal paths |

Seeding **refuses to run** unless `ENVIRONMENT` is `local` or `test`, checked before any write, so
accounts with a published password cannot reach a deployed environment.

**Create a single user** with a password you choose:

```bash
uv run python -m app.cli create-user <username>
```

It prompts for the password twice, stores an Argon2id hash, and refuses a username that already
exists. Both commands call the same `UserService` a registration endpoint would, so adding one later
is wiring rather than reimplementation.

## Tests

```bash
uv run pytest                                    # full suite (80 tests)
uv run pytest tests/test_sign_in.py              # one file
uv run pytest -k "expired or tampered"           # by name
```

Tests run against a temporary SQLite database and override the `get_db_session` dependency, so they
never touch your development database. Every scenario in the `user-auth` specification has a test
that names it.

> `tests/conftest.py` sets its environment variables **before importing any app module** —
> `app/db/session.py` builds its engine at import time, so a later override would bind the real
> database instead of a throwaway one. Preserve that ordering when adding fixtures.

## Project layout

```
app/
├── main.py              create_app() factory; app = create_app()
├── cli.py               operational commands (create-user)
├── core/
│   ├── config.py        Settings, startup validation
│   ├── lifespan.py      schema creation on startup
│   └── security.py      password hashing + JWT encode/decode (no FastAPI or DB imports)
├── db/
│   ├── base.py          declarative Base
│   └── session.py       engine, SessionLocal, get_db_session dependency
├── users/               models, repository, schemas, service, router
└── auth/                schemas, service, dependencies, router
```

Code is organised by domain, not by technical layer: a new domain gets `app/<domain>/` with the same
file roles. Path operations stay thin — business logic lives in services, queries in repositories,
and collaborators arrive via `Depends()`.

`app/auth/dependencies.py` holds `get_current_user`, the single place a token is verified. A new
protected endpoint depends on it and never handles the token itself.

## Notes for contributors

**Migrations are the only authority for schema.** Alembic lives in `migrations/`, and
`migrations/env.py` takes its URL from the application's own `Settings`, so migrations and the app can
never target different databases.

```bash
uv run alembic upgrade head                        # apply
uv run alembic revision --autogenerate -m "..."    # after changing a model
uv run alembic check                               # report model-vs-migration drift
uv run alembic downgrade -1                        # revert one
```

The test suite builds its schema from model metadata rather than by running migrations — a deliberate
trade for speed. The cost is that a migration which disagrees with the models will not fail the suite,
so **run `alembic check` after changing a model**. `tests/test_migrations.py` executes the migrations
against a scratch database and asserts the resulting columns match `Base.metadata`, which catches the
common case but does not replace that habit.

The project pins its own FastAPI documentation under `.fastapi-harness/` and exposes it over MCP —
worth consulting for version-specific behaviour, since this version documents `pwdlib` and `PyJWT`
rather than the `passlib`/`python-jose` pairing most older tutorials show.

Specifications live in `openspec/specs/`, and completed change proposals — with their design
rationale — are in `openspec/changes/archive/`. `openspec/specs/user-auth/spec.md` is the standing
description of the authentication behaviour described above.

## Not implemented

Deliberately out of scope so far, each a candidate for its own change: user registration over the
API, refresh tokens and revocation, password reset, roles/scopes/permissions, rate limiting and
account lockout, and email verification.
