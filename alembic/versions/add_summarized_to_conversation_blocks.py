"""add summarized field to conversation_blocks

Revision ID: add_summarized_conv_blocks
Revises: merge_conversation_bm25
Create Date: 2026-03-17

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "add_summarized_conv_blocks"
down_revision: Union[str, None] = "merge_conversation_bm25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 summarized 字段到 conversation_blocks 表，用于方案E的印象总结逻辑。"""
    # 添加 summarized 字段（用 INTEGER 表示布尔值，兼容 SQLite）
    op.add_column(
        "conversation_blocks",
        sa.Column(
            "summarized",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="是否已被印象总结（0=未总结，1=已总结）",
        ),
        schema="conversation",
    )


def downgrade() -> None:
    """移除 summarized 字段。"""
    op.drop_column("conversation_blocks", "summarized", schema="conversation")
