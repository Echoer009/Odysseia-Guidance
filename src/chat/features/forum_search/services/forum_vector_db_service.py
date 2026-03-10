# -*- coding: utf-8 -*-

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import select, text

from src.database.database import AsyncSessionLocal
from src.database.models import ForumThread

log = logging.getLogger(__name__)


class ForumVectorDBService:
    """
    专门用于论坛帖子语义搜索的向量数据库服务。
    使用 ParadeDB (PostgreSQL + pgvector) 进行向量搜索和 BM25 全文搜索。
    """

    def __init__(self):
        """初始化服务，ParadeDB 不需要单独的客户端连接"""
        log.info("ForumVectorDBService 已初始化 (使用 ParadeDB)")

    def is_available(self) -> bool:
        """检查服务是否可用"""
        # ParadeDB 始终可用，只要数据库连接正常
        return True

    def recreate_collection(self):
        """
        重新创建集合（ParadeDB 中对应表）。
        ParadeDB 使用数据库表，不需要显式删除和重新创建集合。
        这个方法保留以保持接口兼容性，但实际不做任何操作。
        """
        log.info("ParadeDB 使用数据库表，不需要重新创建集合。")

    async def add_document(
        self,
        thread_id: int,
        thread_name: str,
        content: str,
        author_id: int,
        author_name: str,
        category_name: str,
        channel_id: int,
        guild_id: int,
        created_at,
        embedding: List[float],
        source_metadata: Optional[dict] = None,
    ) -> bool:
        """
        添加单个论坛帖子到 ParadeDB。

        Args:
            thread_id: Discord 帖子 ID
            thread_name: 帖子标题
            content: 帖子内容
            author_id: 作者 Discord ID
            author_name: 作者名称
            category_name: 分类名称
            channel_id: 频道 ID
            guild_id: 服务器 ID
            created_at: 创建时间
            embedding: 向量嵌入
            source_metadata: 源元数据

        Returns:
            bool: 是否成功添加
        """
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # 检查是否已存在
                    existing = await session.execute(
                        select(ForumThread).where(ForumThread.thread_id == thread_id)
                    )
                    existing_thread = existing.scalar_one_or_none()

                    if existing_thread:
                        # 更新现有记录
                        existing_thread.thread_name = thread_name
                        existing_thread.content = content
                        existing_thread.author_id = author_id
                        existing_thread.author_name = author_name
                        existing_thread.category_name = category_name
                        existing_thread.channel_id = channel_id
                        existing_thread.guild_id = guild_id
                        existing_thread.created_at = created_at
                        existing_thread.embedding = embedding
                        existing_thread.source_metadata = source_metadata
                        log.info(f"更新现有帖子: {thread_id}")
                    else:
                        # 创建新记录
                        new_thread = ForumThread(
                            thread_id=thread_id,
                            thread_name=thread_name,
                            content=content,
                            author_id=author_id,
                            author_name=author_name,
                            category_name=category_name,
                            channel_id=channel_id,
                            guild_id=guild_id,
                            created_at=created_at,
                            embedding=embedding,
                            source_metadata=source_metadata,
                        )
                        session.add(new_thread)
                        log.info(f"添加新帖子: {thread_id}")

                    await session.commit()
                    return True

        except Exception as e:
            log.error(f"添加帖子 {thread_id} 到 ParadeDB 时出错: {e}", exc_info=True)
            return False

    async def get_all_indexed_thread_ids(self) -> List[int]:
        """
        从 ParadeDB 中获取所有已索引的帖子的唯一 thread_id。

        Returns:
            List[int]: 一个包含所有唯一 thread_id 的列表。
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(ForumThread.thread_id))
                thread_ids = [row[0] for row in result.fetchall()]
                return thread_ids
        except Exception as e:
            log.error(f"获取所有已索引的帖子ID时出错: {e}", exc_info=True)
            return []

    async def get_oldest_indexed_thread_timestamp(
        self, channel_id: int
    ) -> Optional[str]:
        """
        获取指定频道中已索引的最旧帖子的创建时间戳。

        Args:
            channel_id: 目标论坛频道的ID

        Returns:
            Optional[str]: 最旧帖子的ISO 8601格式时间戳字符串，如果该频道没有任何帖子被索引，则返回None。
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ForumThread.created_at)
                    .where(ForumThread.channel_id == channel_id)
                    .order_by(ForumThread.created_at.asc())
                    .limit(1)
                )
                row = result.scalar_one_or_none()
                if row:
                    return row.isoformat()
                return None
        except Exception as e:
            log.error(
                f"查询频道 {channel_id} 最旧帖子时间戳时发生错误: {e}", exc_info=True
            )
            return None

    async def search_bm25(
        self,
        query: str,
        n_results: int = 5,
        where_filter: Optional[dict] = None,
    ) -> List[dict]:
        """
        在 ParadeDB 中执行 BM25 全文搜索。

        Args:
            query: 搜索查询文本
            n_results: 返回结果数量
            where_filter: 过滤条件

        Returns:
            List[dict]: 搜索结果列表
        """
        try:
            async with AsyncSessionLocal() as session:
                # 构建 BM25 搜索查询
                # 使用 @@@ 操作符进行全文搜索，与世界书和教程搜索使用相同的方式
                sql_query = text(
                    """
                    SELECT
                        ft.id,
                        ft.thread_id,
                        ft.thread_name,
                        ft.author_name,
                        ft.author_id,
                        ft.category_name,
                        ft.channel_id,
                        ft.guild_id,
                        ft.created_at,
                        paradedb.score(ft.id) as score
                    FROM forum.forum_threads ft
                    WHERE ft.content @@@ :query
                    """
                )

                # 添加过滤条件
                params: Dict[str, Any] = {"query": query}
                conditions = []

                if where_filter:
                    for key, value in where_filter.items():
                        if value is None:
                            continue

                        if key == "category_name":
                            if isinstance(value, list):
                                placeholders = ", ".join(
                                    [f":cat_{i}" for i in range(len(value))]
                                )
                                conditions.append(
                                    f"ft.category_name IN ({placeholders})"
                                )
                                for i, v in enumerate(value):
                                    params[f"cat_{i}"] = v
                            else:
                                conditions.append("ft.category_name = :category_name")
                                params["category_name"] = value
                        elif key == "author_id":
                            conditions.append("ft.author_id = :author_id")
                            params["author_id"] = value
                        elif key == "author_name":
                            conditions.append("ft.author_name = :author_name")
                            params["author_name"] = value
                        elif key == "channel_id":
                            conditions.append("ft.channel_id = :channel_id")
                            params["channel_id"] = value
                        elif key == "start_date":
                            conditions.append("ft.created_at >= :start_date")
                            params["start_date"] = value
                        elif key == "end_date":
                            conditions.append("ft.created_at <= :end_date")
                            params["end_date"] = value

                if conditions:
                    sql_query = text(
                        sql_query.text + " AND " + " AND ".join(conditions)
                    )

                # 添加排序和限制
                sql_query = text(
                    sql_query.text
                    + """
                    ORDER BY score DESC
                    LIMIT :limit
                    """
                )
                params["limit"] = n_results

                result = await session.execute(sql_query, params)
                rows = result.fetchall()

                # 构建结果列表
                search_results = []
                for row in rows:
                    search_results.append(
                        {
                            "id": row.thread_id,
                            "metadata": {
                                "thread_id": row.thread_id,
                                "thread_name": row.thread_name,
                                "author_name": row.author_name,
                                "author_id": row.author_id,
                                "category_name": row.category_name,
                                "channel_id": row.channel_id,
                                "guild_id": row.guild_id,
                                "created_at": row.created_at.isoformat()
                                if row.created_at
                                else None,
                            },
                            "distance": 0.0,  # BM25 不返回距离，使用 0
                        }
                    )

                return search_results

        except Exception as e:
            log.error(f"在 ParadeDB 中执行 BM25 搜索时出错: {e}", exc_info=True)
            return []

    async def search_hybrid(
        self,
        query_embedding: List[float],
        query_text: str,
        where_filter: Optional[dict] = None,
        max_distance: float = 0.5,
    ) -> List[dict]:
        """
        在 ParadeDB 中执行混合搜索（向量 + BM25）。
        使用 RRF (Reciprocal Rank Fusion) 合并向量搜索和 BM25 搜索的结果。

        Args:
            query_embedding: 查询向量
            query_text: 查询文本（用于 BM25）
            where_filter: 过滤条件
            max_distance: 最大距离阈值

        Returns:
            List[dict]: 搜索结果列表
        """
        try:
            from src.chat.config.chat_config import FORUM_RAG_CONFIG

            top_k_vector = FORUM_RAG_CONFIG.get("TOP_K_VECTOR", 20)
            top_k_fts = FORUM_RAG_CONFIG.get("TOP_K_FTS", 20)
            rrf_k = FORUM_RAG_CONFIG.get("RRF_K", 60)
            final_k = FORUM_RAG_CONFIG.get("HYBRID_SEARCH_FINAL_K", 5)

            async with AsyncSessionLocal() as session:
                # 构建混合搜索查询
                # 使用 RRF (Reciprocal Rank Fusion) 合并向量搜索和 BM25 搜索的结果
                # 与世界书和教程搜索使用相同的实现方式
                sql_query = text(
                    """
                    WITH semantic_search AS (
                        SELECT
                            ft.id,
                            RANK() OVER (ORDER BY ft.embedding <=> CAST(:query_vector AS halfvec)) as rank
                        FROM forum.forum_threads ft
                        WHERE ft.embedding IS NOT NULL
                        ORDER BY ft.embedding <=> CAST(:query_vector AS halfvec)
                        LIMIT :top_k_vector
                    ),
                    keyword_search AS (
                        SELECT
                            ft.id,
                            RANK() OVER (ORDER BY paradedb.score(ft.id) DESC) as rank
                        FROM forum.forum_threads ft
                        WHERE ft.content @@@ :query_text
                        LIMIT :top_k_fts
                    ),
                    fused_ranks AS (
                        SELECT
                            COALESCE(s.id, k.id) as id,
                            (COALESCE(1.0 / (:rrf_k + s.rank), 0.0) + COALESCE(1.0 / (:rrf_k + k.rank), 0.0)) as rrf_score
                        FROM semantic_search s
                        FULL OUTER JOIN keyword_search k ON s.id = k.id
                    )
                    SELECT
                        ft.id,
                        ft.thread_id,
                        ft.thread_name,
                        ft.author_name,
                        ft.author_id,
                        ft.category_name,
                        ft.channel_id,
                        ft.guild_id,
                        ft.created_at,
                        fr.rrf_score
                    FROM fused_ranks fr
                    JOIN forum.forum_threads ft ON fr.id = ft.id
                    """
                )

                # 添加过滤条件
                params: Dict[str, Any] = {
                    "query_vector": str(query_embedding),
                    "query_text": query_text,
                    "top_k_vector": top_k_vector,
                    "top_k_fts": top_k_fts,
                    "rrf_k": rrf_k,
                }
                conditions = []

                if where_filter:
                    for key, value in where_filter.items():
                        if value is None:
                            continue

                        if key == "category_name":
                            if isinstance(value, list):
                                placeholders = ", ".join(
                                    [f":cat_{i}" for i in range(len(value))]
                                )
                                conditions.append(
                                    f"ft.category_name IN ({placeholders})"
                                )
                                for i, v in enumerate(value):
                                    params[f"cat_{i}"] = v
                            else:
                                conditions.append("ft.category_name = :category_name")
                                params["category_name"] = value
                        elif key == "author_id":
                            conditions.append("ft.author_id = :author_id")
                            params["author_id"] = value
                        elif key == "author_name":
                            conditions.append("ft.author_name = :author_name")
                            params["author_name"] = value
                        elif key == "channel_id":
                            conditions.append("ft.channel_id = :channel_id")
                            params["channel_id"] = value
                        elif key == "start_date":
                            conditions.append("ft.created_at >= :start_date")
                            params["start_date"] = value
                        elif key == "end_date":
                            conditions.append("ft.created_at <= :end_date")
                            params["end_date"] = value

                if conditions:
                    sql_query = text(
                        sql_query.text + " WHERE " + " AND ".join(conditions)
                    )

                # 添加排序和限制
                sql_query = text(
                    sql_query.text
                    + """
                    ORDER BY fr.rrf_score DESC
                    LIMIT :final_k
                    """
                )
                params["final_k"] = final_k

                result = await session.execute(sql_query, params)
                rows = result.fetchall()

                # 构建结果列表
                search_results = []
                for row in rows:
                    rrf_score = float(row.rrf_score) if row.rrf_score else 0.0
                    search_results.append(
                        {
                            "id": row.thread_id,
                            "metadata": {
                                "thread_id": row.thread_id,
                                "thread_name": row.thread_name,
                                "author_name": row.author_name,
                                "author_id": row.author_id,
                                "category_name": row.category_name,
                                "channel_id": row.channel_id,
                                "guild_id": row.guild_id,
                                "created_at": row.created_at.isoformat()
                                if row.created_at
                                else None,
                            },
                            "distance": rrf_score,  # 使用 RRF 分数
                        }
                    )

                log.info(
                    f"[FORUM_SEARCH] search_hybrid 返回 {len(search_results)} 条结果，RRF分数范围: {[r['distance'] for r in search_results]}"
                )
                return search_results

        except Exception as e:
            log.error(f"在 ParadeDB 中执行混合搜索时出错: {e}", exc_info=True)
            return []

    async def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where_filter: Optional[dict] = None,
        max_distance: float = 0.5,
    ) -> List[dict]:
        """
        在 ParadeDB 中执行向量相似度搜索。

        Args:
            query_embedding: 查询向量
            n_results: 返回结果数量
            where_filter: 过滤条件
            max_distance: 最大距离阈值

        Returns:
            List[dict]: 搜索结果列表
        """
        try:
            async with AsyncSessionLocal() as session:
                # 构建基础查询
                # 使用 ::halfvec 类型转换需要在 SQL 中直接使用 CAST
                sql_query = text(
                    """
                    SELECT
                        ft.id,
                        ft.thread_id,
                        ft.thread_name,
                        ft.author_name,
                        ft.author_id,
                        ft.category_name,
                        ft.channel_id,
                        ft.guild_id,
                        ft.created_at,
                        1 - (ft.embedding <=> CAST(:query_vector AS halfvec)) as similarity
                    FROM forum.forum_threads ft
                    WHERE ft.embedding IS NOT NULL
                    """
                )

                # 添加过滤条件
                params: Dict[str, Any] = {"query_vector": str(query_embedding)}
                conditions = []

                if where_filter:
                    for key, value in where_filter.items():
                        if value is None:
                            continue

                        if key == "category_name":
                            if isinstance(value, list):
                                placeholders = ", ".join(
                                    [f":cat_{i}" for i in range(len(value))]
                                )
                                conditions.append(
                                    f"ft.category_name IN ({placeholders})"
                                )
                                for i, v in enumerate(value):
                                    params[f"cat_{i}"] = v
                            else:
                                conditions.append("ft.category_name = :category_name")
                                params["category_name"] = value
                        elif key == "author_id":
                            conditions.append("ft.author_id = :author_id")
                            params["author_id"] = value
                        elif key == "author_name":
                            conditions.append("ft.author_name = :author_name")
                            params["author_name"] = value
                        elif key == "channel_id":
                            conditions.append("ft.channel_id = :channel_id")
                            params["channel_id"] = value
                        elif key == "start_date":
                            conditions.append("ft.created_at >= :start_date")
                            params["start_date"] = value
                        elif key == "end_date":
                            conditions.append("ft.created_at <= :end_date")
                            params["end_date"] = value

                if conditions:
                    sql_query = text(
                        sql_query.text + " AND " + " AND ".join(conditions)
                    )

                # 添加排序和限制
                sql_query = text(
                    sql_query.text
                    + """
                    ORDER BY similarity DESC
                    LIMIT :limit
                    """
                )
                params["limit"] = n_results

                result = await session.execute(sql_query, params)
                rows = result.fetchall()

                # 构建结果列表
                search_results = []
                for row in rows:
                    search_results.append(
                        {
                            "id": row.thread_id,
                            "metadata": {
                                "thread_id": row.thread_id,
                                "thread_name": row.thread_name,
                                "author_name": row.author_name,
                                "author_id": row.author_id,
                                "category_name": row.category_name,
                                "channel_id": row.channel_id,
                                "guild_id": row.guild_id,
                                "created_at": row.created_at.isoformat()
                                if row.created_at
                                else None,
                            },
                            "distance": 1.0 - row.similarity,  # 转换为距离
                        }
                    )

                return search_results

        except Exception as e:
            log.error(f"在 ParadeDB 中执行搜索时出错: {e}", exc_info=True)
            return []

    async def get(
        self, where: Optional[dict] = None, include: Optional[List[str]] = None
    ) -> dict:
        """
        从 ParadeDB 中获取文档（用于元数据浏览）。

        Args:
            where: 过滤条件
            include: 包含的字段列表

        Returns:
            dict: 包含 ids, metadatas 等的结果字典
        """
        try:
            async with AsyncSessionLocal() as session:
                # 构建查询
                stmt = select(ForumThread)

                # 添加过滤条件
                if where:
                    conditions = []
                    for key, value in where.items():
                        if value is None:
                            continue

                        if key == "channel_id":
                            conditions.append(ForumThread.channel_id == value)
                        elif key == "category_name":
                            if isinstance(value, list):
                                conditions.append(ForumThread.category_name.in_(value))
                            else:
                                conditions.append(ForumThread.category_name == value)
                        elif key == "author_id":
                            conditions.append(ForumThread.author_id == value)
                        elif key == "author_name":
                            conditions.append(ForumThread.author_name == value)

                    if conditions:
                        stmt = stmt.where(*conditions)

                result = await session.execute(stmt)
                threads = result.fetchall()

                # 构建结果
                ids = []
                metadatas = []

                for row in threads:
                    thread = row[0]
                    ids.append(str(thread.thread_id))
                    metadatas.append(
                        {
                            "thread_id": thread.thread_id,
                            "thread_name": thread.thread_name,
                            "author_name": thread.author_name,
                            "author_id": thread.author_id,
                            "category_name": thread.category_name,
                            "channel_id": thread.channel_id,
                            "guild_id": thread.guild_id,
                            "created_at": thread.created_at.isoformat()
                            if thread.created_at
                            else None,
                        }
                    )

                return {"ids": ids, "metadatas": metadatas}

        except Exception as e:
            log.error(f"从 ParadeDB 获取文档时出错: {e}", exc_info=True)
            return {"ids": [], "metadatas": []}


# 全局实例
forum_vector_db_service = ForumVectorDBService()
