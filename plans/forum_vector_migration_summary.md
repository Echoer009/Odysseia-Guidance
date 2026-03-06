# 论坛帖子向量迁移总结

## 已完成的工作

### 1. 数据库模型定义 ✅

在 [`src/database/models.py`](src/database/models.py) 中添加了以下模型：

- `FORUM_SCHEMA = "forum"` - 论坛 schema 定义
- `ForumDocument` - 论坛帖子文档表
  - 存储帖子元数据（thread_id, thread_name, author_name, author_id, category_name, channel_id, guild_id, created_at, created_timestamp, original_content, source_metadata）
  - 与 `ForumChunk` 建立一对多关系

- `ForumChunk` - 论坛帖子分块表
  - 存储分块数据（chunk_index, chunk_text, embedding）
  - HNSW 索引配置：`m=16, ef_construction=64, halfvec_cosine_ops`
  - 使用 `HALFVEC(3072)` 存储向量

### 2. Alembic 迁移文件 ✅

创建了 [`alembic/versions/add_forum_vector_tables.py`](alembic/versions/add_forum_vector_tables.py)：

- 创建 `forum` schema（如果不存在）
- 创建 `forum.forum_documents` 表
- 创建 `forum.forum_chunks` 表
- 创建 `idx_forum_embedding_hnsw` 索引用于向量搜索
- 包含完整的 upgrade 和 downgrade 逻辑

**迁移已执行**：表结构已在 PostgreSQL 中创建

### 3. 数据迁移脚本 ✅

创建了 [`scripts/migrate_forum_to_paradedb.py`](scripts/migrate_forum_to_paradedb.py)：

**功能**：
- 从 ChromaDB 读取所有论坛帖子数据
- 按 `thread_id` 分组数据
- 重建完整内容（按顺序连接所有分块）
- 写入 PostgreSQL 的 `forum_documents` 和 `forum_chunks` 表
- 支持 `--dry-run` 模式用于测试
- 支持 `--limit N` 限制迁移数量用于测试

**使用方法**：
```bash
# 测试模式（不写入数据库）
python scripts/migrate_forum_to_paradedb.py --dry-run

# 限制数量测试
python scripts/migrate_forum_to_paradedb.py --limit 10

# 实际迁移
python scripts/migrate_forum_to_paradedb.py
```

### 4. ForumVectorDBService 重构 ✅

完全重写了 [`src/chat/features/forum_search/services/forum_vector_db_service.py`](src/chat/features/forum_search/services/forum_vector_db_service.py)：

**主要变化**：
- 移除 ChromaDB 依赖
- 使用 SQLAlchemy 异步会话
- 实现以下方法：
  - `is_available()` - 检查服务可用性
  - `add_documents()` - 添加或更新帖子及其分块
  - `delete_documents()` - 删除指定帖子
  - `get_all_indexed_thread_ids()` - 获取所有已索引帖子 ID
  - `get_oldest_indexed_thread_timestamp()` - 获取最旧帖子时间戳
  - `search()` - 向量搜索（使用余弦距离）
  - `get()` - 按元数据获取文档

**向量搜索实现**：
- 使用 `pgvector.sqlalchemy.halfvec.HALFVEC`
- 余弦距离计算：`1 - cosine_distance(embedding, query_embedding)`
- 支持元数据过滤（category_name, author_id, author_name, start_date, end_date）
- 距离阈值过滤

### 5. ForumSearchService 适配 ✅

更新了 [`src/chat/features/forum_search/services/forum_search_service.py`](src/chat/features/forum_search/services/forum_search_service.py)：

**更新的方法**：

1. `process_thread()` - 处理单个帖子
   - 适配新的 `add_documents()` API
   - 传递所有必需参数（thread_id, thread_name, author_name, author_id, category_name, channel_id, guild_id, created_at, created_timestamp, original_content, chunks_data）

2. `add_documents_batch()` - 批量添加文档
   - 适配新的 `add_documents()` API
   - 为每个文档单独调用 `add_documents()`

3. `get_oldest_indexed_thread_timestamp()` - 获取最旧帖子时间戳
   - 使用新的 `get_oldest_indexed_thread_timestamp()` API

4. `search()` - 执行搜索
   - 适配新的 `search()` 和 `get()` API
   - 移除 ChromaDB 特定的语法（`$eq`, `$in`, `$gte`, `$lte`）
   - 直接传递 filters 字典给 PostgreSQL

## 待完成的工作

### 6. 配置更新 ⏳

需要更新 [`src/chat/config/chat_config.py`](src/chat/config/chat_config.py)：

**可选**：
- 标记旧的 ChromaDB 配置为已弃用
- 添加新的 PostgreSQL 配置（如果需要）

**建议**：
```python
# 保留旧配置用于备份
# FORUM_VECTOR_DB_PATH = "data/forum_chroma_db"
# FORUM_VECTOR_DB_COLLECTION_NAME = "forum_threads"

# 添加注释说明已迁移到 PostgreSQL
# 论坛帖子向量已迁移到 PostgreSQL forum schema
# 旧 ChromaDB 配置已弃用，保留用于备份
```

