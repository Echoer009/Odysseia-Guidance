# -*- coding: utf-8 -*-
"""使用 Ollama 本地 bge-m3 模型重新生成论坛帖子 embedding 的脚本

此脚本用于将论坛帖子的 embedding 重新生成，使用 Docker 中的 Ollama 本地向量模型，
并使用余弦距离（cosine）。

运行前请确保：
1. Ollama 服务已启动并运行 bge-m3 模型（在 Docker 中）
2. .env 文件中的数据库配置正确
3. 论坛数据已存在于 ChromaDB 中

此脚本会直接从 ChromaDB 的 SQLite 文件中提取文本数据，然后使用 Ollama 重新生成 embedding。
"""

import asyncio
import logging
import argparse
import chromadb
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime
from tqdm import tqdm

# --- Path and Module Configuration ---
import os
import sys
from pathlib import Path

# 设置 Docker 环境下的 Ollama 地址
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama:11434")
os.environ.setdefault("OLLAMA_MODEL", "bge-m3")

current_script_path = os.path.abspath(__file__)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Project Imports ---
from src.chat.config import chat_config as config
from src.chat.services.ollama_embedding_service import OllamaEmbeddingService

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- Concurrency Configuration ---
CONCURRENCY_LIMIT = 5  # 降低并发数以减少内存占用
BATCH_SIZE = 50  # 减小批量大小以降低内存占用


