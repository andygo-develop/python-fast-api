## 1. Alembic setup

- [x] 1.1 `uv add alembic` (resolves to 1.19.1, pulling `mako`)
- [x] 1.2 `uv run alembic init migrations` — environment in `migrations/`, `alembic.ini` at the project root
- [x] 1.3 In `alembic.ini`, leave `sqlalchemy.url` empty so the URL has exactly one home (design Decision 2)
- [x] 1.4 `migrations/env.py`: set the URL from `get_settings().database_url`, import `app.users.models` so `target_metadata = Base.metadata` is populated, and pass `render_as_batch=True` to `context.configure` in both offline and online modes
- [x] 1.5 Verify `uv run alembic current` runs against the configured database and reports no version yet

## 2. Baseline migration

- [x] 2.1 Generate the baseline: `uv run alembic revision --autogenerate -m "create users table"`
- [x] 2.2 Read the generated migration and confirm it matches `app/users/models.py` exactly — `id` PK, `username` unique + indexed, `hashed_password`, `is_active` defaulting true, `created_at` — correcting it by hand rather than accepting whatever autogenerate emitted
- [x] 2.3 Confirm `downgrade()` drops the table and its index
- [x] 2.4 Apply to a scratch database: `uv run alembic upgrade head`, then inspect the schema — spec: *Applying migrations builds the schema*
- [x] 2.5 `uv run alembic downgrade base` then `upgrade head` again to prove reversibility — spec: *A migration can be reverted*
- [x] 2.6 Run `uv run alembic upgrade head` twice against the same database to confirm the second is a no-op — spec: *Applying migrations twice is safe*

## 3. Startup stops touching the schema

- [x] 3.1 `app/core/lifespan.py`: remove the `create_all()` call and the model import that existed only to populate metadata for it; drop the Alembic-trigger comment now that the trigger has been pulled
- [x] 3.2 Confirm the lifespan still exists and is still wired into `create_app()` — it now manages nothing, so if it is empty, leave a comment saying why it is kept
- [x] 3.3 Start the app against an empty database and confirm no tables are created and a request fails rather than succeeding — spec: *Starting the application does not change the schema*
- [x] 3.4 Confirm `tests/conftest.py` is untouched and still builds tables from metadata

## 4. Seeding

- [x] 4.1 `app/db/seeds.py`: a declarative list of seed users (username, password, is_active) with the documented development password, and `run_seeds(session)` returning what it created versus skipped
- [x] 4.2 Make `run_seeds` idempotent by looking each username up and skipping when present — not by relying on database-level conflict handling (design Decision 6)
- [x] 4.3 Seed through `UserService.create_user` so hashing and persistence have no second implementation — spec: *Seeding creates a known dataset*
- [x] 4.4 `app/cli.py`: add the `seed` subcommand, reporting created and skipped users
- [x] 4.5 Guard the command on `settings.environment`, permitting only `local` and `test` and refusing everything else, checked *before* any write — spec: *Seeding is refused outside development environments*
- [x] 4.6 Exit non-zero with a message naming the environment when refused

## 5. Strict sign-in form

- [x] 5.1 `app/auth/schemas.py`: add `SignInForm` with `model_config = ConfigDict(extra="forbid")` and `username`/`password` both `min_length=1`
- [x] 5.2 `app/auth/router.py`: take `Annotated[SignInForm, Form()]` in place of the `OAuth2PasswordRequestForm` dependency; the handler body is otherwise unchanged
- [x] 5.3 Delete `get_sign_in_form` from `app/auth/dependencies.py` along with its now-unused `RequestValidationError` and `OAuth2PasswordRequestForm` imports — `min_length=1` replaces it natively (design Decision 8)
- [x] 5.4 Keep `oauth2_scheme` and `get_current_user` exactly as they are — only the request form changes, not token verification
- [x] 5.5 Confirm the OpenAPI request schema for `POST /auth/sign-in` lists only `username` and `password` — spec: *Only the two credential fields are published*

## 6. Tests

- [x] 6.1 Test — valid credentials plus an arbitrary extra form field return 422 naming that field, and issue no token — spec: *An unrecognized field is rejected*
- [x] 6.2 Test — valid credentials plus each of `grant_type`, `scope`, `client_id`, `client_secret` return 422 — spec: *Previously tolerated OAuth2 parameters are rejected*
- [x] 6.3 Test — the OpenAPI schema for the endpoint declares exactly `username` and `password` — spec: *Only the two credential fields are published*
- [x] 6.4 Test — exactly the two fields still return 200 with a token — spec: *Exactly the two credential fields still succeed*
- [x] 6.5 Confirm the existing blank/missing-field tests still pass unchanged now that the 422 comes from Pydantic rather than the deleted dependency; update them only if the error *shape* changed, never the status
- [x] 6.6 Test — `run_seeds` against an empty database creates the documented users, and each can sign in with its documented password — spec: *Seeding an empty database*
- [x] 6.7 Test — `run_seeds` twice leaves the user count unchanged and reports nothing created the second time — spec: *Seeding twice*
- [x] 6.8 Test — the seed command refuses with a non-zero exit and creates nothing when `ENVIRONMENT` is `staging` or `production`, and proceeds under `local` and `test` — spec: *Seeding is blocked in a deployed environment*, *Seeding is permitted in development*
- [x] 6.9 Test — migrations applied to an empty scratch database produce a `users` table whose columns match `Base.metadata`, and `downgrade` removes it — spec: *Applying migrations builds the schema*, *A migration can be reverted*

## 7. Documentation

- [x] 7.1 `README.md` Quick start: add `uv run alembic upgrade head` before the first run, and `uv run python -m app.cli seed` as the way to get usable accounts
- [x] 7.2 `README.md`: remove the claim that the `/docs` Authorize button works, and say plainly that sign-in accepts only `username` and `password`
- [x] 7.3 `README.md`: correct `ACCESS_TOKEN_EXPIRE_MINUTES` from `60` to `30`, which is what `app/core/config.py` and `.env.example` actually say — a stale value predating this change
- [x] 7.4 `README.md`: document the seed users and their password, and that seeding is refused outside `local`/`test`
- [x] 7.5 `README.md` contributor notes: replace the "no migration tool" paragraph with the migration workflow — `alembic revision --autogenerate`, `alembic upgrade head`, and `alembic check` after changing a model
- [x] 7.6 `CLAUDE.md`: replace the `create_all`/Alembic-trigger note with the migration workflow, record that tests still build from metadata and why that makes `alembic check` the drift guard, and note that sign-in forbids extra fields

## 8. Verification

- [x] 8.1 Run `uv run pytest` and confirm the whole suite passes, reporting real output
- [x] 8.2 On a scratch database: `alembic upgrade head` → `seed` → sign in as a seeded user via curl → `GET /users/me`, end to end against a running server
- [x] 8.3 Confirm `POST /auth/sign-in` with `grant_type=password` returns 422 against the running server, and that the same request without it succeeds
- [x] 8.4 Confirm `uv run alembic check` reports no drift between models and migrations
- [x] 8.5 Confirm the PostgreSQL development database (`python-fast-api`) reaches `head` from empty, and that a SQLite database pre-built by `create_all()` can instead be adopted with `alembic stamp head`
