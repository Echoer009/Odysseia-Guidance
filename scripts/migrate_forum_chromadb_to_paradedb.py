# -*- coding: utf-8 -*-
"""将论坛帖子从 ChromaDB 迁移到 ParadeDB 的脚本

此脚本执行两个步骤：
1. 从 ChromeDB 提取所有帖子的元数据和内容，保存为 JSON 文件
2. 使用 Docker 中的 Ollama bge-m3 模型生成向量，导入到 ParadeDB

运行前请确保：
1. Ollama 服务已启动并运行 bge-m3 模型（在 Docker 中）
2. ChromeDB 数据存在于 data/forum_chroma_db
3. PostgreSQL 数据库连接配置正确（.env 文件）
4. 已执行 alembic upgrade head 创建 forum.forum_threads 表

使用方法：
    # 执行完整迁移（步骤1 + 步骤2）
    python scripts/migrate_forum_chromadb_to_paradedb.py

    # 只执行步骤1：导出数据
    python scripts/migrate_forum_chromadb_to_paradedb.py --step export

    # 只执行步骤2：导入数据
    python scripts/migrate_forum_chromadb_to_paradedb.py --step import
"""

import argparse
import asyncio
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from tqdm import tqdm

# 设置 Docker 环境下的 Ollama 地址
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama:11434")
os.environ.setdefault("OLLAMA_MODEL", "bge-m3")

# 项目路径配置
current_script_path = os.path.abspath(__file__)
project_root = Path(__file__).resolve().parent.parent
sys_path = str(project_root)
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

# 项目导入
from src.chat.config import chat_config as config
from src.chat.services.ollama_embedding_service import OllamaEmbeddingService
from src.database.database import AsyncSessionLocal
from src.database.models import ForumThread
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# 日志配置
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# 导出文件路径
EXPORT_FILE = "data/forum_chroma_backup.json"
# 批处理大小
BATCH_SIZE = 50
# 并发数
CONCURRENCY_LIMIT = 5


