# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

One capability is implemented: username/password authentication (`user-auth`). `app/` holds the
application, root `main.py` is a thin re-export of `app.main:app`, and `tests/` covers the auth
surface. New domains follow the same package shape — see Architecture.

Stack (verified in this checkout, not assumed):

- Python 3.14.5 (`requires-python >=3.14`)
- FastAPI 0.141.1 with the `[standard]` extra (brings `fastapi` CLI, uvicorn, httpx, email-validator)
- Pydantic **v2** (2.13.4) — use `model_config = ConfigDict(...)`, `model_dump()`, `@field_validator`;
  never v1 syntax
- SQLAlchemy 2.0 (typed `Mapped`/`mapped_column`), sync engine and `Session`
- `pyjwt` (HS256) and `pwdlib[argon2]` — this FastAPI version's docs specify these, *not* the
  `passlib`/`python-jose` pairing most older tutorials show
- `uv` for dependency and virtualenv management (`uv.lock` is committed)

## Commands

```bash
uv sync                                  # install/refresh .venv from uv.lock
uv run fastapi dev main.py               # dev server with reload
uv run fastapi run main.py               # production-style server
uv run pytest                            # full suite
uv run pytest tests/test_sign_in.py      # one file
uv run pytest -k "expired or tampered"   # by name
uv run pytest tests/test_sign_in.py::test_wrong_password_and_unknown_username_are_indistinguishable
uv run python -m app.cli create-user <username>   # only way to create a user; no signup endpoint
uv add <pkg> / uv add --dev <pkg>        # add a runtime / dev-only dependency
```

Prefix anything Python with `uv run` — the venv is not assumed to be activated.

No linter or formatter is installed; project conventions expect `ruff` when one is wanted.

Tests set `ENVIRONMENT`, `AUTH_SECRET_KEY` and a temp-file `DATABASE_URL` at the *top of
`tests/conftest.py`, before importing any app module* — `app/db/session.py` builds its engine at
import time, so a later override binds the real database instead of a throwaway one. Keep that
ordering if you add fixtures.

## FastAPI documentation MCP (`fastapi-docs`)

This repo ships a documentation harness pinned to its exact FastAPI version. The manuals live in
`.fastapi-harness/manuals/fastapi-0.141.1/` with a BM25 SQLite index; the MCP server is started via
`npx @andygo.dev/fastapi-harness mcp start` (see `.mcp.json`, enabled in `.claude/settings.local.json`).

**Look up uncertain framework APIs there instead of recalling them** — `search_fastapi_manual`,
`get_fastapi_manual`, `search_fastapi_api`. FastAPI's surface and the Pydantic/SQLAlchemy/Starlette
ecosystem around it move independently, and version-specific behaviour (dependency caching, lifespan,
validators) is exactly where memory is wrong. If the MCP reports the docs are out of sync, tell the
user to run `fastapi-harness manuals update`.

`search_project_specs` / `get_project_spec` query a *separate* corpus — this project's own design notes.
It is currently disabled (`specs.enabled: false` in `.fastapi-harness/config.json`), so those tools
return nothing until specs exist and the flag is flipped. Never present a project spec as framework
behaviour or vice versa.

## Architecture conventions

Full guidance lives in the `fastapi` skill (`.claude/skills/fastapi/SKILL.md` plus `references/`);
load it for any non-trivial FastAPI work. The load-bearing points:

- **Organise by domain, not by layer.** The existing layout is the template for a new domain:

  ```
  app/
  ├── main.py                     create_app(); app = create_app()
  ├── cli.py                      operational commands (create-user)
  ├── core/{config,lifespan,security}.py
  ├── db/{base,session}.py        declarative Base, engine, get_db_session
  ├── users/{models,repository,schemas,service,router}.py
  └── auth/{schemas,service,dependencies,router}.py
  ```

  Add `app/<domain>/` with the same file roles — never `app/routers/` + `app/schemas/` + `app/services/`.
- **Request flow / layer ownership:** middleware → routing → `Depends()` → Pydantic validation →
  thin path operation → service (business logic) → repository (persistence) → `response_model`
  serialization → exception handlers.
- **Path operations stay thin** (~20 lines); they coordinate and pick a response shape. Business logic
  lives in services, queries in repositories.
- **Collaborators arrive via `Depends()`** — no module-level singletons or globals reached for inside
  domain code.
- **Never bind a request body onto an ORM model** (`Model(**body.model_dump())`) and never return an
  ORM model from a handler — separate `...Create`/`...Update` input schemas and a `...Read`
  `response_model` are the mass-assignment and over-exposure defences.
