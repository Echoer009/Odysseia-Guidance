"""add admin schema with audit log and config overrides

Revision ID: b7d2e4f6a8c1
Revises: 81ae9d79793e
Create Date: 2026-08-30

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


revision: str = "b7d2e4f6a8c1"
down_revision: Union[str, Sequence[str], None] = "81ae9d79793e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("CREATE SCHEMA IF NOT EXISTS admin"))

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.String(200), nullable=False, server_default=""),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Index("ix_admin_audit_log_created_at", "created_at"),
        schema="admin",
    )

    op.create_table(
        "config_overrides",
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        schema="admin",
    )


def downgrade() -> None:
    op.drop_table("config_overrides", schema="admin")
    op.drop_table("audit_log", schema="admin")
    op.execute(text("DROP SCHEMA IF EXISTS admin"))
