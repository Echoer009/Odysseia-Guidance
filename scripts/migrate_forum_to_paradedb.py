# -*- coding: utf-8 -*-

"""
将论坛帖子从 ChromaDB 迁移到 PostgreSQL (ParadeDB)

用法:
    python scripts/migrate_forum_to_paradedb.py [--dry-run] [--limit N]
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# --- 动态添加项目根目录到 sys.path ---
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# --- 路径设置结束 ---

import chromadb
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.database import AsyncSessionLocal
from src.database.models import ForumDocument, ForumChunk
from src.chat.config import chat_config as config

# --- 配置 ---
CHROMADB_PATH = config.FORUM_VECTOR_DB_PATH
CHROMADB_COLLECTION_NAME = config.FORUM_VECTOR_DB_COLLECTION_NAME

# 日志配置
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
log = logging.getLogger(__name__)


def get_chromadb_client():
    """连接到 ChromaDB"""
    try:
        client = chromadb.PersistentClient(path=CHROMADB_PATH)
        log.info(f"成功连接到 ChromaDB: {CHROMADB_PATH}")
        return client
    except Exception as e:
        log.error(f"连接 ChromaDB 失败: {e}", exc_info=True)
        raise


def read_chromadb_data(client, limit: Optional[int] = None) -> Dict[str, Any]:
    """
    从 ChromaDB 读取所有数据

    Args:
        limit: 限制读取的文档数量（用于测试）

    Returns:
        按thread_id分组的数据字典
    """
    log.info("开始从 ChromaDB 读取数据...")

    try:
        collection = client.get_collection(name=CHROMADB_COLLECTION_NAME)

        # 获取所有数据
        results = collection.get(include=["documents", "embeddings", "metadatas"])

        if not results or not results["ids"]:
            log.warning("ChromaDB 中没有数据")
            return {}

        ids = results["ids"]
        documents = results["documents"]
        embeddings = results["embeddings"]
        metadatas = results["metadatas"]

        # 应用限制
        if limit:
            ids = ids[:limit]
            documents = documents[:limit]
            embeddings = embeddings[:limit]
            metadatas = metadatas[:limit]
            log.info(f"限制读取数量为: {limit}")

        log.info(f"从 ChromaDB 读取了 {len(ids)} 个数据块")

        # 按 thread_id 分组
        grouped_data: Dict[str, Dict[str, Any]] = {}

        for i, (chunk_id, document, embedding, metadata) in enumerate(
            zip(ids, documents, embeddings, metadatas)
        ):
            thread_id = metadata.get("thread_id")
            if not thread_id:
                log.warning(f"数据块 {chunk_id} 缺少 thread_id，跳过")
                continue

            # 解析 chunk_id 格式: "{thread_id}:{chunk_index}"
            try:
                chunk_index = int(chunk_id.split(":")[-1])
            except (ValueError, IndexError):
                log.warning(f"无法解析 chunk_id: {chunk_id}，使用索引 {i}")
                chunk_index = i

            if thread_id not in grouped_data:
                # 初始化帖子数据
                grouped_data[thread_id] = {
                    "thread_id": thread_id,
                    "thread_name": metadata.get("thread_name", ""),
                    "author_name": metadata.get("author_name", ""),
                    "author_id": str(metadata.get("author_id", "")),
                    "category_name": metadata.get("category_name", ""),
                    "channel_id": str(metadata.get("channel_id", "")),
                    "guild_id": str(metadata.get("guild_id", "")),
                    "created_at": metadata.get("created_at", ""),
                    "created_timestamp": metadata.get("created_timestamp", 0.0),
                    "chunks": [],
                    "source_metadata": metadata,
                }

            # 添加分块数据
            grouped_data[thread_id]["chunks"].append(
                {
                    "chunk_index": chunk_index,
                    "chunk_text": document,
                    "embedding": embedding,
                }
            )

        # 按chunk_index排序分块
        for thread_id in grouped_data:
            grouped_data[thread_id]["chunks"].sort(key=lambda x: x["chunk_index"])

        log.info(f"数据分组完成，共 {len(grouped_data)} 个帖子")
        return grouped_data

    except Exception as e:
        log.error(f"读取 ChromaDB 数据时出错: {e}", exc_info=True)
        raise


def parse_created_at(created_at_str: str) -> datetime:
    """解析 ISO 格式的时间戳"""
    try:
        return datetime.fromisoformat(created_at_str)
    except (ValueError, TypeError):
        log.warning(f"无法解析时间戳: {created_at_str}，使用当前时间")
        return datetime.utcnow()


async def migrate_to_postgresql(
    session: AsyncSession,
    grouped_data: Dict[str, Dict[str, Any]],
    dry_run: bool = False,
) -> None:
    """
    将数据迁移到 PostgreSQL

    Args:
        session: SQLAlchemy 异步会话
        grouped_data: 按 thread_id 分组的数据
        dry_run: 是否为 dry-run 模式
    """
    log.info(f"开始迁移数据到 PostgreSQL (dry_run={dry_run})...")

    success_count = 0
    error_count = 0

    for thread_id, data in grouped_data.items():
        try:
            # 解析时间戳
            created_at = parse_created_at(data["created_at"])
            created_timestamp = float(data["created_timestamp"])

            # 创建 ForumDocument
            forum_doc = ForumDocument(
                thread_id=thread_id,
                thread_name=data["thread_name"],
                author_name=data["author_name"],
                author_id=data["author_id"],
                category_name=data["category_name"],
                channel_id=data["channel_id"],
                guild_id=data["guild_id"],
                created_at=created_at,
                created_timestamp=created_timestamp,
                # 重建完整内容（按顺序连接所有分块）
                original_content="\n".join(
                    chunk["chunk_text"] for chunk in data["chunks"]
                ),
                source_metadata=data["source_metadata"],
            )

            # 添加到会话
            session.add(forum_doc)

            # 刷新以获取 document_id
            if not dry_run:
                await session.flush()
                document_id = forum_doc.id

                # 创建 ForumChunk
                for chunk_data in data["chunks"]:
                    forum_chunk = ForumChunk(
                        document_id=document_id,
                        chunk_index=chunk_data["chunk_index"],
                        chunk_text=chunk_data["chunk_text"],
                        embedding=chunk_data["embedding"],
                    )
                    session.add(forum_chunk)

                success_count += 1

                if success_count % 10 == 0:
                    log.info(f"已迁移 {success_count} 个帖子...")

        except Exception as e:
            error_count += 1
            log.error(f"迁移帖子 {thread_id} 时出错: {e}", exc_info=True)
            if not dry_run:
                await session.rollback()
            else:
                # dry-run 模式下继续处理下一个
                continue

    # 提交事务
    if not dry_run and success_count > 0:
        try:
            await session.commit()
            log.info(f"成功迁移 {success_count} 个帖子到 PostgreSQL")
        except Exception as e:
            log.error(f"提交数据时出错: {e}", exc_info=True)
            await session.rollback()
            raise
    elif dry_run:
        log.info(f"DRY RUN 模式：将迁移 {success_count} 个帖子")

    if error_count > 0:
        log.warning(f"迁移过程中有 {error_count} 个帖子出错")


async def main():
    """主迁移函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="将论坛帖子从 ChromaDB 迁移到 PostgreSQL"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="执行检查但不提交任何数据到数据库",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制迁移的帖子数量（用于测试）",
    )
    args = parser.parse_args()

    try:
        # 1. 从 ChromaDB 读取数据
        client = get_chromadb_client()
        grouped_data = read_chromadb_data(client, limit=args.limit)

        if not grouped_data:
            log.error("没有数据可迁移")
            return

        # 2. 迁移到 PostgreSQL
        async with AsyncSessionLocal() as session:
            await migrate_to_postgresql(session, grouped_data, dry_run=args.dry_run)

        log.info("迁移完成！")

    except Exception as e:
        log.error(f"迁移过程中发生严重错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