- **App factory + `lifespan`**, one `Settings` class from `pydantic-settings` driven by env/`.env` —
  not `config_dev.py`/`config_prod.py`.
- **Absolute imports** from the app package root; avoid re-exporting `__init__.py` files.
- **This project is sync throughout** — `def` path operations, sync `Session`. FastAPI runs sync
  handlers in a threadpool, which is what keeps CPU-bound Argon2 verification from stalling the event
  loop. Do not introduce an `async def` handler over the sync session without reading design
  Decision 1 in `openspec/changes/archive/2026-08-19-add-user-sign-in/design.md` first.

## Authentication

Implemented per `openspec/changes/archive/2026-08-19-add-user-sign-in/` and
`openspec/changes/switch-sign-in-to-json/`. The shape to preserve:

- `POST /auth/sign-in` takes a JSON body (`SignInRequest`: `username`, `password`) and returns
  `{access_token, token_type}`. Form-encoded, malformed, or absent bodies are `422`.
  `GET /users/me` is the worked example of a protected route.
- **`get_current_user` (`app/auth/dependencies.py`) is the only place a token is verified.** A new
  protected endpoint depends on it and never touches the token itself.
- JWT claims are `sub` (user **id** as a string), `iat`, `exp`. `sub` holds the id, not the username,
  so a later username change cannot transfer a live token to a different identity. Verification still
  loads the user — deleted and `is_active=False` users are refused even with a validly signed token.
- **Every auth failure returns the same generic 401 with `WWW-Authenticate: Bearer`.** Unknown
  username and wrong password are byte-identical by design, and `AuthService.authenticate` verifies
  against a dummy hash when no user is found so the two paths cost the same time. Do not add a
  message, status, or timing difference that distinguishes them.
- **Sign-in accepts only `username` and `password`.** `SignInRequest` sets `extra="forbid"`, so any
  other field — including the OAuth2 `grant_type`, `scope`, `client_id`, `client_secret` — is a
  `422 extra_forbidden`; do not "fix" this by loosening the model. Blank credentials are also a 422,
  from `min_length=1` on the same model. `GET /users/me` uses a plain `HTTPBearer` scheme rather than
  `OAuth2PasswordBearer`, so `/docs` Authorize takes a pasted token directly.
- `app/core/security.py` imports no FastAPI, SQLAlchemy, or settings: keys and algorithms arrive as
  arguments. Keep it that way — it is the layer worth testing exhaustively.
- Settings refuse a missing or placeholder `AUTH_SECRET_KEY` unless `ENVIRONMENT=local`, at
  construction rather than at first sign-in.

**Migrations own the schema; startup does not touch it.** `app/core/lifespan.py` deliberately
creates nothing — an unmigrated database fails at the first query instead of being silently repaired
at boot. Alembic lives in `migrations/`, and `migrations/env.py` reads the URL from `Settings` rather
than `alembic.ini` (whose `sqlalchemy.url` is intentionally empty) so the two can never diverge.
`render_as_batch=True` stays on because SQLite cannot `ALTER TABLE`.

**Tests build their schema from model metadata, not from migrations** — a deliberate speed trade. So
a migration that drifts from the models will not fail the suite: run `uv run alembic check` after
changing a model. `tests/test_migrations.py` executes migrations against a scratch database and
compares columns to `Base.metadata`, which catches the common case but is not a substitute.

**Development runs on PostgreSQL** (`DATABASE_URL` in `.env`, database `python-fast-api`, driver
`psycopg`). SQLite is still the code default and is what the test suite uses, so migrations must work
on both.

## Subagents

Project-scoped agents in `.claude/agents/` wrap the same doc-verification discipline. Use
`fastapi-planner` before substantial features or refactors, `fastapi-expert` for implementation,
`fastapi-test-writer` for test work, and `fastapi-code-reviewer` after changing FastAPI code.

## OpenSpec workflow

`openspec/` uses the `spec-driven` schema (openspec CLI 1.9.0 on PATH; `openspec/config.yaml` has no
project context or custom rules filled in yet). Changes are planned as artifacts — `proposal.md`,
`specs/<capability>/spec.md` deltas, `design.md`, `tasks.md` — before code is written.

`/opsx:propose` and `/opsx:new` (and the `openspec-*` skills) are **planning-only**: they must not edit
project code, and implementation waits for an explicit follow-up request that runs `/opsx:apply`.
Other entry points: `/opsx:continue`, `/opsx:verify`, `/opsx:archive`.
