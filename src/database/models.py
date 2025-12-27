import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    func,
)
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import HALFVEC

# 定义一个自定义的 schema 用于存放教程相关的表。
SCHEMA_NAME = "tutorials"
# 我们将为 Gemini 模型使用 3072 维的向量，并以半精度浮点数存储。
EMBEDDING_DIMENSION = 3072

Base = declarative_base()


class TutorialDocument(Base):
    """
    代表一份原始、完整的教程文档。
    该表存储了源信息和元数据。
    """

    __tablename__ = "tutorial_documents"
    __table_args__ = {"schema": SCHEMA_NAME}

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False, comment="教程的标题。")
    category = Column(String, nullable=True, comment="教程所属的高级类别。")
    source_url = Column(String, nullable=True, comment="文档的源URL。")
    author = Column(String, nullable=True, comment="文档的作者名。")
    author_id = Column(String, nullable=False, comment="作者的Discord用户ID。")
    thread_id = Column(String, nullable=True, comment="原始Discord帖子的ID。")
    tags = Column(JSON, nullable=True, comment="用于存储标签的JSON字段。")

    # 完整的原始内容存储在这里，以备参考和重新分块。
    original_content = Column(Text, nullable=False)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 这创建了与 KnowledgeChunk 的一对多关系。
    chunks = relationship("KnowledgeChunk", back_populates="document")

    __table_args__ = (
        Index("ix_tutorial_documents_author_id", "author_id"),
        {"schema": SCHEMA_NAME},
    )

    def __repr__(self):
        return f"<TutorialDocument(id={self.id}, title='{self.title}')>"


class KnowledgeChunk(Base):
    """
    代表来自 TutorialDocument 的一个文本块，及其对应的向量。
    我们将在此表上执行向量搜索。
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        # 警告：下面的 BM25 索引定义仅供参考，因为它无法完全表达 ParadeDB v2 所需的特殊原生 SQL 语法。
        # 该索引的实际创建和管理是在 Alembic 迁移脚本 '43ecab4319d0' 中通过 op.execute() 手动完成的。
        # Index(
        #     "idx_chunk_text_bm25",
        #     "chunk_text",
        #     postgresql_using="bm25",
        # ),
        # HNSW 索引定义现在是准确的，包含了 pgvector 必需的操作符类。
        Index(
            "idx_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
        {"schema": SCHEMA_NAME},
    )

    id = Column(Integer, primary_key=True, index=True)

    # 用于链接回父文档的外键。
    document_id = Column(
        Integer, ForeignKey(f"{SCHEMA_NAME}.tutorial_documents.id"), nullable=False
    )

    chunk_text = Column(Text, nullable=False, comment="这个特定文本块的内容。")
    chunk_order = Column(Integer, nullable=False, comment="文本块在文档中的序列号。")

    embedding = Column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=False,
        comment="此文本块的半精度嵌入向量。",
    )

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # 这创建了回到 TutorialDocument 的多对一关系。
    document = relationship("TutorialDocument", back_populates="chunks")

    def __repr__(self):
        return f"<KnowledgeChunk(id={self.id}, document_id={self.document_id})>"
