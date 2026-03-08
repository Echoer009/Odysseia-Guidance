"""update embedding dimension to 1024 for bge-m3 model

Revision ID: update_dim_1024
Revises: 0d3c2d406343
Create Date: 2026-03-07

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "update_dim_1024"
down_revision: Union[str, Sequence[str], None] = "0d3c2d406343"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - update embedding dimension from 3072 to 1024"""
    # 删除旧的 HNSW 索引
    op.execute("DROP INDEX IF EXISTS tutorials.idx_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS general_knowledge.idx_gk_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS community.idx_cm_embedding_hnsw")

    # 临时移除 NOT NULL 约束
    op.execute(
        "ALTER TABLE tutorials.knowledge_chunks ALTER COLUMN embedding DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE general_knowledge.knowledge_chunks ALTER COLUMN embedding DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE community.member_chunks ALTER COLUMN embedding DROP NOT NULL"
    )

    # 清空旧的 embedding 数据（因为维度不兼容，必须在修改列类型之前执行）
    op.execute("UPDATE tutorials.knowledge_chunks SET embedding = NULL")
    op.execute("UPDATE general_knowledge.knowledge_chunks SET embedding = NULL")
    op.execute("UPDATE community.member_chunks SET embedding = NULL")

    # 修改 embedding 列类型
    op.execute(
        "ALTER TABLE tutorials.knowledge_chunks ALTER COLUMN embedding TYPE halfvec(1024)"
    )
    op.execute(
        "ALTER TABLE general_knowledge.knowledge_chunks ALTER COLUMN embedding TYPE halfvec(1024)"
    )
    op.execute(
        "ALTER TABLE community.member_chunks ALTER COLUMN embedding TYPE halfvec(1024)"
    )

    # 注意：不重新添加 NOT NULL 约束，因为 embedding 数据将在 re-embedding 脚本中填充
    # 如果需要 NOT NULL 约束，可以在 re-embedding 完成后手动添加

    # 重新创建 HNSW 索引
    op.execute("""
        CREATE INDEX idx_embedding_hnsw
        ON tutorials.knowledge_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_gk_embedding_hnsw
        ON general_knowledge.knowledge_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_cm_embedding_hnsw
        ON community.member_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    """Downgrade schema - revert embedding dimension back to 3072"""
    # 删除新的 HNSW 索引
    op.execute("DROP INDEX IF EXISTS tutorials.idx_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS general_knowledge.idx_gk_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS community.idx_cm_embedding_hnsw")

    # 恢复旧的 embedding 列类型
    op.execute(
        "ALTER TABLE tutorials.knowledge_chunks ALTER COLUMN embedding TYPE halfvec(3072)"
    )
    op.execute(
        "ALTER TABLE general_knowledge.knowledge_chunks ALTER COLUMN embedding TYPE halfvec(3072)"
    )
    op.execute(
        "ALTER TABLE community.member_chunks ALTER COLUMN embedding TYPE halfvec(3072)"
    )

    # 清空新的 embedding 数据（因为维度不兼容）
    op.execute("UPDATE tutorials.knowledge_chunks SET embedding = NULL")
    op.execute("UPDATE general_knowledge.knowledge_chunks SET embedding = NULL")
    op.execute("UPDATE community.member_chunks SET embedding = NULL")

    # 重新创建旧索引
    op.execute("""
        CREATE INDEX idx_embedding_hnsw
        ON tutorials.knowledge_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_gk_embedding_hnsw
        ON general_knowledge.knowledge_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    op.execute("""
        CREATE INDEX idx_cm_embedding_hnsw
        ON community.member_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
