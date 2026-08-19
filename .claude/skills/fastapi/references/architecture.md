# Architecture

FastAPI does not prescribe a project structure the way some frameworks do.
This is deliberate freedom, but it means the conventions below are this
skill's own vocabulary, not the framework's — verify anything framework-level
with the documentation MCP rather than assuming it's official.

## Bootstrap

### App factory

Prefer a factory function over a module-level `app = FastAPI()` once a
project has more than a couple of routers or needs different configuration
for tests vs production:

```python
# app/main.py
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.lifespan import lifespan
from app.routers import orders, users


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        lifespan=lifespan,
    )

    app.include_router(users.router, prefix="/users", tags=["users"])
    app.include_router(orders.router, prefix="/orders", tags=["orders"])

    return app


app = create_app()
```

A factory makes it possible to build an app with test-only overrides
(a different database URL, disabled auth) without any of the global-state
hacks a module-level `app` invites. See `references/testing.md`.

### Lifespan, not `on_event`

Startup/shutdown resource management (DB connection pools, cache clients,
background workers) belongs in a `lifespan` context manager, not the
deprecated `@app.on_event("startup")` style:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_engine = create_engine(settings.database_url)
    yield
    await app.state.db_engine.dispose()
```

Verify with the MCP whether a project's pinned FastAPI version still supports
`on_event` before assuming either style — this is exactly the kind of detail
that changes between versions.

## Components and routers

A **component** here means the directory for one business domain (`orders/`,
`users/`) or one infrastructure integration (`notifications/`). It typically
owns:

```
app/
├── orders/
│   ├── router.py          APIRouter — path operations only
│   ├── schemas.py          Pydantic request/response models
│   ├── service.py          business logic
│   ├── repository.py       persistence, named query methods
│   └── models.py           ORM models (or shared in app/db/models.py)
```

A large component splits into several routers under one prefix rather than
one router with fifty path operations:

```python
# app/orders/router.py
from fastapi import APIRouter

router = APIRouter()
router.include_router(checkout_router, prefix="/checkout")
router.include_router(returns_router, prefix="/returns")
```

Keep routers themselves free of business logic — a router module should read
like a table of contents: path, method, dependencies, delegate to the
service, return.

## Dependency injection

FastAPI's DI is function-based, not a container that scans and registers
classes. `Depends()` accepts any callable (function, `staticmethod`, or a
class's `__init__` via `Depends(SomeClass)`):

```python
from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session


def get_order_service(db: Session = Depends(get_db_session)) -> OrderService:
    return OrderService(db)


@router.get("/{order_id}")
def get_order(order_id: int, service: OrderService = Depends(get_order_service)) -> OrderRead:
    return service.get(order_id)
```

Rules of thumb:

- **Services take their collaborators as constructor parameters.** A service
  should be instantiable and testable with a fake `db`/settings, with no
  dependency on FastAPI's request cycle at all. `Depends()` is how the
  *router* wires it up, not how the service itself is written.
- **Dependencies compose.** A dependency can itself depend on other
  dependencies (`get_order_service` above depends on `get_db_session`).
  FastAPI resolves the whole graph per request.
- **Caching is per-request, keyed by callable + resolved arguments.** Two
  path operations that both `Depends(get_db_session)` in the same request
  get the *same* session object (assuming default `use_cache=True` and
  identical arguments) — useful for "resolve current user once, reuse it,"
  easy to get wrong if you assume it caches across *different* arguments too.
- **A dependency can gate access.** Raising `HTTPException` inside a
  dependency stops the request before the handler runs — this is FastAPI's
  guard-equivalent:

```python
def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


router = APIRouter(dependencies=[Depends(require_admin)])
```

- **`yield` dependencies run cleanup after the response.** A dependency using
  `yield` instead of `return` runs the code after `yield` once the response
  has been sent (or an exception has propagated) — the standard pattern for
  "open a session, `yield` it, close it":

```python
def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

## Background work

- **`BackgroundTasks`** — for work that must happen after the response is
  sent but doesn't need a separate worker (send a confirmation email, write
  an audit log). Injected like any other dependency:

```python
@router.post("/")
def create_order(order: OrderCreate, background_tasks: BackgroundTasks) -> OrderRead:
    created = service.create(order)
    background_tasks.add_task(send_confirmation_email, created.id)
    return created
```

- **A real task queue** (Celery, arq, Dramatiq) — for anything that must
  survive a process restart, needs retries, or takes long enough that
  request-scoped background work isn't appropriate. `BackgroundTasks` runs
  in-process and is lost if the server restarts before it finishes; don't
  reach for it as a substitute for a queue.
- **A scheduled task** — a separate cron/scheduler process (or
  `apscheduler`), not something bolted onto request handling.

## Configuration

Centralise settings in one `pydantic-settings` model rather than reading
`os.environ` throughout the codebase:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    project_name: str = "orders-api"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Inject it via `Depends(get_settings)` rather than importing a module-level
instance directly into business logic — the same "makes tests possible"
reasoning as the DB session dependency. `pydantic-settings` is a separate
package from Pydantic core as of Pydantic v2; verify a project's pin before
assuming it's available.

## Logging

Use the standard library `logging` module, configured once at startup (or a
structured logging library like `structlog` if the project already has one).
Don't reach for `print()` in request-handling code, and don't log full
request bodies or headers unfiltered — see `references/security.md` on
secrets. Correlate logs to a request with a middleware that assigns a request
ID (see `references/middleware.md`), not by threading an ID through every
function signature by hand.
