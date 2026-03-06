# -*- coding: utf-8 -*-

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, func, and_, text

from src.database.database import AsyncSessionLocal
from src.database.models import ForumDocument, ForumChunk

log = logging.getLogger(__name__)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class ForumVectorDBService:
    """
    专门用于论坛帖子语义搜索的向量数据库服务。
    使用 PostgreSQL + pgvector 替代 ChromaDB。
    """

    def __init__(self):
        self.session_factory = AsyncSessionLocal

    def is_available(self) -> bool:
        """检查服务是否可用"""
        return self.session_factory is not None

    async def add_documents(
        self,
        thread_id: str,
        thread_name: str,
        author_name: str,
        author_id: str,
        category_name: str,
        channel_id: str,
        guild_id: str,
        created_at: datetime,
        created_timestamp: float,
        original_content: str,
        chunks_data: List[Dict[str, Any]],
    ):
        """
        添加或更新帖子及其分块。

        Args:
            thread_id: Discord帖子ID
            thread_name: 帖子标题
            author_name: 作者显示名称
            author_id: 作者Discord ID
            category_name: 论坛频道名称
            channel_id: 父频道ID
            guild_id: 服务器ID
            created_at: 帖子创建时间
            created_timestamp: Unix时间戳
            original_content: 完整原始内容
            chunks_data: 分块数据列表，每个元素包含 chunk_index, chunk_text, embedding
        """
        async with self.session_factory() as session:
            try:
                # 检查帖子是否已存在
                result = await session.execute(
                    select(ForumDocument).where(ForumDocument.thread_id == thread_id)
                )
                existing_doc = result.scalar_one_or_none()

                if existing_doc:
                    # 删除旧的分块
                    await session.execute(
                        select(ForumChunk).where(
                            ForumChunk.document_id == existing_doc.id
                        )
                    )
                    # 更新文档
                    # type: ignore[attr-defined]  # Pylance doesn't understand SQLAlchemy instances
                    existing_doc.thread_name = thread_name  # type: ignore[attr-defined]
                    existing_doc.author_name = author_name  # type: ignore[attr-defined]
                    existing_doc.author_id = author_id  # type: ignore[attr-defined]
                    existing_doc.category_name = category_name  # type: ignore[attr-defined]
                    existing_doc.channel_id = channel_id  # type: ignore[attr-defined]
                    existing_doc.guild_id = guild_id  # type: ignore[attr-defined]
                    existing_doc.created_at = created_at  # type: ignore[attr-defined]
                    existing_doc.created_timestamp = created_timestamp  # type: ignore[attr-defined]
                    existing_doc.original_content = original_content  # type: ignore[attr-defined]
                    document_id = existing_doc.id
                    log.info(f"更新现有帖子: {thread_id}")
                else:
                    # 创建新文档
                    forum_doc = ForumDocument(
                        thread_id=thread_id,
                        thread_name=thread_name,
                        author_name=author_name,
                        author_id=author_id,
                        category_name=category_name,
                        channel_id=channel_id,
                        guild_id=guild_id,
                        created_at=created_at,
                        created_timestamp=created_timestamp,
                        original_content=original_content,
                    )
                    session.add(forum_doc)
                    await session.flush()
                    document_id = forum_doc.id
                    log.info(f"创建新帖子: {thread_id}")

                # 添加分块
                for chunk_data in chunks_data:
                    forum_chunk = ForumChunk(
                        document_id=document_id,
                        chunk_index=chunk_data["chunk_index"],
                        chunk_text=chunk_data["chunk_text"],
                        embedding=chunk_data["embedding"],
                    )
                    session.add(forum_chunk)

                await session.commit()
                log.info(f"成功添加/更新帖子 {thread_id} 的 {len(chunks_data)} 个分块")

            except Exception as e:
                await session.rollback()
                log.error(f"添加文档时出错: {e}", exc_info=True)
                raise

    async def delete_documents(self, thread_ids: List[str]):
        """
        删除指定的帖子。

        Args:
            thread_ids: 要删除的帖子ID列表
        """
        if not thread_ids:
            log.warning("尝试删除文档，但未提供任何 thread_id")
            return

        async with self.session_factory() as session:
            try:
                # 查找帖子
                result = await session.execute(
                    select(ForumDocument).where(ForumDocument.thread_id.in_(thread_ids))
                )
                docs = result.scalars().all()

                if not docs:
                    log.warning(f"未找到要删除的帖子: {thread_ids}")
                    return

                # 删除帖子（级联删除分块）
                for doc in docs:
                    await session.delete(doc)

                await session.commit()
                log.info(f"成功删除 {len(docs)} 个帖子")

            except Exception as e:
                await session.rollback()
                log.error(f"删除文档时出错: {e}", exc_info=True)
                raise

    async def get_all_indexed_thread_ids(self) -> List[str]:
        """
        获取所有已索引的帖子的唯一 thread_id。

        Returns:
            包含所有唯一 thread_id 的列表。
        """
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(ForumDocument.thread_id).distinct()
                )
                thread_ids = [row[0] for row in result.all()]
                return thread_ids
            except Exception as e:
                log.error(f"获取所有已索引的帖子ID时出错: {e}", exc_info=True)
                return []

    async def get_oldest_indexed_thread_timestamp(
        self, channel_id: str
    ) -> Optional[str]:
        """
        获取指定频道中已索引的最旧帖子的创建时间戳。

        Args:
            channel_id: 目标论坛频道的ID

        Returns:
            ISO 8601格式时间戳字符串，如果该频道没有任何帖子被索引，则返回None
        """
        async with self.session_factory() as session:
            try:
                result = await session.execute(
                    select(func.min(ForumDocument.created_at)).where(
                        ForumDocument.channel_id == channel_id
                    )
                )
                oldest_timestamp = result.scalar()

                if not oldest_timestamp:
                    log.info(f"频道 {channel_id} 中未找到任何已索引的帖子")
                    return None

                # 转换为 ISO 格式字符串
                if isinstance(oldest_timestamp, datetime):
                    return oldest_timestamp.isoformat()
                else:
                    return str(oldest_timestamp)

            except Exception as e:
                log.error(
                    f"查询频道 {channel_id} 最旧帖子时间戳时发生错误: {e}",
                    exc_info=True,
                )
                return None

    async def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        max_distance: float = 1.0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行向量搜索。

        Args:
            query_embedding: 查询的嵌入向量
            n_results: 返回结果的数量
            max_distance: 最大距离阈值
            filters: 元数据过滤条件

        Returns:
            包含搜索结果的字典列表
        """
        if not query_embedding:
            log.warning("接收到无效的 query_embedding，搜索将返回空结果")
            return []

        async with self.session_factory() as session:
            try:
                # 将 query_embedding 转换为 pgvector 的数组字符串格式
                embedding_str = str(query_embedding)

                # 构建基础查询
                base_query = """
                    SELECT
                        fc.*,
                        fd.*,
                        (fc.embedding <=> :query_vector) as distance
                    FROM forum.forum_chunks fc
                    JOIN forum.forum_documents fd ON fc.document_id = fd.id
                """

                # 构建过滤条件
                where_clauses = []
                params = {"query_vector": embedding_str, "limit": n_results}

                if filters:
                    for key, value in filters.items():
                        if value is None:
                            continue

                        if key == "start_date":
                            start_dt = datetime.strptime(value, "%Y-%m-%d")
                            start_dt_aware = start_dt.replace(tzinfo=BEIJING_TZ)
                            where_clauses.append(
                                f"fd.created_at >= '{start_dt_aware.isoformat()}'"
                            )
                        elif key == "end_date":
                            end_dt = datetime.strptime(value, "%Y-%m-%d")
                            end_dt_aware = end_dt.replace(
                                hour=23, minute=59, second=59, tzinfo=BEIJING_TZ
                            )
                            where_clauses.append(
                                f"fd.created_at <= '{end_dt_aware.isoformat()}'"
                            )
                        elif isinstance(value, list):
                            # 处理列表类型的过滤条件
                            value_list = ", ".join(f"'{v}'" for v in value)
                            where_clauses.append(f"fd.{key} IN ({value_list})")
                        else:
                            # 处理字符串类型的过滤条件
                            where_clauses.append(f"fd.{key} = '{value}'")

                # 组合完整的查询
                full_query = base_query
                if where_clauses:
                    full_query += " WHERE " + " AND ".join(where_clauses)
                full_query += " ORDER BY distance LIMIT :limit"

                # 执行查询
                query = text(full_query)
                result = await session.execute(query, params)
                rows = result.fetchall()

                # 将原始结果转换为对象
                results = []
                for row in rows:
                    # 跳过距离超过阈值的结果
                    distance = row.distance
                    if distance > max_distance:
                        continue

                    # 构建 ForumChunk 对象
                    chunk = ForumChunk(
                        id=row.id,
                        document_id=row.document_id,
                        chunk_index=row.chunk_index,
                        chunk_text=row.chunk_text,
                        embedding=row.embedding,
                    )

                    # 构建 ForumDocument 对象
                    doc = ForumDocument(
                        id=row.id_1,
                        thread_id=row.thread_id,
                        thread_name=row.thread_name,
                        author_name=row.author_name,
                        author_id=row.author_id,
                        category_name=row.category_name,
                        channel_id=row.channel_id,
                        guild_id=row.guild_id,
                        created_at=row.created_at,
                        created_timestamp=row.created_timestamp,
                        original_content=row.original_content,
                        source_metadata=row.source_metadata,
                    )

                    results.append(
                        {
                            "id": f"{doc.thread_id}:{chunk.chunk_index}",
                            "content": chunk.chunk_text,
                            "distance": distance,
                            "metadata": {
                                "thread_id": doc.thread_id,
                                "thread_name": doc.thread_name,
                                "author_name": doc.author_name,
                                "author_id": doc.author_id,
                                "category_name": doc.category_name,
                                "channel_id": doc.channel_id,
                                "guild_id": doc.guild_id,
                                "created_at": doc.created_at.isoformat()
                                if doc.created_at
                                else "",
                                "created_timestamp": doc.created_timestamp,
                            },
                        }
                    )

                log.info(
                    f"向量搜索完成，返回 {len(results)} 个结果（阈值: {max_distance}）"
                )
                return results

            except Exception as e:
                log.error(f"执行向量搜索时出错: {e}", exc_info=True)
                return []

    async def get(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        按元数据获取文档。

        Args:
            filters: 元数据过滤条件
            limit: 限制返回的数量

        Returns:
            包含 ids, metadatas 的字典
        """
        async with self.session_factory() as session:
            try:
                query = select(ForumDocument)

                # 应用过滤条件
                if filters:
                    conditions = []
                    for key, value in filters.items():
                        if value is None:
                            continue

                        if isinstance(value, list):
                            conditions.append(getattr(ForumDocument, key).in_(value))
                        else:
                            conditions.append(getattr(ForumDocument, key) == value)

                    if conditions:
                        query = query.where(and_(*conditions))

                # 按创建时间倒序排序
                query = query.order_by(ForumDocument.created_at.desc())

                if limit:
                    query = query.limit(limit)

                result = await session.execute(query)
                docs = result.scalars().all()

                # 格式化结果
                ids = [doc.thread_id for doc in docs]
                metadatas = [
                    {
                        "thread_id": doc.thread_id,
                        "thread_name": doc.thread_name,
                        "author_name": doc.author_name,
                        "author_id": doc.author_id,
                        "category_name": doc.category_name,
                        "channel_id": doc.channel_id,
                        "guild_id": doc.guild_id,
                        "created_at": doc.created_at.isoformat()
                        if doc.created_at
                        else "",
                        "created_timestamp": doc.created_timestamp,
                    }
                    for doc in docs
                ]

                return {"ids": ids, "metadatas": metadatas}

            except Exception as e:
                log.error(f"获取文档时出错: {e}", exc_info=True)
                return {"ids": [], "metadatas": []}


# 全局实例
forum_vector_db_service = ForumVectorDBService()
