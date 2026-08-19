# Security

## Mass assignment

Binding a request body directly onto an ORM model or passing it straight into
a `.update()`/constructor call lets a client set *any* field the model has —
including ones never meant to be client-settable (`is_admin`, `balance`,
`verified`):

```python
# Dangerous: request body's fields all land on the model unfiltered.
@router.patch("/{user_id}")
def update_user(user_id: int, payload: dict, db: Session = Depends(get_db_session)):
    user = db.get(User, user_id)
    for key, value in payload.items():
        setattr(user, key, value)  # is_admin=true works if the client sends it
    db.commit()
```

Defend against it the same way every time: a dedicated Pydantic schema that
only contains the fields a client is allowed to set, with
`model_config = ConfigDict(extra="forbid")` so an unexpected field is
rejected rather than silently ignored, and apply it explicitly:

```python
class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    email: str | None = None
    # is_admin, balance, verified are deliberately absent


@router.patch("/{user_id}", response_model=UserRead)
def update_user(user_id: int, payload: UserUpdate, service: UserService = Depends(get_user_service)):
    return service.update(user_id, payload)
```

`model_dump(exclude_unset=True)` inside the service, applied field-by-field
onto the ORM model, keeps a `PATCH` semantics of "only update what was sent"
without ever touching a field the schema doesn't expose.

## SQL injection

Never build a query by string-formatting or concatenating user input, even
through the ORM's own escape hatches:

```python
# Dangerous, regardless of which ORM: string-built SQL.
db.execute(text(f"SELECT * FROM orders WHERE customer_id = {customer_id}"))
```

Use parameter binding — the ORM's query builder, or bound parameters on raw
SQL:

```python
db.execute(text("SELECT * FROM orders WHERE customer_id = :customer_id"), {"customer_id": customer_id})
# or, preferring the query builder entirely:
db.execute(select(Order).where(Order.customer_id == customer_id))
```

This applies identically to a `LIKE` pattern, an `ORDER BY` column name taken
from a query parameter (validate against an allow-list of real column names,
never interpolate the parameter directly), and any raw-SQL escape hatch the
project's ORM offers.

## Authentication

FastAPI ships the OAuth2 *scaffolding* (`OAuth2PasswordBearer`, security
dependencies that populate the OpenAPI docs' auth UI) but no user store, no
session mechanism and no token issuance — that's the project's own code or a
library (`fastapi-users`, `authlib`) layered on top. Common shape:

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db_session)) -> User:
    payload = decode_jwt(token)  # raises on invalid/expired — let it propagate to a 401 handler
    user = db.get(User, payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

- Verify a JWT's signature and expiry on every request — don't decode without
  verification "for convenience" anywhere that isn't a test.
- Keep the signing key out of source control and out of `settings.py`
  defaults — see Secrets below.
- Prefer short-lived access tokens plus a refresh flow over long-lived
  tokens, unless the project has a specific reason not to.

## Authorization

Put authorization checks in a dependency (see `references/middleware.md`),
not scattered through handler bodies — a check written inline in one path
operation is easy to forget to copy into the next one that needs it:

```python
def require_owner_or_admin(order_id: int, user: User = Depends(get_current_user), ...) -> User:
    order = ...
    if order.customer_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not allowed")
    return user
```

## CORS and headers

- Configure `CORSMiddleware` explicitly (see `references/middleware.md`);
  don't wildcard origins on anything handling authenticated requests.
- Set security headers (`X-Content-Type-Options`, `Strict-Transport-Security`
  for HTTPS deployments) via middleware or at the reverse proxy — verify
  which layer a given deployment actually handles this at before assuming
  FastAPI needs to.

## Secrets

- Read secrets through the `pydantic-settings` `Settings` object (see
  `references/architecture.md`), sourced from environment variables or a
  secrets manager — never hardcode a key, connection string or token in
  source, and never commit a `.env` file with real values.
- Don't log a request body, header, or settings object unfiltered — a
  bearer token or password can end up in application logs that way. Scrub
  or allow-list what a logging middleware records.
- Rate-limit sensitive or expensive endpoints (login, password reset,
  anything doing real work per request) — `slowapi` is a common choice; a
  reverse proxy or API gateway is another valid place to enforce it,
  depending on the deployment.

## Input beyond the request body

- File uploads (`UploadFile`) — validate content type and size before
  reading the whole thing into memory; stream large uploads rather than
  buffering.
- Redirect targets, webhook URLs, or anything else that becomes an outbound
  request based on client input — validate against an allow-list to avoid
  building an open redirect or SSRF vector.
