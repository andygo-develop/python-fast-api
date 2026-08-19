# Testing

## Unit tests: services, not HTTP

A service written the way `references/architecture.md` describes — taking
its collaborators as parameters — should be testable with plain pytest and a
fake or in-memory collaborator, with no FastAPI app, no `TestClient`, and no
running server involved at all:

```python
def test_create_order_rejects_unknown_sku():
    fake_repo = FakeOrderRepository(known_skus=set())
    service = OrderService(fake_repo)

    with pytest.raises(DomainError, match="Unknown SKU"):
        service.create(OrderCreate(customer_id=1, sku="missing", quantity=1))
```

If a test for business logic needs to spin up an app or hit an HTTP client to
exercise it, that's usually a sign the logic is trapped inside the path
operation function instead of a service — see rule 1 in `SKILL.md`.

## HTTP-level tests: `TestClient`

`TestClient` (from `fastapi.testclient`, itself built on `httpx`) drives the
app through actual ASGI request/response handling, without a real socket:

```python
from fastapi.testclient import TestClient

client = TestClient(app)


def test_create_order_endpoint():
    response = client.post("/orders/", json={"customer_id": 1, "sku": "abc", "quantity": 2})
    assert response.status_code == 201
    assert response.json()["sku"] == "abc"
```

For testing `async def` code paths directly (rather than through the sync
`TestClient`, which runs its own event loop under the hood), use
`httpx.AsyncClient` with `ASGITransport`:

```python
import httpx


async def test_create_order_async():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/orders/", json={...})
    assert response.status_code == 201
```

Verify with the MCP which of these a project's pinned `httpx`/FastAPI
versions actually support — `ASGITransport`'s import path and `TestClient`'s
constructor signature have both changed across versions.

## Dependency overrides

`app.dependency_overrides` is how a test replaces a real dependency (a DB
session pointed at production, the real current-user auth check) with a
test double, without touching the path operation's code:

```python
def override_get_db_session():
    yield test_session


app.dependency_overrides[get_db_session] = override_get_db_session

def test_with_test_db():
    response = client.get("/orders/1")
    ...

app.dependency_overrides.clear()
```

Scope overrides to a test (a fixture with setup/teardown, or a context
manager) rather than leaving them set globally across a test module — a
forgotten override bleeding into an unrelated test is a common source of
tests that pass alone and fail in the full suite.

```python
@pytest.fixture
def client_with_test_db(test_session):
    app.dependency_overrides[get_db_session] = lambda: test_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

## Database fixtures

- A real test database (a throwaway Postgres schema, or SQLite for speed) is
  usually worth it for anything doing real queries — mocking the ORM session
  itself tends to test the mock, not the query.
- Wrap each test in a transaction that's rolled back at the end (or recreate
  the schema per test module) so tests don't leak state into each other.
- Prefer a fixture that builds real rows through the repository/service layer
  over hand-crafted `INSERT` fixtures — it exercises the same code paths
  production traffic does, and stays correct when the schema changes.

## What to assert

- Status code, response shape (via the response schema's fields, not just
  "the JSON parses"), and side effects that matter (a row was created, an
  email-sending function was called) — not implementation details like which
  private method a service called internally.
- Cover failure paths, not just the happy path: a missing resource (404), a
  validation failure (422 from Pydantic), a domain rule violation (400/409
  from a raised `HTTPException` or domain exception), and an authorization
  failure (401/403) for anything behind a dependency guard.
- For a dependency that gates access (`require_admin`), test both that a
  non-admin is rejected *and* that an admin is allowed through — a suite that
  only tests the rejection path can pass even if the guard is accidentally
  applied to the wrong router entirely.
- Assert on `response_model` shape, not on the ORM model's shape — a test
  asserting against internal fields that `response_model` doesn't actually
  expose is testing something the client can never see, and will pass even
  after the response schema starts hiding data it's meant to hide.

## What not to do

- Don't mock the ORM session itself for a test that's meant to verify query
  correctness — mock at the repository boundary for unit tests, and use a
  real (test) database for anything asserting the query does the right
  thing.
- Don't rewrite production code to make a failing test pass without
  understanding why it failed first — a failing test is either a bug found
  or a test that encodes a wrong assumption; treat it as a question to
  answer, not an obstacle to clear.
- Don't claim a suite passes without having actually run it.
