"""add_image_src_to_products

Revision ID: b7a0c3d2f6a1
Revises: ae5f8c0bb964
Create Date: 2026-03-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7a0c3d2f6a1"
down_revision: Union[str, None] = "ae5f8c0bb964"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_src", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_src")
