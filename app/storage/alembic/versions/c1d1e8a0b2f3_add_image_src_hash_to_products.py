"""add_image_src_hash_to_products

Revision ID: c1d1e8a0b2f3
Revises: b7a0c3d2f6a1
Create Date: 2026-03-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "c1d1e8a0b2f3"
down_revision: Union[str, None] = "b7a0c3d2f6a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_src_hash", sa.String(), nullable=True))
    op.create_index("ix_products_image_src_hash", "products", ["image_src_hash"])


def downgrade() -> None:
    op.drop_index("ix_products_image_src_hash", table_name="products")
    op.drop_column("products", "image_src_hash")
