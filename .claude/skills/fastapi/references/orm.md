# Persistence

FastAPI ships no ORM of its own. SQLAlchemy (often via SQLModel, which layers
Pydantic-flavoured models on top of SQLAlchemy Core) is the most common choice
in real projects; Tortoise ORM and raw async drivers (`asyncpg`, `databases`)
also appear. Confirm which one a project actually uses before assuming its
patterns apply — do not assume SQLAlchemy just because it's the most common.

## Sessions

A session (SQLAlchemy) or connection is request-scoped, opened and closed by
a `yield` dependency (see `references/architecture.md`), never held on a
module-level global:

```python
def get_db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

For an async engine, the equivalent uses `AsyncSession` and an `async def`
dependency. Do not mix a sync `Session` into an `async def` path operation
without wrapping it (`run_in_threadpool` or a sync dependency) — that blocks
the event loop exactly like any other blocking call.

## Models and relationships

Keep the ORM model (the table mapping) separate from the Pydantic schema
returned to the client (see `references/routers.md`). They look similar and
it's tempting to collapse them into one class — resist it, because "what the
database stores" and "what the API exposes" diverge the moment either one
needs a field the other doesn't.

```python
# app/orders/models.py — ORM model
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    total_cents: Mapped[int]
    customer: Mapped["Customer"] = relationship(back_populates="orders")
```

```python
# app/orders/schemas.py — API-facing schema
class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_cents: int
```

`from_attributes=True` (Pydantic v2; `orm_mode = True` under `class Config` in
v1) lets a Pydantic model validate directly from an ORM instance's
attributes, which is what makes `response_model=OrderRead` work against a
SQLAlchemy object without manual field-by-field copying.

### Relations and N+1 queries

A relationship accessed inside a loop, with no eager loading, issues one
query per iteration:

```python
# N+1: one query per order to fetch its customer
for order in orders:
    print(order.customer.name)
```

Use `selectinload`/`joinedload` (SQLAlchemy) or the equivalent for whichever
ORM is in use when a response is known to need a relation:

```python
orders = db.execute(
    select(Order).options(selectinload(Order.customer))
).scalars().all()
```

Verify with the MCP which loading strategy the pinned SQLAlchemy version
recommends for the shape of the relationship (one-to-many vs many-to-many) —
this is a place stale memory produces confidently wrong advice.

## Migrations

Schema changes go through a migration tool (Alembic is standard with
SQLAlchemy) — never hand-edit a production schema, and never rely on
`Base.metadata.create_all()` outside tests or local scaffolding. A migration
should be reviewable independently of the model change that prompted it.

## Validation vs domain rules

A Pydantic model validates *shape*: required fields, types, string length,
numeric ranges, regex patterns. It cannot check anything that needs the
database — "is this email already registered," "does this SKU exist," "is
the total within the customer's credit limit." Those are domain rules and
belong in the service layer, after Pydantic validation has already passed:

```python
class OrderCreate(BaseModel):
    customer_id: int
    sku: str = Field(min_length=1, max_length=64)
    quantity: int = Field(gt=0)


class OrderService:
    def create(self, data: OrderCreate) -> Order:
        if not self.repository.sku_exists(data.sku):
            raise DomainError(f"Unknown SKU: {data.sku}")
        return self.repository.create(data)
```

Async, DB-backed validation (uniqueness checks, cross-field checks needing a
query) does not belong in a Pydantic `field_validator`/`model_validator` —
those run synchronously during parsing, before a DB session even exists in
scope. Do it in the service instead, and raise a domain exception that an
exception handler maps to the right status code (see
`references/middleware.md`).

## Transactions

Keep a transaction's boundary at the service method, not scattered across
repository calls — a service method that calls three repository methods
should either commit all three or roll back all three, not commit after each.
Whether that means an explicit `with session.begin():` block or relying on
the session's default autocommit-off behaviour depends on the ORM
configuration in use; verify the project's actual session setup rather than
assuming.
