# 论坛帖子向量从 ChromaDB 迁移到 PostgreSQL 分析

## 一、当前状态分析

### 1.1 ChromaDB 存储结构

**位置**: `data/forum_chroma_db`

**集合名称**: `forum_threads`

**数据结构**:
- 每个论坛帖子被分块存储（最大1000字符）
- 每个块包含:
  - `id`: 格式为 `{thread_id}:{chunk_index}`
  - `document`: 文本块内容
  - `embedding`: 3072维向量
  - `metadata`: 包含以下字段
    - `thread_id`: Discord帖子ID
    - `thread_name`: 帖子标题
    - `author_name`: 作者显示名称
    - `author_id`: 作者Discord ID
    - `category_name`: 论坛频道名称
    - `channel_id`: 父频道ID
    - `guild_id`: 服务器ID
    - `created_at`: ISO格式时间戳
    - `created_timestamp`: Unix时间戳

### 1.2 当前服务架构

```
ForumSearchService
    ↓
ForumVectorDBService (继承自 VectorDBService)
    ↓
ChromaDB (PersistentClient)
```

**关键文件**:
- `src/chat/features/forum_search/services/forum_vector_db_service.py`
- `src/chat/features/forum_search/services/forum_search_service.py`
- `src/chat/services/vector_db_service.py`

### 1.3 现有 PostgreSQL 模式

项目已使用 PostgreSQL + ParadeDB 存储其他向量数据，参考模型:
- `TutorialDocument` / `KnowledgeChunk` (tutorials schema)
- `GeneralKnowledgeDocument` / `GeneralKnowledgeChunk` (general_knowledge schema)
- `CommunityMemberProfile` / `CommunityMemberChunk` (community schema)

**共同特征**:
- 使用 `HALFVEC(3072)` 存储向量
- HNSW索引配置: `m=16, ef_construction=64, halfvec_cosine_ops`
- 文档-分块关联表结构
- 支持BM25全文搜索（可选）

## 二、迁移需求分析

### 2.1 数据库模型设计

需要在 `src/database/models.py` 中添加:

```python
# --- 论坛帖子模型 ---

FORUM_SCHEMA = "forum"

class ForumDocument(Base):
    """代表一个完整的论坛帖子"""
    __tablename__ = "forum_documents"
    __table_args__ = {"schema": FORUM_SCHEMA}

    id = Column(Integer, primary_key=True, index=True)
    thread_id = Column(String, unique=True, nullable=False, comment="Discord帖子ID")
    thread_name = Column(Text, nullable=False, comment="帖子标题")
    author_name = Column(String, nullable=True, comment="作者显示名称")
    author_id = Column(String, nullable=True, comment="作者Discord ID")
    category_name = Column(String, nullable=True, comment="论坛频道名称")
    channel_id = Column(String, nullable=True, comment="父频道ID")
    guild_id = Column(String, nullable=True, comment="服务器ID")
    created_at = Column(DateTime, nullable=False, comment="帖子创建时间")
    created_timestamp = Column(Float, nullable=False, comment="Unix时间戳")
    original_content = Column(Text, nullable=False, comment="完整原始内容")
    source_metadata = Column(JSON, nullable=True, comment="来自ChromaDB的完整元数据备份")

    # 与分块的一对多关系
    chunks = relationship("ForumChunk", back_populates="document", cascade="all, delete-orphan")


class ForumChunk(Base):
    """代表论坛帖子的一个文本块，及其对应的向量"""
    __tablename__ = "forum_chunks"
    __table_args__ = (
        Index(
            "idx_forum_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
        {"schema": FORUM_SCHEMA},
    )

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(
        Integer, ForeignKey(f"{FORUM_SCHEMA}.forum_documents.id"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False, comment="分块在帖子中的序号")
    chunk_text = Column(Text, nullable=False, comment="文本块内容")
    embedding = Column(
        HALFVEC(EMBEDDING_DIMENSION),
        nullable=False,
        comment="半精度嵌入向量",
    )
    created_at = Column(DateTime, server_default=func.now())

    # 回到 ForumDocument 的多对一关系
    document = relationship("ForumDocument", back_populates="chunks")
```

### 2.2 Alembic 迁移文件

需要创建新的迁移文件，包含:
1. 创建 `forum` schema（如果不存在）
2. 创建 `forum_documents` 表
3. 创建 `forum_chunks` 表
4. 创建 HNSW索引
5. （可选）创建BM25全文搜索索引

### 2.3 数据迁移脚本

需要创建 `scripts/migrate_forum_to_paradedb.py`，功能包括:
1. 连接 ChromaDB (`data/forum_chroma_db`)
2. 读取所有文档和元数据
3. 按thread_id分组，重建完整的帖子内容
4. 写入 PostgreSQL 的 `forum_documents` 和 `forum_chunks` 表
5. 支持dry-run模式
6. 支持进度显示和错误处理

