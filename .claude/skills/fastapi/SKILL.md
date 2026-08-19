---
name: fastapi
description: Development conventions, architecture and testing practices for FastAPI applications. Use when writing, reviewing or refactoring FastAPI code — routers, path operations, dependencies, Pydantic models, persistence, or tests. Pairs with the FastAPI documentation MCP server for verified framework APIs.
---

# FastAPI Development

How to write FastAPI code well. This skill holds **conventions and judgement**;
the authoritative **framework reference** lives in the documentation MCP server.
Keep those roles separate — do not guess at APIs that the MCP can confirm.

## Verify before you assert

The single most damaging failure mode in FastAPI work is a confidently
invented API: a parameter that never existed, a dependency pattern from a
different Pydantic major version, a lifecycle hook whose signature changed.
FastAPI's own surface moves fast — it ships releases far more often than most
frameworks — and the ecosystem around it (Pydantic v1 vs v2, SQLAlchemy 1.4
vs 2.0, Starlette internals) moves independently and is exactly where stale
memory bites.

**Consult the documentation MCP before writing code whenever:**

- you are unsure a parameter, class or its options exist;
- behaviour may be version-specific (Pydantic v1/v2 differences, `Depends()`
  caching rules, lifespan vs `on_event`);
- a dependency's scope, caching or override behaviour is uncertain;
- middleware, dependency or exception-handler execution order is uncertain;
- ORM, validation or authentication behaviour is uncertain;
- you are about to describe framework behaviour to the user as fact.

Tools available:

| Tool | Use |
|---|---|
| `search_fastapi_manual` | Find documentation for a topic, class or parameter |
| `get_fastapi_manual` | Fetch a full document by `documentId` from a search hit |
| `search_fastapi_api` | Look up a specific class, function or parameter type |

The MCP server is already scoped to **this project's FastAPI version**.
Results it returns are correct for the version in use; your memory may not be.

> Prefer verified information from the FastAPI Documentation MCP over
> assumptions or memory. Never invent parameters, methods, dependency
> behaviour or framework behaviour — look them up.

If the MCP reports that documentation is not synchronized, tell the user to
run `fastapi-harness manuals update` rather than falling back to guesswork.

## Project specs are separate

Some projects also index their own specs, ADRs and design notes. Use these for
application-specific requirements and expected behaviour, not for FastAPI
framework facts.

| Tool | Use |
|---|---|
| `search_project_specs` | Find this project's own requirements, design notes and ADRs |
| `get_project_spec` | Fetch a full project spec by `documentId` from a search hit |

Search project specs when planning features, writing tests for business rules,
or checking whether a domain behaviour is already documented. Keep the corpora
distinct in your reasoning and reporting: FastAPI manual results explain the
framework; project specs explain this application's intended behaviour.

## Architecture in one page

FastAPI is a thin, type-hint-driven layer over Starlette (ASGI) and Pydantic
(validation/serialization). There is no built-in DI container, no decorator-
based class registration and no fixed module system — composition happens
through plain Python functions, `APIRouter`, and `Depends()`. Request flow:

```
Request
  → ASGI server (uvicorn/hypercorn)   accepts the connection
  → Middleware (Starlette/ASGI)        cross-cutting, wraps the whole request+response
  → Routing (APIRouter → path op)      matches method + path to a function
  → Dependencies (Depends())           resolved before the handler; may short-circuit via HTTPException
  → Pydantic validation                request body/params validated against type hints
  → Path operation function            thin: coordinate, don't compute
  → Service layer                      business logic, plain functions/classes
  → Repository / ORM                   persistence (SQLAlchemy, SQLModel, …)
  → response_model serialization       shapes the outgoing response
  → Exception handlers                 catch and format anything thrown above
```

Layer responsibilities:

- **Component** — the architectural folder for one business domain or one
  infrastructure integration; can contain several routers. Not a FastAPI
  concept by that name — this skill's vocabulary for the directory unit.
- **Path operation function** — read input, delegate, choose a response
  shape. No business logic. FastAPI's equivalent of a "controller action."
- **Service** — business logic; receives its collaborators (DB session,
  settings, other services) as plain function/constructor parameters, often
  themselves wired via `Depends()`.
- **Router (`APIRouter`)** — the unit of composition: groups path operations
  under a prefix, shared tags and shared dependencies. A component typically
  owns one or more — see `references/architecture.md`.
- **Dependency (`Depends()`)** — decides what a request needs (auth, DB
  session, shared query params) and can gate access by raising
  `HTTPException` before the handler runs — FastAPI's equivalent of a guard.
- **Middleware** — wraps every request/response; logging, CORS, GZip,
  request timing. No access to path parameters or the resolved route.
- **Pydantic model (`BaseModel`)** — validates and transforms individual
  arguments (request bodies, query/path params via type hints).
- **Exception handler (`@app.exception_handler`)** — turns a raised error
  into a well-shaped HTTP response.
- **Repository** — persistence, with named query methods, behind the
  service, not the path operation function.
- **Response schema** — a `BaseModel` passed as `response_model` (or a return
  type annotation); shapes what a response actually exposes, separate from
  the ORM model it's built from.
- **CLI command** — an operational script (Typer/Click), often reusing the
  same service layer as the API, not a copy of it.

