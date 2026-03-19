"""add_conversation_blocks_table

Revision ID: add_conversation_blocks
Revises: add_user_tool_settings
Create Date: 2026-03-15 22:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import HALFVEC

# revision identifiers, used by Alembic.
revision: str = "add_conversation_blocks"
down_revision: Union[str, Sequence[str], None] = "add_user_tool_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 向量维度常量
EMBEDDING_DIMENSION = 1024
QWEN_EMBEDDING_DIMENSION = 1024


def upgrade() -> None:
    """创建对话记忆块表和相关索引。"""
    # 1. 创建 conversation schema（如果不存在）
    op.execute("CREATE SCHEMA IF NOT EXISTS conversation")

    # 2. 创建 conversation_blocks 表
    op.create_table(
        "conversation_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "discord_id",
            sa.String(50),
            nullable=False,
            comment="用户的Discord ID",
        ),
        sa.Column(
            "conversation_text",
            sa.Text(),
            nullable=False,
            comment="对话块的原始文本内容",
        ),
        sa.Column(
            "start_time",
            sa.DateTime(),
            nullable=False,
            comment="对话块中第一条消息的时间",
        ),
        sa.Column(
            "end_time",
            sa.DateTime(),
            nullable=False,
            comment="对话块中最后一条消息的时间",
        ),
        sa.Column(
            "message_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="对话块中的消息数量",
        ),
        sa.Column(
            "bge_embedding",
            HALFVEC(EMBEDDING_DIMENSION),
            nullable=True,
            comment="BGE-M3 模型的对话内容向量嵌入（用于语义搜索）",
        ),
        sa.Column(
            "qwen_embedding",
            HALFVEC(QWEN_EMBEDDING_DIMENSION),
            nullable=True,
            comment="Qwen3-Embedding-0.6B 模型的对话内容向量嵌入（用于语义搜索）",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            comment="数据库记录创建时间",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            comment="数据库记录更新时间",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema="conversation",
    )

    # 3. 创建主键索引
    op.create_index(
        "ix_conversation_conversation_blocks_id",
        "conversation_blocks",
        ["id"],
        unique=False,
        schema="conversation",
    )

    # 4. 创建 discord_id 索引（用于按用户过滤）
    op.create_index(
        "idx_conv_discord_id",
        "conversation_blocks",
        ["discord_id"],
        unique=False,
        schema="conversation",
    )

    # 5. 创建 start_time 索引（用于按时间排序）
    op.create_index(
        "idx_conv_start_time",
        "conversation_blocks",
        ["start_time"],
        unique=False,
        schema="conversation",
    )

    # 6. 创建 HNSW 向量索引（BGE-M3）
    op.execute("""
        CREATE INDEX idx_conv_bge_embedding_hnsw
        ON conversation.conversation_blocks
        USING hnsw (bge_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # 7. 创建 HNSW 向量索引（Qwen）
    op.execute("""
        CREATE INDEX idx_conv_qwen_embedding_hnsw
        ON conversation.conversation_blocks
        USING hnsw (qwen_embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # 8. 创建 BM25 索引（用于关键词搜索）
    op.execute("""
        CREATE INDEX idx_conv_text_bm25
        ON conversation.conversation_blocks
        USING bm25 (id, (conversation_text::pdb.chinese_compatible))
        WITH (key_field='id');
    """)


def downgrade() -> None:
    """删除对话记忆块表和相关索引。"""
    # 1. 删除 BM25 索引
    op.execute("DROP INDEX IF EXISTS conversation.idx_conv_text_bm25")

    # 2. 删除 HNSW 向量索引
    op.execute("DROP INDEX IF EXISTS conversation.idx_conv_qwen_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS conversation.idx_conv_bge_embedding_hnsw")

    # 3. 删除普通索引
    op.drop_index(
        "idx_conv_start_time", table_name="conversation_blocks", schema="conversation"
    )
    op.drop_index(
        "idx_conv_discord_id", table_name="conversation_blocks", schema="conversation"
    )
    op.drop_index(
        "ix_conversation_conversation_blocks_id",
        table_name="conversation_blocks",
        schema="conversation",
    )

    # 4. 删除表
    op.drop_table("conversation_blocks", schema="conversation")

    # 5. 删除 schema（如果为空）
    op.execute("DROP SCHEMA IF EXISTS conversation CASCADE")
