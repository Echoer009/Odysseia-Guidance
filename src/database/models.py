import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
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
EMBEDDING_DIMENSION = 1024  # bge-m3 和 qwen3-embedding-0.6B 模型都使用 1024 维度
QWEN_EMBEDDING_DIMENSION = 1024  # qwen3-embedding-0.6B 模型的维度

# --- Schema 名称 ---
TUTORIALS_SCHEMA = "tutorials"
GENERAL_KNOWLEDGE_SCHEMA = "general_knowledge"
COMMUNITY_SCHEMA = "community"
SHOP_SCHEMA = "shop"
USER_SCHEMA = "user"
ECONOMY_SCHEMA = "economy"
FORUM_SCHEMA = "forum"

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
            "idx_bge_embedding_hnsw",
            "bge_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"bge_embedding": "halfvec_cosine_ops"},
        ),
        Index(
            "idx_qwen_embedding_hnsw",
            "qwen_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"qwen_embedding": "halfvec_cosine_ops"},
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

    bge_embedding = Column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=False,
        comment="BGE-M3 模型的嵌入向量。",
    )
    qwen_embedding = Column(
        HALFVEC(QWEN_EMBEDDING_DIMENSION),
        nullable=True,
        comment="Qwen3-Embedding-0.6B 模型的嵌入向量。",
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
            "idx_gk_bge_embedding_hnsw",
            "bge_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"bge_embedding": "halfvec_cosine_ops"},
        ),
        Index(
            "idx_gk_qwen_embedding_hnsw",
            "qwen_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"qwen_embedding": "halfvec_cosine_ops"},
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

    bge_embedding = Column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=False,
        comment="BGE-M3 模型的嵌入向量。",
    )
    qwen_embedding = Column(
        HALFVEC(QWEN_EMBEDDING_DIMENSION),
        nullable=True,
        comment="Qwen3-Embedding-0.6B 模型的嵌入向量。",
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
            "idx_cm_bge_embedding_hnsw",
            "bge_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"bge_embedding": "halfvec_cosine_ops"},
        ),
        Index(
            "idx_cm_qwen_embedding_hnsw",
            "qwen_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"qwen_embedding": "halfvec_cosine_ops"},
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

    bge_embedding = Column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=False,
        comment="BGE-M3 模型的嵌入向量。",
    )
    qwen_embedding = Column(
        HALFVEC(QWEN_EMBEDDING_DIMENSION),
        nullable=True,
        comment="Qwen3-Embedding-0.6B 模型的嵌入向量。",
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


class UserCommandSettings(Base):
    """
    存储每个用户的命令启用设置。
    用户可以控制在自己的帖子里哪些命令可以使用。
    默认启用所有命令，如果用户没有设置记录。
    """

    __tablename__ = "user_command_settings"
    __table_args__ = {"schema": USER_SCHEMA}

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="用户的Discord ID"
    )
    enabled_commands: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        comment="用户启用的命令列表（JSON格式），为null表示启用所有命令",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<UserCommandSettings(user_id='{self.user_id}')>"


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


# --- 论坛搜索模型 (ParadeDB) ---


class ForumThread(Base):
    """
    代表一个完整的论坛帖子。
    使用单表结构，不进行文本分块，支持混合搜索（向量+BM25）。
    """

    __tablename__ = "forum_threads"
    __table_args__ = (
        # HNSW 向量索引用于向量相似度搜索
        Index(
            "idx_forum_bge_embedding_hnsw",
            "bge_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"bge_embedding": "halfvec_cosine_ops"},
        ),
        Index(
            "idx_forum_qwen_embedding_hnsw",
            "qwen_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"qwen_embedding": "halfvec_cosine_ops"},
        ),
        # 创建时间索引用于排序
        Index("idx_forum_created_at", "created_at"),
        # 分类名称索引用于过滤
        Index("idx_forum_category", "category_name"),
        # 作者ID索引用于过滤
        Index("idx_forum_author", "author_id"),
        # 频道ID索引用于过滤
        Index("idx_forum_channel", "channel_id"),
        {"schema": FORUM_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Discord 帖子唯一标识
    thread_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, comment="Discord帖子的唯一ID"
    )

    # 帖子基本信息
    thread_name: Mapped[str] = mapped_column(Text, nullable=False, comment="帖子标题")
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="帖子完整内容（首楼）"
    )

    # 作者信息
    author_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="作者的Discord ID"
    )
    author_name: Mapped[str] = mapped_column(
        Text, nullable=False, comment="作者的显示名称"
    )

    # 分类和频道信息
    category_name: Mapped[str] = mapped_column(
        Text, nullable=False, comment="论坛频道名称（分类）"
    )
    channel_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="父频道的Discord ID"
    )
    guild_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="服务器的Discord ID"
    )

    # 时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, comment="帖子创建时间（Discord时间）"
    )

    # 可选字段
    source_metadata: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="来自旧系统的完整元数据备份"
    )
    bge_embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=True,
        comment="BGE-M3 模型的整帖内容向量嵌入（用于语义搜索）",
    )
    qwen_embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(QWEN_EMBEDDING_DIMENSION),
        nullable=True,
        comment="Qwen3-Embedding-0.6B 模型的整帖内容向量嵌入（用于语义搜索）",
    )

    # 数据库管理时间戳
    created_at_db: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="数据库记录创建时间"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="数据库记录更新时间",
    )

    def __repr__(self):
        return f"<ForumThread(id={self.id}, thread_id={self.thread_id}, thread_name='{self.thread_name}')>"