class ForumReEmbedService:
    """论坛数据重新嵌入服务"""

    def __init__(self, ollama_service: OllamaEmbeddingService):
        self.ollama_service = ollama_service
        self.client = chromadb.PersistentClient(path=config.FORUM_VECTOR_DB_PATH)
        self.collection_name = config.FORUM_VECTOR_DB_COLLECTION_NAME
        self.collection = None

    def get_collection(self):
        """获取或创建集合"""
        if self.collection is None:
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self.collection

    def get_all_documents_from_sqlite(self) -> Dict[str, Any]:
        """
        从 ChromaDB 的 SQLite 文件中直接提取文本数据和元数据

        Returns:
            包含 ids, documents, metadatas 的字典
        """
        try:
            db_path = os.path.join(config.FORUM_VECTOR_DB_PATH, "chroma.sqlite3")
            log.info(f"正在从 SQLite 文件提取数据: {db_path}")

            # 只读模式连接
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 锁定文本列
            doc_col = "c0"
            log.info(f"锁定真实文本列: 【 {doc_col} 】")

            # 主查询：获取 ID、文本和元数据
            query = f"""
                SELECT 
                    e.id AS internal_id,
                    e.embedding_id AS user_id,
                    fts.{doc_col} AS document
                FROM embeddings e
                JOIN embedding_fulltext_search_content fts ON e.id = fts.rowid
            """

            cursor.execute(query)

            # 准备一个副游标查元数据
            meta_cursor = conn.cursor()

            ids = []
            documents = []
            metadatas = []

            count = 0
            while True:
                row = cursor.fetchone()
                if not row:
                    break

                # 提取基础信息
                user_id = row["user_id"]
                doc_content = row["document"]
                internal_id = row["internal_id"]

                # 类型检查
                if not isinstance(doc_content, str):
                    doc_content = str(doc_content) if doc_content is not None else ""
                    if not doc_content:
                        log.warning(f"警告: ID {user_id} 内容为空或非字符串")

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
                    log.warning(f"元数据提取失败 (ID: {user_id}): {e}")
                    metadata = {"error": "metadata_extraction_failed"}

                ids.append(user_id)
                documents.append(doc_content)
                metadatas.append(metadata)

                count += 1
                if count % 500 == 0:
                    log.info(f"已提取 {count} 条记录...")

            conn.close()
            log.info(f"共从 SQLite 提取到 {count} 条记录")

            return {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
        except Exception as e:
            log.error(f"从 SQLite 获取文档失败: {e}", exc_info=True)
            return {"ids": [], "documents": [], "metadatas": []}

    def get_all_documents(self) -> Dict[str, Any]:
        """
        从 ChromaDB 获取所有文档

        Returns:
            包含 ids, documents, metadatas 的字典
        """
        try:
            collection = self.get_collection()
            log.info("正在从 ChromaDB 获取所有文档...")

            # 获取所有文档，不包括 embeddings（因为我们要重新生成）
            results = collection.get(include=["documents", "metadatas"])

            ids = results.get("ids", [])
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])

            log.info(f"共获取到 {len(ids)} 个文档")

            return {
                "ids": ids,
                "documents": documents,
                "metadatas": metadatas,
            }
        except Exception as e:
            log.error(f"获取文档失败: {e}", exc_info=True)
            return {"ids": [], "documents": [], "metadatas": []}

    def clear_collection(self):
        """清空集合"""
        try:
            log.info(f"正在清空集合: {self.collection_name}...")
            self.client.delete_collection(name=self.collection_name)
            # 重新创建集合
            self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self.collection = None  # 重置集合引用
            log.info("集合已清空并重新创建")
        except Exception as e:
            log.error(f"清空集合失败: {e}", exc_info=True)
            raise

    def restore_backup(self, backup_data: Dict[str, Any]):
        """
        恢复备份数据

        Args:
            backup_data: 包含 ids, documents, metadatas 的字典
        """
        try:
            log.info("正在恢复备份数据...")
            collection = self.get_collection()

            ids = backup_data["ids"]
            documents = backup_data["documents"]
            metadatas = backup_data["metadatas"]

            # 恢复时不需要 embeddings，因为备份时没有保存
            # 使用 None 让 ChromaDB 自动处理 embeddings
            collection.add(
                ids=ids,
                documents=documents,
                embeddings=None,
                metadatas=metadatas,
            )

            log.info(f"成功恢复 {len(ids)} 条备份数据")
        except Exception as e:
            log.error(f"恢复备份数据失败: {e}", exc_info=True)
            raise

    async def re_embed_document(
        self, doc_id: str, document: str, metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        为单个文档重新生成 embedding

        Args:
            doc_id: 文档ID
            document: 文档内容
            metadata: 元数据

        Returns:
            包含 id, document, embedding, metadata 的字典，失败时返回 None
        """
        try:
            # 获取标题（用于生成更好的 embedding）
            title = metadata.get("thread_name", "")

            # 生成 embedding
            embedding = await self.ollama_service.generate_embedding(
                text=document, title=title, task_type="retrieval_document"
            )

            if embedding:
                return {
                    "id": doc_id,
                    "document": document,
                    "embedding": embedding,
                    "metadata": metadata,
                }
            else:
                log.warning(f"文档 {doc_id} 的 embedding 生成失败")
                return None
        except Exception as e:
            log.error(f"处理文档 {doc_id} 时出错: {e}", exc_info=True)
            return None

    async def re_embed_batch(
        self, doc_ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量重新生成 embedding（使用 Ollama 批量 API）

        Args:
            doc_ids: 文档ID列表
            documents: 文档内容列表
            metadatas: 元数据列表

        Returns:
            成功处理的文档列表
        """
        results = []

        try:
            # 使用 Ollama 批量 API 一次性生成所有 embeddings
            embeddings = await self.ollama_service.generate_embeddings_batch(
                documents, task_type="retrieval_document"
            )

            # 构建结果
            for i, embedding in enumerate(embeddings):
                if embedding is not None:
                    results.append(
                        {
                            "id": doc_ids[i],
                            "document": documents[i],
                            "embedding": embedding,
                            "metadata": metadatas[i],
                        }
                    )
                else:
                    log.warning(f"文档 {doc_ids[i]} 的 embedding 生成失败")

        except Exception as e:
            log.error(f"批量生成 embedding 失败: {e}", exc_info=True)

        return results

    def add_documents_to_collection(self, documents: List[Dict[str, Any]]):
        """
        将处理后的文档添加到集合

        Args:
            documents: 包含 id, document, embedding, metadata 的字典列表
        """
        try:
            if not documents:
                log.warning("没有文档需要添加")
                return

            collection = self.get_collection()

            ids = [doc["id"] for doc in documents]
            embeddings = [doc["embedding"] for doc in documents]
            documents_text = [doc["document"] for doc in documents]
            # 清理 metadata 中的保留键
            metadatas = []
            for doc in documents:
                metadata = doc["metadata"].copy()
                # 移除 ChromaDB 的保留键
                metadata.pop("chroma:document", None)
                metadatas.append(metadata)

            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents_text,
                metadatas=metadatas,
            )

            log.info(f"成功添加 {len(documents)} 个文档到集合")
        except Exception as e:
            log.error(f"添加文档失败: {e}", exc_info=True)
            raise

    async def re_embed_all(
        self,
        limit: Optional[int] = None,
        skip_clear: bool = False,
        use_sqlite: bool = True,
    ):
        """
        重新嵌入所有文档

        Args:
            limit: 限制处理的文档数量（用于测试）
            skip_clear: 是否跳过清空集合（用于增量更新）
            use_sqlite: 是否从 SQLite 文件中提取数据（默认 True）
        """
        start_time = datetime.now()
        log.info("=== 开始论坛数据重新嵌入 ===")

        # 1. 获取所有文档
        if use_sqlite:
            log.info("使用 SQLite 文件提取数据...")
            all_data = self.get_all_documents_from_sqlite()
        else:
            log.info("使用 ChromaDB API 获取数据...")
            all_data = self.get_all_documents()

        doc_ids = all_data["ids"]
        documents = all_data["documents"]
        metadatas = all_data["metadatas"]

        if not doc_ids:
            log.warning("没有找到任何文档，退出")
            return

        # 应用限制
        if limit:
            doc_ids = doc_ids[:limit]
            documents = documents[:limit]
            metadatas = metadatas[:limit]
            log.info(f"限制处理数量为 {limit}")

        total_docs = len(doc_ids)
        log.info(f"共需处理 {total_docs} 个文档")

        # 2. 备份现有数据（如果不清空）
        backup_data = None
        if not skip_clear:
            log.info("正在备份现有数据...")
            backup_data = self.get_all_documents()
            log.info(f"已备份 {len(backup_data['ids'])} 条记录")

        # 3. 清空集合（如果需要）
        if not skip_clear:
            self.clear_collection()
        else:
            log.info("跳过清空集合，将使用 upsert 模式")

        # 4. 批量处理
        success_count = 0
        fail_count = 0

        try:
            # 创建进度条（固定在底部）
            with tqdm(
                total=total_docs,
                desc="重新生成 embedding",
                unit="文档",
                position=0,
                leave=True,
            ) as pbar:
                for i in range(0, total_docs, BATCH_SIZE):
                    batch_start = i
                    batch_end = min(i + BATCH_SIZE, total_docs)

                    batch_ids = doc_ids[batch_start:batch_end]
                    batch_documents = documents[batch_start:batch_end]
                    batch_metadatas = metadatas[batch_start:batch_end]

                    # 重新生成 embedding
                    batch_results = await self.re_embed_batch(
                        batch_ids, batch_documents, batch_metadatas
                    )

                    # 添加到集合
                    if batch_results:
                        if skip_clear:
                            # 使用 upsert 模式
                            self.add_documents_to_collection(batch_results)
                        else:
                            # 使用 add 模式
                            self.add_documents_to_collection(batch_results)

                        success_count += len(batch_results)
                        fail_count += (batch_end - batch_start) - len(batch_results)

                    # 更新进度条
                    pbar.update(batch_end - batch_start)
                    pbar.set_postfix(
                        {
                            "成功": f"{success_count}/{total_docs}",
                            "失败": str(fail_count),
                        }
                    )

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            log.info("=== 论坛数据重新嵌入完成 ===")
            log.info(f"总文档数: {total_docs}")
            log.info(f"成功: {success_count}")
            log.info(f"失败: {fail_count}")
            log.info(f"耗时: {duration:.2f} 秒")

            # 打印处理的帖子标题
            log.info("\n=== 处理的帖子标题 ===")
            thread_names = set()
            for metadata in metadatas:
                thread_name = metadata.get("thread_name", "未知标题")
                thread_names.add(thread_name)

            for i, title in enumerate(sorted(thread_names), 1):
                log.info(f"{i}. {title}")
            log.info(f"\n共 {len(thread_names)} 个帖子")

        except Exception as e:
            log.error(f"处理过程中发生错误: {e}", exc_info=True)

            # 恢复备份数据
            if backup_data and not skip_clear:
                log.warning("正在恢复备份数据...")
                try:
                    self.restore_backup(backup_data)
                    log.info("备份数据已恢复")
                except Exception as restore_error:
                    log.error(f"恢复备份数据失败: {restore_error}", exc_info=True)
                    log.error("数据可能已损坏，请手动检查")

            raise


