"""merge all heads

Revision ID: merge_all_heads_20260513
Revises: add_user_persona_preference, d4d2d70d3faa, add_thread_name_bm25, 40a238a8bfb3, add_shop_items, update_dim_1024, add_conversation_blocks
Create Date: 2026-05-13

"""

from typing import Sequence, Union

from alembic import op


revision: str = "merge_all_heads_20260513"
down_revision: Union[str, Sequence[str], None] = (
    "add_user_persona_preference",
    "d4d2d70d3faa",
    "add_thread_name_bm25",
    "40a238a8bfb3",
    "add_shop_items",
    "update_dim_1024",
    "add_conversation_blocks",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