### 7. 测试 ⏳

**需要测试的功能**：

1. **数据迁移脚本**
   ```bash
   # 先用 dry-run 测试
   python scripts/migrate_forum_to_paradedb.py --dry-run

   # 小批量测试
   python scripts/migrate_forum_to_paradedb.py --limit 10

   # 完整迁移
   python scripts/migrate_forum_to_paradedb.py
   ```

2. **向量搜索功能**
   - 测试语义搜索（有查询关键词）
   - 测试元数据浏览（无查询关键词）
   - 测试各种过滤条件（category_name, author_id, start_date, end_date）
   - 验证距离阈值过滤

3. **帖子索引功能**
   - 测试新帖子索引
   - 测试帖子更新
   - 测试帖子删除

4. **回溯任务**
   - 测试 `get_oldest_indexed_thread_timestamp()`
   - 验证回溯任务正常工作

### 8. 清理旧数据 ⏳

**可选**（确认迁移成功后）：

1. 备份旧的 ChromaDB 数据：
   ```bash
   cp -r data/forum_chroma_db data/forum_chroma_db.backup
   ```

2. 删除旧的 ChromaDB 数据：
   ```bash
   rm -rf data/forum_chroma_db
   ```

3. 移除 ChromaDB 依赖（如果不再需要）：
   ```bash
   pip uninstall chromadb
   ```

## 关键注意事项

### 数据一致性

- **向量维度**：ChromaDB 和 PostgreSQL 都使用 3072 维，无需重新生成嵌入
- **分块逻辑**：保持一致（max_chars=1000）
- **时间戳格式**：正确转换 ISO 字符串和 Unix 时间戳

### 性能考虑

- **HNSW 索引**：使用与现有表相同的配置（m=16, ef_construction=64）
- **批量操作**：迁移脚本使用批量插入提高性能
- **异步操作**：所有数据库操作都是异步的

### 错误处理

- **迁移脚本**：包含详细的错误处理和日志记录
- **服务层**：捕获并记录所有异常
- **回滚机制**：失败时自动回滚事务

## 迁移步骤总结

1. ✅ 分析当前 ChromaDB 存储结构和数据模型
2. ✅ 分析现有 PostgreSQL 模式和模型
3. ✅ 设计目标数据库模型 (ForumDocument 和 ForumChunk)
4. ✅ 创建迁移分析文档
5. ✅ 创建架构图文档
6. ✅ 创建论坛帖子数据库模型 (ForumDocument 和 ForumChunk)
7. ✅ 创建 Alembic 迁移文件，定义表结构和索引
8. ✅ 运行迁移创建表结构
9. ✅ 创建数据迁移脚本，从 ChromaDB 读取数据并写入 PostgreSQL
10. ✅ 重构 ForumVectorDBService，使用 PostgreSQL 替代 ChromaDB
11. ✅ 更新 ForumSearchService 以适配新的数据库服务
12. ✅ 创建迁移总结文档
13. ⏳ 更新相关配置和依赖
14. ⏳ 测试迁移脚本和搜索功能
15. ⏳ 清理旧的 ChromaDB 数据（可选）

## 相关文件

### 新创建的文件
- [`plans/forum_vector_migration_analysis.md`](plans/forum_vector_migration_analysis.md) - 详细迁移分析
- [`plans/forum_vector_migration_architecture.md`](plans/forum_vector_migration_architecture.md) - 架构图
- [`plans/forum_vector_migration_summary.md`](plans/forum_vector_migration_summary.md) - 本总结文档
- [`scripts/migrate_forum_to_paradedb.py`](scripts/migrate_forum_to_paradedb.py) - 数据迁移脚本
- [`alembic/versions/add_forum_vector_tables.py`](alembic/versions/add_forum_vector_tables.py) - 数据库迁移文件

### 修改的文件
- [`src/database/models.py`](src/database/models.py) - 添加 ForumDocument 和 ForumChunk 模型
- [`src/chat/features/forum_search/services/forum_vector_db_service.py`](src/chat/features/forum_search/services/forum_vector_db_service.py) - 完全重写使用 PostgreSQL
- [`src/chat/features/forum_search/services/forum_search_service.py`](src/chat/features/forum_search/services/forum_search_service.py) - 适配新 API

## 下一步

1. **运行数据迁移脚本**
   ```bash
   python scripts/migrate_forum_to_paradedb.py --dry-run
   python scripts/migrate_forum_to_paradedb.py
   ```

2. **测试搜索功能**
   - 使用 Discord 机器人测试论坛搜索
   - 验证语义搜索正常工作
   - 验证元数据过滤正常工作

3. **更新配置**（可选）
   - 标记旧配置为已弃用
   - 添加迁移说明

4. **清理旧数据**（可选）
   - 备份 ChromaDB 数据
   - 删除旧的 ChromaDB 数据目录

---

*创建日期: 2026-03-06*
*状态: 代码实现完成，待测试*