# --- 对话记忆块模型 (ParadeDB) ---


# 对话记忆使用的 schema
CONVERSATION_SCHEMA = "conversation"


class ConversationBlock(Base):
    """
    代表用户与类脑娘的一段对话块。
    每 block_size 条对话存储为一个块，支持向量检索实现"永久记忆"。
    使用混合搜索（向量+BM25）来检索相关历史对话。
    """

    __tablename__ = "conversation_blocks"
    __table_args__ = (
        # HNSW 向量索引用于向量相似度搜索
        Index(
            "idx_conv_bge_embedding_hnsw",
            "bge_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"bge_embedding": "halfvec_cosine_ops"},
        ),
        Index(
            "idx_conv_qwen_embedding_hnsw",
            "qwen_embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"qwen_embedding": "halfvec_cosine_ops"},
        ),
        # 用户ID索引用于过滤
        Index("idx_conv_discord_id", "discord_id"),
        # 开始时间索引用于排序
        Index("idx_conv_start_time", "start_time"),
        {"schema": CONVERSATION_SCHEMA},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # 用户标识
    discord_id: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="用户的Discord ID"
    )

    # 对话块内容
    conversation_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="对话块的原始文本内容"
    )

    # 时间范围（用于显示"X天前的对话"）
    start_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, comment="对话块中第一条消息的时间"
    )
    end_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, comment="对话块中最后一条消息的时间"
    )

    # 消息数量
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="对话块中的消息数量"
    )

    # 是否已被印象总结（用于方案E：每2个新块触发一次印象总结）
    summarized: Mapped[bool] = mapped_column(
        Integer,  # SQLite兼容：用 0/1 表示布尔值
        nullable=False,
        default=0,
        comment="是否已被印象总结（0=未总结，1=已总结）",
    )

    # 向量嵌入
    bge_embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=True,
        comment="BGE-M3 模型的对话内容向量嵌入（用于语义搜索）",
    )
    qwen_embedding: Mapped[list[float] | None] = mapped_column(
        HALFVEC(QWEN_EMBEDDING_DIMENSION),
        nullable=True,
        comment="Qwen3-Embedding-0.6B 模型的对话内容向量嵌入（用于语义搜索）",
    )

    # 数据库管理时间戳
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), comment="数据库记录创建时间"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="数据库记录更新时间",
    )

    def __repr__(self):
        return f"<ConversationBlock(id={self.id}, discord_id='{self.discord_id}', start_time={self.start_time})>"


# --- Economy 模型 (ParadeDB) ---


