"""create panel_user_registrations table

Revision ID: 9d5c8ef4e1a2
Revises: 6fba5b0d6e21
Create Date: 2026-04-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9d5c8ef4e1a2"
down_revision: Union[str, None] = "6fba5b0d6e21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "panel_user_registrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("verification_token_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_used", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("verification_expires_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.store_id"]),
    )

    op.create_index(
        "ix_panel_user_registrations_store_id",
        "panel_user_registrations",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_panel_user_registrations_email",
        "panel_user_registrations",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_panel_user_registrations_verification_token_hash",
        "panel_user_registrations",
        ["verification_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_panel_user_registrations_verification_token_hash",
        table_name="panel_user_registrations",
    )
    op.drop_index(
        "ix_panel_user_registrations_email",
        table_name="panel_user_registrations",
    )
    op.drop_index(
        "ix_panel_user_registrations_store_id",
        table_name="panel_user_registrations",
    )
    op.drop_table("panel_user_registrations")
