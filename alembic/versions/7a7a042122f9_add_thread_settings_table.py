"""add_thread_settings_table

Revision ID: 7a7a042122f9
Revises: d1b5ce4c26a4
Create Date: 2026-02-09 14:39:03.530379

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a7a042122f9"
down_revision: Union[str, Sequence[str], None] = "d1b5ce4c26a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the thread_settings table in the tutorials schema
    op.create_table(
        "thread_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.String(), nullable=False, comment="Discord帖子的ID"),
        sa.Column(
            "search_mode",
            sa.String(),
            nullable=False,
            server_default="ISOLATED",
            comment="教程搜索模式: 'ISOLATED' (隔离) 或 'PRIORITY' (优先)",
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("thread_id"),
        schema="tutorials",
    )
    # Create index on id
    op.create_index(
        op.f("ix_thread_settings_id"),
        "thread_settings",
        ["id"],
        unique=False,
        schema="tutorials",
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the index and the table
    op.drop_index(
        op.f("ix_thread_settings_id"), table_name="thread_settings", schema="tutorials"
    )
    op.drop_table("thread_settings", schema="tutorials")
