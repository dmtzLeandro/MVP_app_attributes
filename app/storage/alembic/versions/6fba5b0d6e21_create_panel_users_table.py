"""create panel_users table

Revision ID: 6fba5b0d6e21
Revises: c1d1e8a0b2f3
Create Date: 2026-03-16 18:05:44.465686
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "6fba5b0d6e21"
down_revision: Union[str, None] = "c1d1e8a0b2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "panel_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
    )

    op.create_index("ix_panel_users_email", "panel_users", ["email"], unique=True)
    op.create_index("ix_panel_users_store_id", "panel_users", ["store_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_panel_users_store_id", table_name="panel_users")
    op.drop_index("ix_panel_users_email", table_name="panel_users")
    op.drop_table("panel_users")
