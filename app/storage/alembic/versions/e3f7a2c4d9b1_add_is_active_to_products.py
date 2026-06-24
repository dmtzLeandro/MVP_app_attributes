"""add is_active to products

Revision ID: e3f7a2c4d9b1
Revises: 9d5c8ef4e1a2
Create Date: 2026-04-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e3f7a2c4d9b1"
down_revision: Union[str, None] = "9d5c8ef4e1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "is_active")
