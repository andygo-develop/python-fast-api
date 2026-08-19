## Context

The repository is a scaffold: `main.py` is PyCharm's generated placeholder, the only dependency is
`fastapi[standard]` (FastAPI 0.141.1, Pydantic 2.13.4, Python 3.14.5, `uv` with a committed lockfile),
and there is no `app/` package, database, or test suite. See `proposal.md` — Why.

Two consequences shape this design. First, there is no existing pattern to follow, so this change also
fixes the project's structural conventions; those are taken from `.claude/skills/fastapi/references/`
(domain-oriented packages, thin path operations, `Depends()` wiring, SQLAlchemy 2.0 typed models)
rather than invented here. Second, every framework API below was checked against the pinned 0.141.1
manuals via the `fastapi-docs` MCP — this version documents `pwdlib[argon2]` and `pyjwt`, superseding
the `passlib`/`python-jose` pairing that older tutorials and stale memory both suggest.

## Goals / Non-Goals

**Goals:**

- A layering the next capability can copy without rethinking it: router → service → repository, with
  HTTP concerns confined to the router and the auth rules testable without a client.
- Token verification isolated in one dependency, so every future protected endpoint is one parameter
  away from having an authenticated caller.
- Uniform authentication failures — indistinguishable in status, body, and (approximately) timing —
  as a design property rather than something bolted on later.
- A test suite that exercises the real HTTP surface against a real (temporary) database.

**Non-Goals:**

- Migration tooling. See Decision 6.
- A general authorization model. `get_current_user` answers *who*, never *may they*; scopes and roles
  arrive with the first capability that needs them.
- Multi-tenancy, social/external identity providers, or session-cookie support alongside bearer tokens.

## Decisions

### 1. Sync `def` path operations and a sync SQLAlchemy `Session`

FastAPI runs sync `def` path operations and sync `yield` dependencies in a threadpool, so blocking work
inside them does not stall the event loop — the reverse of what happens if the same blocking call sits
in an `async def` handler.

That distinction is decisive here rather than stylistic: Argon2 verification is *intentionally* slow and
CPU-bound (tens of milliseconds per call). In an `async def` handler with a sync driver it would block
the event loop for every concurrent request; in a threadpool it does not.

*Alternative considered:* async throughout (`asyncpg` + `AsyncSession`), which suits an I/O-bound
service. Rejected for now — it buys nothing while the workload is one CPU-bound hash per login, and it
would commit the project to an async driver before there is any evidence it needs one. The repository
boundary is where a later switch would land, so the cost of deferring is contained. The whole call path
stays sync; no mixing.

### 2. Password hashing with `pwdlib[argon2]`

What the 0.141.1 manuals recommend. Argon2id is memory-hard, and `pwdlib` handles salting and encodes
the algorithm and parameters into the stored string, satisfying the spec's "identifies its algorithm and
parameters" and "identical passwords hash differently" scenarios without hand-rolled salt columns.

*Alternative considered:* `passlib` + bcrypt — the pattern in most older FastAPI material. Rejected:
passlib is effectively unmaintained, and this version's own documentation has moved on.

### 3. JWT with `pyjwt`, HS256, minimal claims

