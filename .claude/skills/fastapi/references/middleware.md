# The request pipeline

FastAPI has three distinct places to put cross-cutting or gating logic —
middleware, dependencies, and exception handlers — and they are not
interchangeable. Picking the wrong one is a common source of subtle bugs.

## Execution order

```
Request
  → Middleware (outer → inner, registration order matters)
  → Routing (which path operation matches)
  → Dependencies (in declaration order: router-level, then path-operation-level)
  → Path operation function
  → response_model validation
  → Middleware (inner → outer, on the way back out)
```

Exception handling sits *underneath* the middleware stack conceptually:
`ExceptionMiddleware` is itself one of Starlette's internal middleware
layers, positioned so that an exception raised by routing, a dependency, or
the handler is turned into a response *before* the rest of your own
middleware sees it on the way out. This is why a custom middleware can log
or modify the final response even when a handler raised — by the time
middleware runs on the way out, the exception has already become a response.

## Middleware

Use middleware for logic that applies uniformly to *every* request,
regardless of which route matched, and does not need route-specific
information:

```python
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.request_id = str(uuid.uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        response.headers["X-Response-Time"] = f"{time.perf_counter() - start:.3f}"
        return response


app.add_middleware(RequestIdMiddleware)
```

Registration order matters: the *last* middleware added via `add_middleware`
runs *outermost* (first on the way in, last on the way out) in Starlette's
model — verify the exact ordering rule for the FastAPI version in use with
the MCP before relying on relative order between two middlewares, since this
has been a source of real confusion even in FastAPI's own issue tracker.

Common uses: request IDs, timing/logging, CORS (`CORSMiddleware`),
compression (`GZipMiddleware`), trusted-host enforcement. Middleware cannot
cleanly express "only for this router" — for that, use a router-level
dependency instead.

## Dependencies as guards

Use a dependency (`Depends()`) for anything that needs to know *which route*
matched, needs path/query parameters, or needs to short-circuit a specific
router or path operation rather than every request:

```python
def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


router = APIRouter(dependencies=[Depends(require_admin)])
```

A router-level dependency applies to every path operation on that router; a
path-operation-level one (`@router.get("/", dependencies=[Depends(...)])`)
applies to just that one. Prefer the narrowest scope that's still correct —
a dependency applied to a whole router because "everything in here happens
to need it today" quietly becomes wrong the day one path operation in that
router shouldn't need it.

## Exception handlers

Use an exception handler for turning a *raised exception type* into a
consistent response shape across many places that might raise it, rather
than repeating a `try`/`except` + response-building block in every handler:

```python
class DomainError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
```

Order of preference for signalling an error from a path operation or
service:

1. `HTTPException` for a one-off, expected condition with no extra
   structure — simplest, works everywhere, no handler needed.
2. A domain exception + registered handler for anything raised from more
   than one place that needs the same response shape, or where the shape is
   richer than a status code + string.
3. Letting an unexpected exception propagate uncaught — becomes a generic
   500 with no detail to the client (correct default for a genuine bug; the
   full traceback still reaches server-side logs).

Don't reach for middleware to catch and format exceptions — that's what
exception handlers are for, and middleware written to `try`/`except` around
`call_next` interacts awkwardly with streaming responses and background
tasks. Verify with the MCP if a specific FastAPI/Starlette version changed
handler-vs-middleware exception propagation before relying on either.

## CORS

`CORSMiddleware` is the standard mechanism; configure it explicitly rather
than wildcarding origins in anything that isn't a fully public, unauthenticated
API:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_origins=["*"]` combined with `allow_credentials=True` is invalid per
the CORS spec and most browsers will refuse it — if credentials are needed,
list explicit origins.
