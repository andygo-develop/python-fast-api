"""create users table

Baseline migration. Matches app/users/models.py exactly, so a database whose
schema was previously built by Base.metadata.create_all() can be adopted with
`alembic stamp head` instead of being migrated.

Revision ID: 089670402896
Revises:
Create Date: 2026-08-19 14:09:26.571784

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "089670402896"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        # is_active and created_at carry Python-side defaults on the model, not
        # server defaults, so none are declared here — the schema stays a
        # faithful mirror of the model rather than quietly diverging from it.
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # batch_alter_table keeps the migration applicable on SQLite, which cannot
    # ALTER an existing table.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_users_username"), ["username"], unique=True
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_username"))

    op.drop_table("users")