`jwt.encode` / `jwt.decode` with a symmetric HS256 key. Claims: `sub` (the user's **id**, as a string),
`exp`, and `iat`.

`sub` carries the id rather than the username so that a later username change cannot silently transfer
a live token to a different identity. Verification must still load the user, because the spec requires
deleted or deactivated users to be refused — the token alone is never sufficient.

Every decode failure — bad signature, malformed structure, expired — is caught as PyJWT's
`InvalidTokenError` base class and mapped to the same generic 401. Distinguishing them in the response
would leak verification detail the spec forbids.

*Alternative considered:* asymmetric RS256, which lets other services verify without holding the signing
key. Rejected as premature with one service; the algorithm lives in settings, so it is revisitable.

### 4. Uniform authentication failure, including timing

Unknown username and wrong password must be indistinguishable. Equal status codes and bodies are the
easy half; the harder half is timing. A naive implementation returns immediately for an unknown user and
spends ~50ms hashing for a known one, which is a measurable user-enumeration oracle.

The service therefore verifies against a fixed dummy hash when no user is found, so both paths perform
one Argon2 verification before returning the same failure. The router raises a single
`HTTPException(401, "Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})` for
either outcome.

### 5. `get_current_user` as the only token-verification path

One dependency: decode → extract `sub` → load the user → reject if missing or inactive → return the ORM
user. Protected endpoints depend on it and never touch the token. Its 401s carry
`WWW-Authenticate: Bearer` as the spec requires.

Because it is a dependency, tests can override it via `app.dependency_overrides` to exercise a protected
route without minting tokens — and, more importantly, so can every future endpoint's tests.

### 6. Tables created from metadata at startup; no Alembic yet

`Base.metadata.create_all()` during lifespan startup. With one table and no production deployment,
Alembic's cost is real and its benefit is not.

This is deliberately a decision with an expiry date: the moment a second developer or a deployed
environment holds data that must survive a schema change, `create_all` becomes actively harmful (it
creates missing tables but never alters existing ones — silent drift, no error). Recorded in
`design.md` and flagged in `tasks.md` so the trigger is visible rather than discovered.

### 7. SQLite by default behind a configurable URL

`DATABASE_URL` defaults to a local SQLite file; tests use a temporary SQLite database. Nothing in the
code assumes SQLite, so pointing the URL at Postgres is a configuration change.

*Assumption on record* (the user did not specify a database): SQLite is right for a project with no
deployment target yet, and the repository boundary keeps the switch cheap. SQLite's `check_same_thread`
must be disabled for the threadpool model in Decision 1.

### 8. Users created by a CLI helper, not an API route

Registration is out of scope, but the login route is untestable without a user. A small
`python -m app.cli create-user` entry point calls the same `UserService.create_user` a future
registration endpoint would call, so adding that endpoint later is wiring, not reimplementation.

### 9. Settings validated at startup

One `Settings` (pydantic-settings) with `auth_secret_key`, `auth_algorithm`, `access_token_expire_minutes`,
`database_url`, `environment`. A validator rejects a missing or placeholder secret unless
`environment == "local"`, satisfying the spec's startup-refusal scenario. Failing at construction — not
at first login — turns a latent production vulnerability into an immediate, obvious boot error.

### 10. Package layout

```
app/
├── main.py              create_app(); app = create_app()
├── cli.py               create-user
├── core/{config,lifespan,security}.py
├── db/{base,session}.py
├── users/{models,repository,schemas,router,service}.py
└── auth/{router,schemas,service,dependencies}.py
```

`core/security.py` holds pure hash/token functions with no FastAPI or DB imports — the layer that is
cheapest to test exhaustively and most damaging to get wrong. `auth/dependencies.py` holds
`get_current_user`, and `users/` owns the model, its persistence, and `/users/me`.

## Risks / Trade-offs

- **`create_all` drifts silently once the schema changes** → Accepted deliberately (Decision 6); the
  adoption trigger is written into `tasks.md` rather than left to memory.
- **A leaked signing key mints tokens for any user, and nothing can revoke them** → Inherent to
  stateless JWTs with no revocation list. Mitigated by short token lifetime (default 30 minutes),
  secret supplied only via environment, and startup refusal on a placeholder value. Revocation is a
  named follow-up.
- **Argon2 is CPU-bound; concurrent logins consume threadpool workers** → Correct behaviour for a
  password hash, but it means login throughput is bounded by CPU, not I/O. Use library default
  parameters, do not tune them upward without measuring, and note that rate limiting (out of scope)
  is what ultimately protects this endpoint from abuse.
- **Timing equalization is approximate, not constant-time** → The dummy-hash path narrows the gap to
  noise for practical purposes; a determined attacker with many samples may still find signal. Full
  constant-time behaviour is not achievable at this layer, and rate limiting is the real defence.
- **Sync-everywhere is a bet that the workload stays CPU-bound** → If a later capability adds outbound
  HTTP calls per request, the threadpool becomes the bottleneck and the async question reopens. The
  repository/service split is what keeps that migration bounded.
- **SQLite differs from Postgres in type affinity, concurrency, and constraint enforcement** → Tests
  passing on SQLite are not proof against Postgres. Keep queries plain and ORM-generated; revisit when
  a deployment target exists.
