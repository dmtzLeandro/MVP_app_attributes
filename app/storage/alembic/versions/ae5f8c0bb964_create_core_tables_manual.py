"""create_core_tables_manual

Revision ID: ae5f8c0bb964
Revises: f0e91d5ef37b
Create Date: 2026-02-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "ae5f8c0bb964"
down_revision: Union[str, None] = "f0e91d5ef37b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stores",
        sa.Column("store_id", sa.String(), primary_key=True),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="installed"),
        sa.Column(
            "installed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
    )

    op.create_table(
        "products",
        sa.Column("store_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("handle", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("tn_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("store_id", "product_id"),
    )
    op.create_index("ix_products_handle", "products", ["handle"])

    op.create_table(
        "attribute_definitions",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("value_type", sa.String(), nullable=False),
    )

    op.create_table(
        "product_attribute_values",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("attribute_key", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["attribute_key"], ["attribute_definitions.key"]),
        sa.UniqueConstraint(
            "store_id", "product_id", "attribute_key", name="uq_store_product_attr"
        ),
    )
    op.create_index("ix_pav_store_id", "product_attribute_values", ["store_id"])
    op.create_index("ix_pav_product_id", "product_attribute_values", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_pav_product_id", table_name="product_attribute_values")
    op.drop_index("ix_pav_store_id", table_name="product_attribute_values")
    op.drop_table("product_attribute_values")
    op.drop_table("attribute_definitions")
    op.drop_index("ix_products_handle", table_name="products")
    op.drop_table("products")
    op.drop_table("stores")