async def main():
    """主执行函数"""
    parser = argparse.ArgumentParser(
        description="使用 Ollama 本地 bge-m3 模型重新生成论坛帖子 embedding"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制处理的文档数量，用于测试",
    )
    parser.add_argument(
        "--skip-clear",
        action="store_true",
        help="跳过清空集合，使用 upsert 模式（用于增量更新）",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
        help="Ollama 服务地址",
    )
    parser.add_argument(
        "--use-sqlite",
        action="store_true",
        default=True,
        help="从 SQLite 文件中提取数据（默认启用）",
    )
    parser.add_argument(
        "--no-sqlite",
        action="store_true",
        help="使用 ChromaDB API 获取数据（不使用 SQLite）",
    )
    args = parser.parse_args()

    # 确定是否使用 SQLite
    use_sqlite = args.use_sqlite and not args.no_sqlite

    log.info("=== 论坛数据重新嵌入脚本启动 ===")
    log.info(f"限制数量: {args.limit if args.limit else '无限制'}")
    log.info(f"跳过清空: {args.skip_clear}")
    log.info(f"Ollama 地址: {args.ollama_url}")
    log.info(f"数据源: {'SQLite 文件' if use_sqlite else 'ChromaDB API'}")

    # 初始化 Ollama 服务
    ollama_service = OllamaEmbeddingService(base_url=args.ollama_url)

    # 检查连接
    if not await ollama_service.check_connection():
        log.error("无法连接到 Ollama 服务，请确保服务已启动")
        return

    log.info("Ollama 服务连接成功")

    # 初始化重新嵌入服务
    re_embed_service = ForumReEmbedService(ollama_service)

    # 执行重新嵌入
    try:
        await re_embed_service.re_embed_all(
            limit=args.limit, skip_clear=args.skip_clear, use_sqlite=use_sqlite
        )
    except KeyboardInterrupt:
        log.warning("用户中断了脚本执行")
    except asyncio.CancelledError:
        log.warning("任务被取消")
    except Exception as e:
        log.error(f"执行过程中发生错误: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
