## Why

Three loose ends from the sign-in work, each cheap now and expensive later.

Schema still comes from `Base.metadata.create_all()`, which was accepted with a stated expiry: it
creates missing tables but never alters existing ones, so the first column change against a populated
database drifts silently. Pulling that trigger before any real data exists is the cheapest it will ever
be. Alongside it, there is no repeatable way to populate a development database — `create-user` prompts
for one user at a time, so every developer's local data is different and no test scenario can assume a
known dataset.

Separately, `POST /auth/sign-in` advertises four fields it never reads. `OAuth2PasswordRequestForm`
brings `grant_type`, `scope`, `client_id` and `client_secret` along with the two credentials that
matter, and every one of them shows up in `/docs` as part of the contract. Documenting inputs the
server ignores misleads anyone integrating against it.

## What Changes

- **BREAKING**: `POST /auth/sign-in` accepts **only** `username` and `password`. Any other form field —
  including the `grant_type`, `scope`, `client_id` and `client_secret` it previously tolerated — is
  rejected with `422` and an `extra_forbidden` error naming the field.
- **BREAKING**: consequently the Swagger **Authorize** button in `/docs` stops working. It always sends
  `grant_type=password` plus the client fields, so it will now receive a 422. Obtaining a token for
  manual testing moves to `curl` or the `POST /auth/sign-in` form in the docs page itself.
- Adopt Alembic. Migrations become the only authority for schema; `create_all()` is removed from
  application startup, and the app no longer creates tables as a side effect of booting.
- Add a baseline migration creating the `users` table, matching the current model exactly so an
  existing development database can be stamped rather than rebuilt.
- Add `python -m app.cli seed`: idempotent (re-running changes nothing), refuses to run when
  `ENVIRONMENT` is `staging` or `production`, and creates a known set of development users with fixed
  credentials.
- Update `README.md`, whose Quick start currently tells the reader the Authorize button works and whose
  setup steps predate migrations.

Test-suite schema handling is deliberately unchanged: `tests/conftest.py` keeps building tables from
model metadata, so the existing suite keeps its speed and none of its 62 tests need rewriting.

## Capabilities

### New Capabilities

- `schema-migrations`: how the database schema is versioned and applied — migrations as the single
  source of schema truth, applying and reverting them, and the guarantee that starting the application
  never modifies the schema on its own.
- `data-seeding`: how a non-production database is populated with a known dataset — what seeding
  creates, its idempotence, and the environments where it refuses to run.

### Modified Capabilities

- `user-auth`: the sign-in endpoint's accepted input narrows from "username and password, other fields
  tolerated" to "username and password only". This adds a requirement covering rejection of
  unrecognized fields; the existing requirements keep their current behaviour.

## Impact

**New dependencies**: `alembic`, and `psycopg[binary]` — the driver the configured
`postgresql+psycopg://` URL requires. The project's development database is PostgreSQL 18 (database
`python-fast-api`), configured via `.env`; SQLite remains the code default and is still what the test
suite runs on.

**New files**: `alembic.ini`, `migrations/` (env.py, script template, `versions/`), `app/db/seeds.py`.

**Changed code**:
- `app/auth/dependencies.py` — `get_sign_in_form` is replaced by a `SignInForm` Pydantic form model
  with `extra="forbid"`; its hand-built `RequestValidationError` for blank fields is no longer needed,
  because `min_length=1` on the model produces the same 422 natively.
- `app/auth/router.py` — the path operation's parameter type changes.
- `app/core/lifespan.py` — `create_all()` removed; the lifespan no longer touches the schema.
- `app/cli.py` — gains the `seed` subcommand.

**Operational change**: a database must be migrated before the app can serve requests
(`uv run alembic upgrade head`). The PostgreSQL development database is empty, so it is migrated
normally. A pre-existing SQLite `app.db` built by `create_all()` already has a matching `users` table
and would instead be stamped (`uv run alembic stamp head`).

**Out of scope**: multi-database or async migration support, autogenerate workflow conventions beyond
a documented command, seeding anything other than users, and restoring OAuth2 password-flow
conformance for the sign-in endpoint (the breaking change above is deliberate).