class ForumMigrationService:
    """论坛数据迁移服务"""

    def __init__(self, ollama_service: Optional[OllamaEmbeddingService] = None):
        self.ollama_service = ollama_service
        self.chroma_db_path = config.FORUM_VECTOR_DB_PATH
        self.export_file = EXPORT_FILE

    def export_from_chromadb(self) -> Dict[str, Any]:
        """
        步骤1：从 ChromeDB 提取所有帖子的元数据和内容，保存为 JSON 文件

        Returns:
            导出的数据字典
        """
        log.info("=" * 60)
        log.info("步骤1：从 ChromeDB 导出数据")
        log.info("=" * 60)

        try:
            db_path = os.path.join(self.chroma_db_path, "chroma.sqlite3")
            log.info(f"ChromeDB 路径: {db_path}")

            if not os.path.exists(db_path):
                log.error(f"ChromeDB 文件不存在: {db_path}")
                raise FileNotFoundError(f"ChromeDB 文件不存在: {db_path}")

            # 只读模式连接 SQLite
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 确定文本列名称
            doc_col = "c0"
            log.info(f"文本列: {doc_col}")

            # 主查询：获取 ID、文本和元数据
            query = f"""
                SELECT 
                    e.id AS internal_id,
                    e.embedding_id AS thread_id,
                    fts.{doc_col} AS content
                FROM embeddings e
                JOIN embedding_fulltext_search_content fts ON e.id = fts.rowid
            """

            cursor.execute(query)

            # 准备副游标查询元数据
            meta_cursor = conn.cursor()

            threads = []
            count = 0
            skipped = 0

            log.info("开始提取数据...")

            while True:
                row = cursor.fetchone()
                if not row:
                    break

                thread_id = row["thread_id"]
                content = row["content"]
                internal_id = row["internal_id"]

                # 转换 thread_id 为整数
                # ChromeDB 的 embedding_id 格式是 "thread_id:0"，需要提取冒号前的部分
                try:
                    if isinstance(thread_id, str) and ":" in thread_id:
                        thread_id = thread_id.split(":")[0]
                    thread_id = int(thread_id)
                except (ValueError, TypeError):
                    log.warning(f"无效的 thread_id: {row['thread_id']}，跳过")
                    skipped += 1
                    continue

                # 转换内容为字符串
                if not isinstance(content, str):
                    content = str(content) if content is not None else ""

                if not content.strip():
                    log.warning(f"帖子 {thread_id} 内容为空，跳过")
                    skipped += 1
                    continue

                # 提取元数据
                metadata = {}
                try:
                    meta_cursor.execute(
                        "SELECT key, string_value, int_value, float_value, bool_value FROM embedding_metadata WHERE id = ?",
                        (internal_id,),
                    )
                    meta_rows = meta_cursor.fetchall()

                    for m_row in meta_rows:
                        key = m_row[0]
                        # 依次判断哪一列有值
                        if m_row[1] is not None:
                            val = m_row[1]  # string
                        elif m_row[2] is not None:
                            val = m_row[2]  # int
                        elif m_row[3] is not None:
                            val = m_row[3]  # float
                        elif m_row[4] is not None:
                            val = bool(m_row[4])  # bool
                        else:
                            val = None

                        if val is not None:
                            metadata[key] = val

                except Exception as e:
                    log.warning(f"提取元数据失败 (thread_id: {thread_id}): {e}")

                # 构建帖子数据
                thread_data = {
                    "thread_id": thread_id,
                    "thread_name": metadata.get("thread_name", "无标题"),
                    "content": content,
                    "author_id": metadata.get("author_id", 0),
                    "author_name": metadata.get("author_name", "未知作者"),
                    "category_name": metadata.get("category_name", "未知分类"),
                    "channel_id": metadata.get("channel_id", 0),
                    "guild_id": metadata.get("guild_id", 0),
                    "created_at": metadata.get("created_at", None),
                }

                threads.append(thread_data)
                count += 1

                if count % 500 == 0:
                    log.info(f"已提取 {count} 条记录...")

            conn.close()

            log.info(f"提取完成：共 {count} 条记录，跳过 {skipped} 条")

            # 保存到 JSON 文件
            result = {
                "exported_at": datetime.utcnow().isoformat(),
                "total_count": count,
                "threads": threads,
            }

            self._save_to_json(result, self.export_file)

            log.info(f"数据已导出到: {self.export_file}")
            return result

        except Exception as e:
            log.error(f"导出 ChromeDB 数据失败: {e}", exc_info=True)
            raise

    def _save_to_json(self, data: Dict[str, Any], filepath: str):
        """保存数据到 JSON 文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_from_json(self, filepath: str) -> Dict[str, Any]:
        """从 JSON 文件加载数据"""
        if not os.path.exists(filepath):
            log.error(f"JSON 文件不存在: {filepath}")
            raise FileNotFoundError(f"JSON 文件不存在: {filepath}")

        log.info(f"从 JSON 文件加载数据: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    async def import_to_paradedb(self):
        """
        步骤2：读取 JSON 文件，使用 Ollama 向量化并导入 ParadeDB
        """
        log.info("=" * 60)
        log.info("步骤2：导入数据到 ParadeDB")
        log.info("=" * 60)

        if not self.ollama_service:
            log.error("OllamaEmbeddingService 未初始化")
            raise ValueError("OllamaEmbeddingService 未初始化")

        # 加载数据
        data = self._load_from_json(self.export_file)
        threads = data.get("threads", [])
        total_count = data.get("total_count", len(threads))

        log.info(f"共 {total_count} 条帖子待导入")

        # 批处理导入
        imported_count = 0
        failed_count = 0

        for i in range(0, len(threads), BATCH_SIZE):
            batch = threads[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(threads) + BATCH_SIZE - 1) // BATCH_SIZE

            log.info(
                f"处理批次 {batch_num}/{total_batches} (线程 {i + 1}-{i + len(batch)})"
            )

            # 并发向量化
            embedding_tasks = []
            for thread in batch:
                task = self._generate_embedding(thread)
                embedding_tasks.append(task)

            embeddings = await asyncio.gather(*embedding_tasks, return_exceptions=True)

            # 批量写入数据库
            for idx, thread in enumerate(batch):
                result = embeddings[idx]

                if isinstance(result, Exception):
                    log.error(
                        f"生成 embedding 失败 (thread_id: {thread['thread_id']}): {result}"
                    )
                    failed_count += 1
                    continue

                if not result:
                    log.warning(f"Embedding 为空 (thread_id: {thread['thread_id']})")
                    failed_count += 1
                    continue

                embedding = result

                # 写入数据库
                try:
                    await self._insert_thread(thread, embedding)  # type: ignore
                    imported_count += 1

                    if imported_count % 100 == 0:
                        log.info(f"已导入 {imported_count} 条记录")

                except Exception as e:
                    log.error(f"写入数据库失败 (thread_id: {thread['thread_id']}): {e}")
                    failed_count += 1

        log.info("=" * 60)
        log.info(f"导入完成：成功 {imported_count} 条，失败 {failed_count} 条")
        log.info("=" * 60)

    async def _generate_embedding(
        self, thread: Dict[str, Any]
    ) -> Optional[List[float]]:
        """生成帖子的向量嵌入"""
        try:
            # 组合标题和内容
            text = f"{thread['thread_name']}\n\n{thread['content']}"

            # 调用 Ollama 生成 embedding
            if not self.ollama_service:
                raise ValueError("ollama_service 未初始化")

            embedding = await self.ollama_service.generate_embedding(text)

            if embedding and len(embedding) == 1024:
                return embedding
            else:
                log.warning(
                    f"Embedding 维度不正确 (thread_id: {thread['thread_id']}): {len(embedding) if embedding else 0}"
                )
                return None

        except Exception as e:
            log.error(f"生成 embedding 错误 (thread_id: {thread['thread_id']}): {e}")
            raise

    async def _insert_thread(self, thread: Dict[str, Any], embedding: List[float]):
        """插入或更新帖子到 ParadeDB"""
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 检查是否已存在
                existing = await session.execute(
                    select(ForumThread).where(
                        ForumThread.thread_id == thread["thread_id"]
                    )
                )
                existing_thread = existing.scalar_one_or_none()

                # 解析 created_at
                created_at = thread.get("created_at")
                if created_at:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at)
                        # 移除时区信息，转换为 naive datetime
                        if created_at.tzinfo is not None:
                            created_at = created_at.replace(tzinfo=None)
                else:
                    created_at = datetime.utcnow()

                if existing_thread:
                    # 更新现有记录
                    existing_thread.thread_name = thread["thread_name"]
                    existing_thread.content = thread["content"]
                    existing_thread.author_id = thread["author_id"]
                    existing_thread.author_name = thread["author_name"]
                    existing_thread.category_name = thread["category_name"]
                    existing_thread.channel_id = thread["channel_id"]
                    existing_thread.guild_id = thread["guild_id"]
                    existing_thread.created_at = created_at
                    existing_thread.embedding = embedding
                    existing_thread.source_metadata = thread
                else:
                    # 创建新记录
                    new_thread = ForumThread(
                        thread_id=thread["thread_id"],
                        thread_name=thread["thread_name"],
                        content=thread["content"],
                        author_id=thread["author_id"],
                        author_name=thread["author_name"],
                        category_name=thread["category_name"],
                        channel_id=thread["channel_id"],
                        guild_id=thread["guild_id"],
                        created_at=created_at,
                        embedding=embedding,
                        source_metadata=thread,
                    )
                    session.add(new_thread)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="将论坛帖子从 ChromaDB 迁移到 ParadeDB"
    )
    parser.add_argument(
        "--step",
        choices=["export", "import", "all"],
        default="all",
        help="执行的步骤：export=导出, import=导入, all=全部（默认）",
    )
    args = parser.parse_args()

    # 初始化 Ollama 服务
    ollama_service = None
    if args.step in ["import", "all"]:
        try:
            ollama_service = OllamaEmbeddingService()
            log.info("OllamaEmbeddingService 初始化成功")
        except Exception as e:
            log.error(f"OllamaEmbeddingService 初始化失败: {e}")
            raise

    migration_service = ForumMigrationService(ollama_service)

    try:
        # 步骤1：导出
        if args.step in ["export", "all"]:
            migration_service.export_from_chromadb()

        # 步骤2：导入
        if args.step in ["import", "all"]:
            await migration_service.import_to_paradedb()

        log.info("迁移完成！")

    except Exception as e:
        log.error(f"迁移失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