### 2.4 服务层重构

需要重构 `ForumVectorDBService`:

**当前实现** (ChromaDB):
```python
class ForumVectorDBService(VectorDBService):
    def __init__(self):
        self.client = chromadb.PersistentClient(path=config.FORUM_VECTOR_DB_PATH)
        self.collection_name = config.FORUM_VECTOR_DB_COLLECTION_NAME
```

**目标实现** (PostgreSQL):
```python
class ForumVectorDBService:
    def __init__(self):
        self.session_factory = AsyncSessionLocal

    async def add_documents(self, thread_id: str, thread_name: str, 
                          author_name: str, author_id: str, 
                          category_name: str, channel_id: str, 
                          guild_id: str, created_at: datetime,
                          original_content: str, chunks_data: List[dict]):
        """添加帖子及其分块"""

    async def search(self, query_embedding: List[float], 
                    n_results: int = 5, 
                    filters: Optional[Dict] = None) -> List[Dict]:
        """向量搜索"""

    async def get_all_indexed_thread_ids(self) -> List[str]:
        """获取所有已索引的帖子ID"""

    async def get_oldest_indexed_thread_timestamp(self, channel_id: int) -> Optional[str]:
        """获取指定频道最旧的已索引帖子时间戳"""
```

### 2.5 ForumSearchService 适配

需要更新 `ForumSearchService` 以适配新的数据库服务:
- `process_thread()` 方法需要适配新的 API
- `search()` 方法需要适配新的查询接口
- `add_documents_batch()` 方法需要适配新的批量添加接口

## 三、迁移步骤

### 步骤1: 数据库模型定义
- 在 `src/database/models.py` 添加 `ForumDocument` 和 `ForumChunk` 模型

### 步骤2: 创建数据库迁移
- 运行 `alembic revision --autogenerate -m "add_forum_vector_tables"`
- 手动调整生成的迁移文件，确保 schema 和索引正确
- 运行 `alembic upgrade head`

### 步骤3: 数据迁移脚本
- 创建 `scripts/migrate_forum_to_paradedb.py`
- 实现从 ChromaDB 读取数据并写入 PostgreSQL 的逻辑
- 测试 dry-run 模式
- 执行实际迁移

### 步骤4: 服务层重构
- 重构 `ForumVectorDBService` 使用 PostgreSQL
- 更新 `ForumSearchService` 适配新服务

### 步骤5: 配置更新
- 更新 `src/chat/config/chat_config.py`，移除或标记旧的 ChromaDB 配置
- 更新依赖（如果需要）

### 步骤6: 测试
- 测试向量搜索功能
- 测试元数据过滤功能
- 测试帖子索引功能
- 测试回溯任务功能

### 步骤7: 清理（可选）
- 备份旧的 ChromaDB 数据
- 删除旧的 ChromaDB 数据目录

## 四、关键注意事项

### 4.1 数据一致性
- ChromaDB 中的嵌入向量已经是 3072 维，与 PostgreSQL 配置一致
- 需要确保时间戳格式正确转换
- 需要处理可能的数据缺失情况

### 4.2 性能考虑
- HNSW索引参数应与现有配置保持一致
- 批量插入时使用批量操作提高性能
- 考虑使用异步操作提高迁移速度

### 4.3 向后兼容
- 保留旧的 ChromaDB 服务代码作为备份
- 迁移完成后可以逐步移除
- 考虑添加回滚机制

### 4.4 错误处理
- 迁移脚本需要处理各种异常情况
- 记录详细的日志以便排查问题
- 支持断点续传

## 五、依赖更新

可能需要更新 `requirements.txt`:
- 确保已安装 `pgvector` 和 `sqlalchemy`
- 确保已安装 `asyncpg`（异步PostgreSQL驱动）
- ChromaDB 依赖可以保留，用于备份

## 六、测试计划

### 6.1 单元测试
- 测试模型定义
- 测试数据库操作
- 测试向量搜索

### 6.2 集成测试
- 测试完整的迁移流程
- 测试搜索功能
- 测试帖子索引功能

### 6.3 性能测试
- 对比 ChromaDB 和 PostgreSQL 的搜索性能
- 测试并发查询性能
- 测试大规模数据迁移性能

## 七、风险评估

| 风险         | 影响 | 缓解措施                         |
| ------------ | ---- | -------------------------------- |
| 数据丢失     | 高   | 迁移前备份ChromaDB数据           |
| 性能下降     | 中   | 使用相同的HNSW配置，进行性能测试 |
| 兼容性问题   | 中   | 充分测试，保留回滚方案           |
| 迁移时间过长 | 低   | 使用批量操作，支持断点续传       |

## 八、时间估算

（根据实际情况填写，不在此文档中提供具体时间）
