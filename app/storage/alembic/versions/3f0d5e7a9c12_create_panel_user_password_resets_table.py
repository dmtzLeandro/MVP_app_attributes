"""create panel_user_password_resets table

Revision ID: 3f0d5e7a9c12
Revises: 9d5c8ef4e1a2
Create Date: 2026-04-17 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3f0d5e7a9c12"
down_revision: Union[str, None] = "e3f7a2c4d9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "panel_user_password_resets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("panel_user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("store_id", sa.String(length=32), nullable=False),
        sa.Column("reset_token_hash", sa.String(length=64), nullable=False),
        sa.Column("reset_expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["panel_user_id"],
            ["panel_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_panel_user_password_resets_panel_user_id",
        "panel_user_password_resets",
        ["panel_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_panel_user_password_resets_email",
        "panel_user_password_resets",
        ["email"],
        unique=False,
    )
    op.create_index(
        "ix_panel_user_password_resets_store_id",
        "panel_user_password_resets",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_panel_user_password_resets_reset_token_hash",
        "panel_user_password_resets",
        ["reset_token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_panel_user_password_resets_reset_token_hash",
        table_name="panel_user_password_resets",
    )
    op.drop_index(
        "ix_panel_user_password_resets_store_id",
        table_name="panel_user_password_resets",
    )
    op.drop_index(
        "ix_panel_user_password_resets_email",
        table_name="panel_user_password_resets",
    )
    op.drop_index(
        "ix_panel_user_password_resets_panel_user_id",
        table_name="panel_user_password_resets",
    )
    op.drop_table("panel_user_password_resets")
