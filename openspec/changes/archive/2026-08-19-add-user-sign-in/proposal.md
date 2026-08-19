## Why

The project is a bare scaffold with no application package, no persistence and no notion of a user, so
every future endpoint that needs to know *who* is calling is blocked. Establishing authentication first
sets the identity primitive that later capabilities depend on, and forces the foundational decisions
(app factory, settings, DB session dependency, layering) to be made once, deliberately, rather than
accreting around whichever feature happens to land first.

## What Changes

- Add `POST /auth/sign-in`: accepts OAuth2 password-flow form credentials (`username`, `password`) and
  returns a signed JWT access token as `{access_token, token_type: "bearer"}`.
- Add a `users` table and `User` ORM model storing an Argon2 password hash — never a plaintext or
  reversibly-encrypted password.
- Add a `get_current_user` dependency that verifies the bearer token and resolves it to a user, and
  `GET /users/me` as the first endpoint consuming it, proving the issued token is usable end to end.
- Stand up the application skeleton this requires: `create_app()` factory, `Settings`
  (pydantic-settings) carrying the JWT secret and token lifetime, a request-scoped SQLAlchemy session
  dependency, and a `UserRepository`.
- Add a way to create a user outside the API (seed/CLI helper), since registration is explicitly out of
  scope but the login route is untestable without at least one user.
- Replace the PyCharm placeholder in `main.py` with the real ASGI entrypoint.

Not breaking: nothing exists to break yet.

## Capabilities

### New Capabilities
- `user-auth`: credential authentication and access-token issuance — how a caller exchanges a username
  and password for a bearer token, how that token is verified on subsequent requests, and how an
  authenticated caller retrieves their own identity. Covers the failure modes (bad credentials,
  expired/malformed/missing token) as observable behaviour.

### Modified Capabilities

None — this is the first capability in the project.

## Impact

**New dependencies** (verified against the pinned FastAPI 0.141.1 manuals, which document these
specific packages rather than the older `passlib`/`python-jose` pairing):

- `pyjwt` — JWT signing and verification (HS256)
- `pwdlib[argon2]` — password hashing; Argon2 is the algorithm the docs recommend
- `sqlalchemy` — ORM and session management
- `pydantic-settings` — typed configuration
- dev: `pytest`, `pytest-asyncio` (httpx already ships with `fastapi[standard]`)

**New code**: `app/` package replacing the placeholder `main.py` — `app/core/` (config, lifespan),
`app/db/` (declarative base, session dependency), `app/users/` (model, repository, schemas, `/users/me`
router), `app/auth/` (router, schemas, service, security helpers, `get_current_user`).

**Configuration**: a signing secret (`AUTH_SECRET_KEY`), algorithm and token TTL become required
environment settings. The app must refuse to start with a missing or default secret in a non-local
environment.

**Database**: introduces the first schema. Migration tooling (Alembic) is *not* adopted here; tables are
created from metadata at startup and the choice is revisited when a second table needs to change shape.

**Out of scope** (deliberate, each a candidate follow-up): user registration through the API, refresh
tokens and revocation, password reset, roles/scopes/permissions, rate limiting and account lockout,
email verification.