Details: `references/architecture.md`. For how these layers are organised once
a component (or the whole app) grows large — splitting a component into
several routers, an app-factory + `lifespan`, per-component settings, project
layout conventions — see `references/conventions.md`.

## Rules that matter most

1. **Thin path operation functions.** A handler that exceeds ~20 lines is
   usually doing work that belongs in a service. Path operations coordinate.
2. **Depend on abstractions via `Depends()`, always.** A service should
   receive its collaborators (DB session, settings, other services) as
   parameters, not reach for a global, a module-level singleton, or a
   service locator inside domain code. See `references/architecture.md`.
3. **Request validation and domain rules are different things.** A Pydantic
   model checks the *shape* of incoming data (required, format, length). A
   uniqueness check or a business invariant that needs the database belongs
   in the service layer. Use both, for their own purposes. See
   `references/orm.md`.
4. **Never bind a request body directly onto an ORM model.** Go through a
   dedicated "create"/"update" Pydantic schema with only the fields that
   should be settable, and apply them explicitly (`model.field = ...` or a
   whitelisted `**dict`) — never `Model(**request_body.model_dump())` against
   a model with more columns than the schema exposes. This is FastAPI's mass-
   assignment defence — see `references/security.md`.
5. **Query in the service or repository, not the path operation function.**
   Reusable query logic belongs behind the repository/service, not repeated
   across handlers.
6. **Let the ORM or query builder parameterise.** Never string-concatenate or
   f-string user input into raw SQL, `.execute(text(...))`, or a filter
   expression. See `references/security.md`.
7. **Test through the framework.** Use `TestClient` (or `httpx.AsyncClient`
   with `ASGITransport`) for HTTP-level behaviour, and `app.dependency_overrides`
   to isolate a path operation from its real dependencies in narrower tests.
   See `references/testing.md`.
8. **Never return an ORM model straight from a handler.** Declare
   `response_model=` (or a return-type annotation) with a dedicated Pydantic
   schema (`model_config = ConfigDict(from_attributes=True)`) so what's
   exposed is an explicit allow-list, not every column and relationship the
   ORM knows about. See `references/routers.md`.

## FastAPI traps

These are the mistakes most likely to appear from stale memory or from
ecosystem packages that moved independently of FastAPI itself. When in doubt,
verify with the MCP.

| Don't | Do |
|---|---|
| Assume a `def` path operation runs on the event loop the same way `async def` does | FastAPI runs sync `def` handlers in a threadpool automatically; blocking I/O inside an `async def` handler stalls the whole event loop — know which one you have |
| Use a mutable default argument or a module-level dict as request-shared "cache" | Handlers run concurrently; shared mutable state needs a real store (Redis, DB) or per-request `Depends()` state, not a global |
| Assume `response_model` also validates or sanitises what got written to the database | It only shapes the *outgoing* response, after the handler already ran — validate on the way in with a request model too |
| Treat Pydantic v1 and v2 syntax as interchangeable | `class Config` vs `model_config = ConfigDict(...)`, `.dict()`/`.json()` vs `.model_dump()`/`.model_dump_json()`, `@validator` vs `@field_validator` — confirm which major version this project pins before using either |
| Assume two `Depends()` calls with different arguments share a cached result | Per-request caching is keyed by the callable *and* its resolved arguments (`use_cache=True` is the default, but that's what it caches) — do not rely on cross-call sharing you haven't verified |
| Raise a bare `Exception` and expect a clean, informative error response | Without a registered `@app.exception_handler`, that becomes a generic detail-free 500 to the client — raise `HTTPException` for expected conditions, register a handler for domain exceptions you want mapped to a specific status |
| Assume one canonical ORM or validation stack | FastAPI ships neither. SQLAlchemy (often via SQLModel) is the most common first-party-adjacent choice, but Tortoise ORM and raw async drivers are common too — confirm which this project actually uses before assuming its patterns apply |

Pydantic major version matters as much as the FastAPI version itself — verify
anything version-sensitive (validators, `model_config`, serialization methods)
before relying on it.

## References

Load these as needed — they are not all relevant to every task.

| File | Covers |
|---|---|
| `references/architecture.md` | App factory, `lifespan`, routers, DI via `Depends()`, background tasks, per-component settings, logging |
| `references/orm.md` | Sessions, models, relationships, migrations, validation vs domain rules |
| `references/routers.md` | Path operations, request/response, Pydantic schemas, `response_model`, pagination |
| `references/middleware.md` | The request pipeline: middleware, dependencies, exception handlers, ordering |
| `references/testing.md` | `TestClient`, dependency overrides, fixtures, what to assert |
| `references/security.md` | Mass assignment, SQL injection, auth (OAuth2/JWT), CORS, secrets |
| `references/conventions.md` | Naming, project layout, splitting routers, settings, tooling |

## Working on a task

1. Identify which layer the change belongs in before writing code.
2. Look up uncertain framework APIs with the FastAPI manual/API tools — do not
   guess.
3. Search project specs when requirements or business behaviour may already be
   documented.
4. Follow existing patterns in the project; match its structure, its ORM, and
   its style.
5. Add or update tests alongside the change.
6. Keep path operations thin and business logic testable in isolation from HTTP.
