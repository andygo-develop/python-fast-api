# Routers and path operations

## Request and response schemas

Every path operation should declare an explicit request schema (for a body)
and an explicit `response_model` — never accept or return a bare `dict`, and
never reuse the same Pydantic model for both input and output:

```python
class OrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: int
    sku: str
    quantity: int = Field(gt=0)


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    sku: str
    quantity: int
    status: str


@router.post("/", response_model=OrderRead, status_code=201)
def create_order(payload: OrderCreate, service: OrderService = Depends(get_order_service)) -> Order:
    return service.create(payload)
```

`extra="forbid"` on the request schema rejects unexpected fields outright
rather than silently dropping them — worth doing on any schema that will feed
an ORM create/update, since a silently-dropped field can hide a client bug
that a rejected field surfaces immediately.

Returning the ORM instance (`Order`) and letting `response_model=OrderRead`
do the shaping is fine and common — FastAPI validates the return value
against the response model regardless of what type the function itself
returns. What isn't fine is skipping `response_model` and returning the ORM
instance (or a dict built from `vars(order)`) directly to the client: that
exposes every column and every relationship the ORM knows about, including
ones added later without anyone noticing they're now public API surface.

## Path and query parameters

Type hints are the validation, not an afterthought:

```python
@router.get("/", response_model=list[OrderRead])
def list_orders(
    status: OrderStatus | None = None,
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
    service: OrderService = Depends(get_order_service),
) -> list[Order]:
    return service.list(status=status, limit=limit, offset=offset)
```

- Bound `limit`/`offset` (or a cursor) at the parameter level with
  `Query(..., le=..., ge=...)` — don't validate pagination bounds by hand
  inside the handler when the type system can reject an out-of-range value
  before the handler ever runs.
- Prefer an `Enum` (`OrderStatus`) over a bare `str` for a parameter with a
  fixed set of legal values — FastAPI renders it as a constrained value in
  the OpenAPI schema and rejects anything else automatically.
- A path parameter's type hint is enforced the same way: `order_id: int` in
  the path rejects a non-numeric id with a 422 before the handler runs.

## Pagination

Two shapes cover most cases:

- **Offset/limit** (`?limit=20&offset=40`) — simple, but a page can shift
  under concurrent writes (item 41 might have moved). Fine for admin UIs and
  low-write-rate data.
- **Cursor-based** (`?cursor=<opaque-token>&limit=20`) — stable under
  concurrent writes, the right choice for a public, high-traffic list
  endpoint. The cursor is normally an encoded value from the sort key (an id,
  or an id+timestamp pair), not a raw offset.

Return pagination metadata explicitly in the response schema
(`total`/`next_cursor`) rather than expecting the client to infer whether
there's a next page from the page size alone.

## Status codes and errors

- Declare `status_code=` on the path operation for anything other than the
  default `200` (`201` for create, `204` for a no-body delete, etc.) rather
  than setting it by hand on a `Response` object.
- Raise `HTTPException(status_code=..., detail=...)` for expected error
  conditions (not found, conflict, validation failure that Pydantic can't
  express). Reserve custom domain exceptions + an `@app.exception_handler`
  for errors that need structured detail beyond a string, or that many
  routers need to handle the same way — see `references/middleware.md`.
- Document error responses with `responses={404: {"model": ErrorDetail}}` on
  the path operation decorator when the error shape matters to API
  consumers (it becomes part of the generated OpenAPI schema).

## Audience-scoped routers

When the same resource needs different shapes for different callers (an
admin endpoint returning internal fields, a public endpoint that doesn't),
prefer two routers with two response schemas over one router branching on a
role check inside the handler:

```python
# app/orders/router.py — public
router = APIRouter()

@router.get("/{order_id}", response_model=OrderRead)
def get_order(...): ...

# app/orders/admin_router.py — admin, mounted under /admin
admin_router = APIRouter(dependencies=[Depends(require_admin)])

@admin_router.get("/{order_id}", response_model=OrderAdminRead)
def get_order_admin(...): ...
```

This keeps the "what does an admin get to see" decision at the router/schema
level, where it's visible in the OpenAPI docs, rather than buried in a
conditional inside a shared handler.

## Versioning

If a project version its API at all, prefer a URL prefix (`/v1`, `/v2`) via
separate routers mounted with `app.include_router(v1_router, prefix="/v1")`
over a header-based or content-negotiated scheme — it's the simplest to
reason about, to document, and to route at a load balancer if that ever
becomes necessary. Don't introduce versioning speculatively for a project
that doesn't have an external API contract to keep stable yet.
