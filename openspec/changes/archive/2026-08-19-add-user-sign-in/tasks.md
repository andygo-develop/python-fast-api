## 1. Dependencies and skeleton

- [x] 1.1 Add runtime dependencies: `uv add pyjwt "pwdlib[argon2]" sqlalchemy pydantic-settings`
- [x] 1.2 Add dev dependencies: `uv add --dev pytest pytest-asyncio` (httpx already ships with `fastapi[standard]`; `python-multipart` is present at 0.0.32 and required for the login form — confirm it is still resolved after the sync)
- [x] 1.3 Configure `pytest` in `pyproject.toml` (`testpaths = ["tests"]`, asyncio mode) and create `app/` and `tests/` packages
- [x] 1.4 Add `.env.example` documenting `ENVIRONMENT`, `AUTH_SECRET_KEY`, `AUTH_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `DATABASE_URL`, and add `.env` and `*.db` to a `.gitignore`

## 2. Configuration and database foundation

- [x] 2.1 `app/core/config.py`: `Settings` (pydantic-settings) with `environment`, `auth_secret_key`, `auth_algorithm` (default `HS256`), `access_token_expire_minutes` (default 30), `database_url` (default local SQLite); expose a cached `get_settings()` dependency
- [x] 2.2 Add a `Settings` validator rejecting a missing/placeholder `auth_secret_key` unless `environment == "local"`, raising an error that names the offending setting — spec: *Missing signing key outside local development*
- [x] 2.3 `app/db/base.py`: SQLAlchemy 2.0 declarative `Base`
- [x] 2.4 `app/db/session.py`: engine built from `settings.database_url` (SQLite needs `check_same_thread=False`), `SessionLocal`, and a `get_db_session()` sync `yield` dependency that always closes
- [x] 2.5 `app/core/lifespan.py`: lifespan context manager calling `Base.metadata.create_all(engine)` on startup, with a comment recording the Alembic trigger from design Decision 6
- [x] 2.6 `app/main.py`: `create_app()` factory wiring lifespan and routers, plus `app = create_app()`; delete the PyCharm placeholder body from the root `main.py` and re-point it at the factory

## 3. User persistence

- [x] 3.1 `app/users/models.py`: `User` ORM model (`id` PK, `username` unique + indexed, `hashed_password`, `is_active` defaulting true, `created_at`) using `Mapped`/`mapped_column`
- [x] 3.2 `app/users/repository.py`: `UserRepository` over a `Session` with `get_by_username`, `get_by_id`, and `add`
- [x] 3.3 `app/users/schemas.py`: `UserRead` response schema (`id`, `username`, `is_active`) with `model_config = ConfigDict(from_attributes=True)` — no password field on any schema returned to a client

## 4. Security primitives

- [x] 4.1 `app/core/security.py`: `hash_password` / `verify_password` via `pwdlib` with the Argon2 hasher, at library-default parameters
- [x] 4.2 Same module: `create_access_token(subject, expires_delta)` producing `sub` (user id as string), `exp`, `iat`, signed with the configured key and algorithm
- [x] 4.3 Same module: `decode_access_token(token)` returning the subject, catching PyJWT's `InvalidTokenError` base class so signature, structure, and expiry failures are indistinguishable to callers
- [x] 4.4 Add a module-level dummy Argon2 hash and a `verify_dummy_password()` helper for the timing-equalization path (design Decision 4)
- [x] 4.5 Keep this module free of FastAPI and SQLAlchemy imports — it must be testable without an app or a database

## 5. Sign-in endpoint

- [x] 5.1 `app/auth/schemas.py`: `Token` response schema (`access_token`, `token_type`)
- [x] 5.2 `app/auth/service.py`: `AuthService.authenticate(username, password)` — load by username, verify against the stored hash, and when no user is found verify against the dummy hash before failing, so both paths cost one Argon2 verification
- [x] 5.3 `app/auth/service.py`: `issue_access_token(user)` returning a signed token with the configured lifetime
- [x] 5.4 `app/auth/router.py`: `POST /auth/sign-in` taking `Annotated[OAuth2PasswordRequestForm, Depends()]`, delegating to the service, returning `Token` via `response_model`; on failure raise `HTTPException(401, "Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})` — identical for unknown user and wrong password
- [x] 5.5 Confirm the handler stays under ~20 lines with no hashing, token, or query logic inline
- [x] 5.6 Register the auth router on the app factory with prefix `/auth` and tag `auth`

## 6. Token verification and `/users/me`

- [x] 6.1 `app/auth/dependencies.py`: `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/sign-in")`
- [x] 6.2 Same module: `get_current_user` — decode, load the user by id, reject a missing user, reject `is_active is False`, return the ORM user; every rejection is a 401 carrying `WWW-Authenticate: Bearer` and a generic message
- [x] 6.3 `app/users/router.py`: `GET /users/me` depending on `get_current_user`, returning `response_model=UserRead`
- [x] 6.4 Register the users router with prefix `/users` and tag `users`

## 7. User creation outside the API

- [x] 7.1 `app/users/service.py`: `UserService.create_user(username, password)` hashing the password and persisting via the repository, raising a domain error on duplicate username
- [x] 7.2 `app/cli.py`: `create-user` entry point (`python -m app.cli create-user <username>`) prompting for the password without echo and calling the same service
- [x] 7.3 Verify the CLI shares the service with no duplicated hashing or persistence logic

## 8. Tests

- [x] 8.1 `tests/conftest.py`: fixtures for a temporary SQLite database, a `Session`, an app with `get_db_session` overridden via `app.dependency_overrides`, a `TestClient`, and a factory creating a user with a known password
- [x] 8.2 Unit-test `app/core/security.py`: hash is not the plaintext and encodes its algorithm; the same password hashes to two different values; verify accepts the right password and rejects the wrong one; a token round-trips to its subject; a token signed with a different key is rejected; an already-expired token is rejected
- [x] 8.3 HTTP test — valid credentials return 200 with a non-empty `access_token` and `token_type == "bearer"`; spec: *Valid credentials are exchanged for a token*
- [x] 8.4 HTTP test — wrong password and unknown username both return 401 with byte-identical bodies and the same headers; spec: *Wrong password*, *Unknown username*
- [x] 8.5 HTTP test — missing username, missing password, and empty values return 422 and issue no token; spec: *Missing credential fields*
- [x] 8.6 HTTP test — no response from `/auth/sign-in`, success or failure, contains the submitted password or any stored hash; spec: *Credentials are never echoed back*
- [x] 8.7 HTTP test — a token from login lets `GET /users/me` return that user, and the body has no password or hash field; spec: *Valid token resolves to its user*
- [x] 8.8 HTTP test — `/users/me` with no header, a malformed token, a token with a tampered payload, and a token signed with a foreign key each return 401 with `WWW-Authenticate: Bearer`; spec: *No token supplied*, *Malformed or tampered token*
- [x] 8.9 HTTP test — a token minted with an expiry in the past returns 401; spec: *Expired token*
- [x] 8.10 HTTP test — a valid token whose user has been deleted, and one whose user has `is_active = False`, both return 401; spec: *Token for a user that no longer exists or is inactive*
- [x] 8.11 Settings test — constructing `Settings` with a missing or placeholder secret and `environment != "local"` raises an error naming the setting, and does not raise when `environment == "local"`; spec: *Missing signing key outside local development*
- [x] 8.12 Settings test — a changed `access_token_expire_minutes` is reflected in the `exp` claim of a newly issued token; spec: *Token lifetime is configurable*
- [x] 8.13 Persistence test — a created user's stored `hashed_password` is neither the plaintext nor recoverable from it; spec: *Stored credential is not reversible*, *Identical passwords hash differently*

## 9. Verification

- [x] 9.1 Run `uv run pytest` and confirm the whole suite passes; report real output, not a summary
- [x] 9.2 Start the app (`uv run fastapi dev main.py`), create a user via the CLI, and exercise login → `/users/me` end to end against the running server
- [x] 9.3 Confirm `/docs` shows the Authorize button wired to `POST /auth/sign-in` and that authorizing there makes `/users/me` succeed
- [x] 9.4 Update `CLAUDE.md`: replace the "no test runner installed" note with the real test commands, and record the now-established `app/` layout and auth conventions
