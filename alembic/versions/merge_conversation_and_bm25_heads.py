"""merge conversation and bm25 heads

Revision ID: merge_conversation_bm25
Revises: add_conversation_blocks, add_thread_name_bm25
Create Date: 2026-03-16

合并 add_conversation_blocks 和 add_thread_name_bm25 两个头，
解决多头冲突问题。

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "merge_conversation_bm25"
down_revision: Union[str, Sequence[str], None] = (
    "add_conversation_blocks",
    "add_thread_name_bm25",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """合并迁移 - 不需要执行任何操作，只是统一头节点。"""
    pass


def downgrade() -> None:
    """降级 - 不需要执行任何操作。"""
    pass
