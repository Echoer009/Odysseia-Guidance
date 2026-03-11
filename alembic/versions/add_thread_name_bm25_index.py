"""add_thread_name_bm25_index

Revision ID: add_thread_name_bm25
Revises: add_dual_embedding
Create Date: 2026-03-11

为 forum.forum_threads 表的 thread_name 字段添加 BM25 索引，
使关键词搜索能够同时搜索标题和内容。

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "add_thread_name_bm25"
down_revision: Union[str, Sequence[str], None] = "add_dual_embedding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 删除旧的只包含 content 的 BM25 索引
    op.execute("DROP INDEX IF EXISTS forum.idx_forum_threads_bm25;")

    # 创建新的 BM25 索引，同时包含 content 和 thread_name
    # 使用 chinese_compatible 配置以支持中文分词
    op.execute(
        """
        CREATE INDEX idx_forum_threads_bm25
        ON forum.forum_threads
        USING bm25 (id, ((content)::pdb.chinese_compatible), ((thread_name)::pdb.chinese_compatible))
        WITH (key_field=id)
    """
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 删除新的 BM25 索引
    op.execute("DROP INDEX IF EXISTS forum.idx_forum_threads_bm25;")

    # 恢复旧的只包含 content 的 BM25 索引
    op.execute(
        """
        CREATE INDEX idx_forum_threads_bm25
        ON forum.forum_threads
        USING bm25 (id, ((content)::pdb.chinese_compatible))
        WITH (key_field=id)
    """
    )
