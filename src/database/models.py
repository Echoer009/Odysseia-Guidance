import datetime
from typing import Optional
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
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from pgvector.sqlalchemy import HALFVEC

# --- 全局配置 ---
EMBEDDING_DIMENSION = 3072  # 所有RAG统一使用3072维度

# --- Schema 名称 ---
TUTORIALS_SCHEMA = "tutorials"
GENERAL_KNOWLEDGE_SCHEMA = "general_knowledge"
COMMUNITY_SCHEMA = "community"
SHOP_SCHEMA = "shop"
USER_SCHEMA = "user"

Base = declarative_base()


class TutorialDocument(Base):
    """
    代表一份原始、完整的教程文档。
    该表存储了源信息和元数据。
    """

    __tablename__ = "tutorial_documents"
    __table_args__ = {"schema": TUTORIALS_SCHEMA}

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
        {"schema": TUTORIALS_SCHEMA},
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
        {"schema": TUTORIALS_SCHEMA},
    )

    id = Column(Integer, primary_key=True, index=True)

    # 用于链接回父文档的外键。
    document_id = Column(
        Integer, ForeignKey(f"{TUTORIALS_SCHEMA}.tutorial_documents.id"), nullable=False
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


class ThreadSetting(Base):
    """
    存储每个帖子（Thread）的独立设置。
    例如：教程搜索模式（ISOLATED 或 PRIORITY）。
    """

    __tablename__ = "thread_settings"
    __table_args__ = {"schema": TUTORIALS_SCHEMA}

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, unique=True, nullable=False, comment="Discord帖子的ID")
    search_mode = Column(
        String,
        nullable=False,
        default="ISOLATED",
        comment="教程搜索模式: 'ISOLATED' (隔离) 或 'PRIORITY' (优先)",
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ThreadSetting(thread_id='{self.thread_id}', search_mode='{self.search_mode}')>"


# --- 通用知识库模型 (关联表结构) ---


class GeneralKnowledgeDocument(Base):
    """
    代表一份完整的通用知识文档。
    存储源信息和元数据，与分块建立一对多关系。
    """

    __tablename__ = "knowledge_documents"
    __table_args__ = {"schema": GENERAL_KNOWLEDGE_SCHEMA}

    id = Column(Integer, primary_key=True)
    external_id = Column(
        String, unique=True, nullable=False, comment="来自旧系统的唯一ID"
    )
    title = Column(Text, nullable=True)
    full_text = Column(
        Text, nullable=False, comment="完整的文本内容，用于重新分块和BM25搜索"
    )
    source_metadata = Column(JSON, nullable=True, comment="来自旧系统的完整元数据备份")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 与分块的一对多关系
    chunks = relationship(
        "GeneralKnowledgeChunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<GeneralKnowledgeDocument(id={self.id}, title='{self.title}')>"


class GeneralKnowledgeChunk(Base):
    """
    代表来自 GeneralKnowledgeDocument 的一个文本块，及其对应的向量。
    我们将在此表上执行向量搜索。
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        # HNSW 索引用于向量搜索
        Index(
            "idx_gk_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
        {"schema": GENERAL_KNOWLEDGE_SCHEMA},
    )

    id = Column(Integer, primary_key=True)

    # 链接回父文档的外键
    document_id = Column(
        Integer,
        ForeignKey(f"{GENERAL_KNOWLEDGE_SCHEMA}.knowledge_documents.id"),
        nullable=False,
    )

    chunk_index = Column(Integer, nullable=False, comment="分块在文档中的序号")
    chunk_text = Column(Text, nullable=False, comment="这个特定文本块的内容")

    embedding = Column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=False,
        comment="此文本块的半精度嵌入向量",
    )

    created_at = Column(DateTime, server_default=func.now())

    # 回到 GeneralKnowledgeDocument 的多对一关系
    document = relationship("GeneralKnowledgeDocument", back_populates="chunks")

    def __repr__(self):
        return f"<GeneralKnowledgeChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"


# --- 社区成员模型 (关联表结构) ---


class CommunityMemberProfile(Base):
    """
    代表一个社区成员的完整档案。
    存储成员元数据，与分块建立一对多关系。
    """

    __tablename__ = "member_profiles"
    __table_args__ = {"schema": COMMUNITY_SCHEMA}

    id = Column(Integer, primary_key=True)
    external_id = Column(
        String,
        unique=True,
        nullable=False,
        comment="来自旧系统的唯一ID, 例如 member_id",
    )
    discord_id = Column(
        String, unique=True, nullable=True, comment="成员的Discord数字ID"
    )
    title = Column(Text, nullable=True, comment="成员标题/昵称")
    full_text = Column(
        Text,
        nullable=False,
        comment="完整的成员档案文本，用于重新分块和BM25搜索",
    )
    source_metadata = Column(JSON, nullable=True, comment="存储原始的、完整的成员档案")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    personal_summary = Column(Text, nullable=True, comment="个人记忆")
    history = Column(JSON, nullable=True, comment="用于生成最近一次个人记忆")
    personal_message_count = Column(
        Integer, nullable=False, default=0, server_default="0", comment="个人消息计数"
    )

    # 与分块的一对多关系
    chunks = relationship(
        "CommunityMemberChunk", back_populates="profile", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CommunityMemberProfile(id={self.id}, discord_id='{self.discord_id}')>"


class CommunityMemberChunk(Base):
    """
    代表来自 CommunityMemberProfile 的一个文本块，及其对应的向量。
    我们将在此表上执行向量搜索。
    """

    __tablename__ = "member_chunks"
    __table_args__ = (
        # HNSW 索引用于向量搜索
        Index(
            "idx_cm_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
        {"schema": COMMUNITY_SCHEMA},
    )

    id = Column(Integer, primary_key=True)

    # 链接回父档案的外键
    profile_id = Column(
        Integer, ForeignKey(f"{COMMUNITY_SCHEMA}.member_profiles.id"), nullable=False
    )

    chunk_index = Column(Integer, nullable=False, comment="分块在档案中的序号")
    chunk_text = Column(Text, nullable=False, comment="这个特定文本块的内容")

    embedding = Column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=False,
        comment="此文本块的半精度嵌入向量",
    )

    created_at = Column(DateTime, server_default=func.now())

    # 回到 CommunityMemberProfile 的多对一关系
    profile = relationship("CommunityMemberProfile", back_populates="chunks")

    def __repr__(self):
        return f"<CommunityMemberChunk(id={self.id}, profile_id={self.profile_id}, chunk_index={self.chunk_index})>"


class TokenUsage(Base):
    """
    记录每天的Token使用情况。
    """

    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    date: Mapped[datetime.datetime] = mapped_column(
        nullable=False, unique=True, default=datetime.datetime.utcnow
    )
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    total_tokens: Mapped[int] = mapped_column(default=0)
    call_count: Mapped[int] = mapped_column(default=0)

    def __repr__(self):
        return f"<TokenUsage(date={self.date}, total_tokens={self.total_tokens})>"


# --- 用户设置模型 (PostgreSQL) ---


class UserToolSettings(Base):
    """
    存储每个用户的工具启用设置。
    用户可以控制在自己的帖子里类脑娘可以使用哪些工具。
    默认启用所有工具，如果用户没有设置记录。
    """

    __tablename__ = "user_tool_settings"
    __table_args__ = {"schema": USER_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="用户的Discord ID"
    )
    enabled_tools: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        comment="用户启用的工具列表（JSON格式），为null表示启用所有工具",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<UserToolSettings(user_id='{self.user_id}')>"


# --- 商店商品模型 (PostgreSQL) ---


class ShopItem(Base):
    """
    商店商品表，用于存储商品配置和CG图片URL。
    商品数据从SQLite迁移到PostgreSQL，用户数据保留在SQLite。
    """

    __tablename__ = "shop_items"
    __table_args__ = {"schema": SHOP_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, comment="商品名称"
    )
    description: Mapped[str] = mapped_column(Text, nullable=True, comment="商品描述")
    price: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="商品价格（类脑币）"
    )
    category: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="商品类别"
    )
    target: Mapped[str] = mapped_column(
        String(50), nullable=False, default="self", comment="商品目标（self/ai）"
    )
    effect_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="商品效果ID"
    )
    cg_url: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, comment="CG图片的Discord链接列表"
    )
    is_available: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="是否可用（1=可用，0=不可用）"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<ShopItem(id={self.id}, name='{self.name}', price={self.price})>"
