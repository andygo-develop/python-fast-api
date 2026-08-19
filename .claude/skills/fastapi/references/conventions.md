# Conventions

FastAPI has no CLI generator and no enforced project layout — unlike
frameworks that scaffold a fixed structure, a FastAPI project's shape is
entirely a team convention. That makes consistency something to actively
maintain rather than something the framework hands you; match whatever this
project already does before introducing a different pattern.

## Project layout

A layout that scales past a handful of endpoints, organised by domain rather
than by technical layer:

```
app/
├── main.py                  create_app() factory, app = create_app()
├── core/
│   ├── config.py            Settings (pydantic-settings)
│   ├── lifespan.py          startup/shutdown resource management
│   └── logging.py
├── db/
│   ├── base.py               declarative Base
│   └── session.py            get_db_session dependency
├── orders/
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   ├── repository.py
│   └── models.py
├── users/
│   ├── router.py
│   ├── schemas.py
│   ├── service.py
│   ├── repository.py
│   └── models.py
└── shared/
    └── exceptions.py         DomainError and friends
```

Avoid the alternative "organise by layer" structure (`app/routers/`,
`app/schemas/`, `app/services/`, `app/models/`, each holding files for every
domain mixed together) once a project has more than two or three domains —
finding everything related to `orders` means visiting five directories
instead of one.

## Naming

- Modules: `snake_case.py` (`order_service.py`, not `OrderService.py`).
- Classes: `PascalCase` (`OrderService`, `OrderCreate`, `OrderRead`).
- Path operation functions: `snake_case`, verb-first and specific
  (`create_order`, `list_orders_for_customer`), not generic (`get`, `post`).
- Pydantic schema suffixes, kept consistent project-wide: `...Create` for
  input on create, `...Update` for input on update (often with all fields
  optional), `...Read` (or `...Out`) for a response schema. Pick one
  convention and apply it everywhere rather than mixing `...Response` in one
  module and `...Read` in another.
- Routers: the module is the router (`orders/router.py` exports `router`),
  not `OrdersController` — there's no framework convention to mirror here
  because FastAPI doesn't have controller classes.

## Splitting a router

A router with path operations spanning clearly separate sub-resources
(`/orders`, `/orders/{id}/items`, `/orders/{id}/refunds`) is a signal to
split into several `APIRouter`s composed under one prefix, the same way a
large module splits into packages in most languages:

```python
# app/orders/router.py
router = APIRouter()
router.include_router(items_router, prefix="/{order_id}/items", tags=["order-items"])
router.include_router(refunds_router, prefix="/{order_id}/refunds", tags=["order-refunds"])
```

## Settings and environments

One `Settings` class (see `references/architecture.md`), with environment-
specific values coming from `.env` files or real environment variables —
not a `config_dev.py`/`config_prod.py` pair selected by an `if` on `ENV` at
import time. `pydantic-settings` supports `env_file` selection and nested
settings models if a project's configuration genuinely needs structure
beyond flat key-value pairs.

## Dependency and virtual environment management

FastAPI itself doesn't care which one a project uses, but consistency
matters for reproducibility. In rough order of what a modern project is
likely to use: `uv` (fastest, lockfile-based), `poetry` (lockfile-based,
widely established), `pip` + `requirements.txt` (simplest, no lockfile
unless paired with `pip-tools`), `pdm`. Whichever is in use, keep production
dependencies and development-only dependencies (test runner, linters)
declared separately, and commit the lock file.

## Tooling

A typical stack: `ruff` for linting and formatting (fast, replaces
`flake8`/`isort`/`black` in one tool for most projects), `mypy` (or `pyright`)
for static typing, `pytest` for tests. Configure them in `pyproject.toml`
rather than a scattering of `.flake8`/`.isort.cfg`/`mypy.ini` files, unless
the project already has a reason to keep them separate.

## Imports

- Absolute imports from the app package root (`from app.orders.service import
  OrderService`) rather than deep relative imports (`from ...service import
  ...`) — they survive a file being moved, and read the same regardless of
  which module you're standing in.
- Avoid a package `__init__.py` that re-exports everything from its
  submodules "for convenience" — it makes circular imports easy to introduce
  by accident as a project grows, and hides where a symbol actually lives.
  Import directly from the module that defines it.

## Async vs sync

Pick one default for path operations and be deliberate about exceptions: if
the project's DB driver and HTTP clients are async-native (`asyncpg`,
`httpx`), default to `async def` path operations and services throughout —
mixing sync blocking calls into them defeats the purpose (see the SKILL.md
traps table). If the stack is sync (`psycopg2`, `requests`), plain `def`
path operations are simpler and FastAPI's automatic threadpool offload
handles concurrency reasonably well without any async code at all. Don't
mix the two within one call path without understanding exactly where the
handoff between sync and async happens.