class UserCoins(Base):
    __tablename__ = "user_coins"
    __table_args__ = (
        Index("ix_coins_user_id", "user_id", unique=True),
        {"schema": ECONOMY_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    last_daily_message_date: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    last_red_envelope_date: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    coffee_effect_expires_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    has_withered_sunflower: Mapped[bool | None] = mapped_column(
        Integer, default=None, nullable=True
    )
    blocks_thread_replies: Mapped[bool] = mapped_column(Integer, default=0)
    thread_cooldown_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thread_cooldown_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thread_cooldown_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<UserCoins(user_id='{self.user_id}', balance={self.balance})>"


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"
    __table_args__ = (
        Index("ix_tx_user_id", "user_id"),
        Index("ix_tx_timestamp", "timestamp"),
        {"schema": ECONOMY_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    def __repr__(self):
        return f"<CoinTransaction(user_id='{self.user_id}', amount={self.amount})>"


class CoinLoan(Base):
    __tablename__ = "coin_loans"
    __table_args__ = (
        Index("ix_loans_user", "user_id"),
        {"schema": ECONOMY_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    paid_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return f"<CoinLoan(user_id='{self.user_id}', amount={self.amount}, status='{self.status}')>"


class InteractionLog(Base):
    __tablename__ = "interaction_logs"
    __table_args__ = (
        Index("ix_interact_user_type", "user_id", "interaction_type"),
        {"schema": ECONOMY_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    interaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    def __repr__(self):
        return f"<InteractionLog(user_id='{self.user_id}', type='{self.interaction_type}')>"


# --- User 扩展模型 (ParadeDB) ---


class UserAffection(Base):
    __tablename__ = "user_affection"
    __table_args__ = (
        Index("ix_affection_user_id", "user_id", unique=True),
        {"schema": USER_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    affection_points: Mapped[int] = mapped_column(Integer, default=0)
    daily_affection_gain: Mapped[int] = mapped_column(Integer, default=0)
    last_update_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_interaction_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_gift_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return (
            f"<UserAffection(user_id='{self.user_id}', points={self.affection_points})>"
        )


class UserWarningRecord(Base):
    __tablename__ = "user_warnings"
    __table_args__ = (
        Index("ix_warnings_user_guild", "user_id", "guild_id", unique=True),
        {"schema": USER_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    guild_id: Mapped[str] = mapped_column(String(50), nullable=False)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return (
            f"<UserWarningRecord(user_id='{self.user_id}', guild_id='{self.guild_id}')>"
        )


# --- AI Provider / Model 配置模型 (PostgreSQL) ---


AI_CONFIG_SCHEMA = "ai_config"


class AiProvider(Base):
    """
    AI 服务提供商配置表。
    通过 Discord UI 动态管理，API Key 加密存储。
    """

    __tablename__ = "ai_providers"
    __table_args__ = (
        Index("ix_ai_provider_name", "name", unique=True),
        {"schema": AI_CONFIG_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, comment="Provider 唯一标识名称"
    )
    provider_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Provider 类型: gemini / deepseek / openai_compatible",
    )
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="显示名称"
    )
    api_key_encrypted: Mapped[str] = mapped_column(
        Text, nullable=False, comment="加密后的 API Key"
    )
    base_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="API 基础 URL"
    )
    extra: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="额外配置参数 (JSON)"
    )
    enabled: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=1, comment="是否启用 (1=启用, 0=禁用)"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    models: Mapped[list["AiModel"]] = relationship(
        "AiModel", back_populates="provider", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<AiProvider(name='{self.name}', type='{self.provider_type}')>"


class AiModel(Base):
    """
    AI 模型配置表。
    每个 Model 关联到一个 AiProvider，通过 Discord UI 动态管理。
    """

    __tablename__ = "ai_models"
    __table_args__ = (
        Index("ix_ai_model_name", "model_name", unique=True),
        Index("ix_ai_model_provider", "provider_id"),
        {"schema": AI_CONFIG_SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    model_name: Mapped[str] = mapped_column(
        String(200), unique=True, nullable=False, comment="模型唯一标识 (如 deepseek-chat)"
    )
    display_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="模型显示名称"
    )
    provider_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{AI_CONFIG_SCHEMA}.ai_providers.id"),
        nullable=False,
        comment="所属 Provider ID",
    )
    actual_model: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="实际调用的模型名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="模型描述"
    )
    supports_vision: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, comment="是否支持视觉"
    )
    supports_tools: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=1, comment="是否支持工具调用"
    )
    supports_thinking: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0, comment="是否支持思考模式"
    )
    max_output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=8192, comment="最大输出 token 数"
    )
    generation_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="生成参数配置 (temperature, top_p 等)"
    )
    prompt_config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="提示词配置"
    )
    enabled: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=1, comment="是否启用 (1=启用, 0=禁用)"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    provider: Mapped["AiProvider"] = relationship("AiProvider", back_populates="models")

    def __repr__(self):
        return f"<AiModel(model_name='{self.model_name}', provider_id={self.provider_id})>"
