"""add user memory notes

Revision ID: add_user_memory_notes
Revises: merge_all_heads_20260513
Create Date: 2026-05-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_user_memory_notes"
down_revision: Union[str, Sequence[str], None] = "merge_all_heads_20260513"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_memory_notes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(50), nullable=False, comment="用户的Discord ID"),
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            comment="记忆类别: emotion(情感) / status(状态) / preference(偏好) / positive_event(正面事件)",
        ),
        sa.Column("content", sa.Text(), nullable=False, comment="记忆内容（单条不超过150字）"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.Index("ix_user_memory_notes_user_category", "user_id", "category"),
        schema="user",
    )


def downgrade() -> None:
    op.drop_table("user_memory_notes", schema="user")
