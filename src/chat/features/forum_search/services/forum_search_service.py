# -*- coding: utf-8 -*-

import logging
from typing import List, Dict, Any
import discord
from datetime import datetime, time
from zoneinfo import ZoneInfo

from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)
from src.chat.features.world_book.services.incremental_rag_service import (
    create_text_chunks,
)
from src.chat.services.regex_service import regex_service

log = logging.getLogger(__name__)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class ForumSearchService:
    """
    核心服务，负责处理论坛帖子的索引和搜索。
    """

    def __init__(self):
        self.gemini_service = None
        self.vector_db_service = forum_vector_db_service

    def _get_gemini_service(self):
        """延迟导入 Gemini 服务以避免循环导入。"""
        if self.gemini_service is None:
            from src.chat.services.gemini_service import gemini_service

            self.gemini_service = gemini_service
        return self.gemini_service

    def is_ready(self) -> bool:
        """检查服务是否已准备好。"""
        gemini_service = self._get_gemini_service()
        return gemini_service.is_available() and self.vector_db_service.is_available()

    async def process_thread(self, thread: discord.Thread):
        """
        处理单个论坛帖子，将其内容向量化并存入数据库。
        """
        if not self.is_ready():
            log.warning("论坛搜索服务尚未准备就绪，无法处理帖子。")
            return

        try:
            # 1. 获取首楼消息
            # messages.next() 在 v2.0 中已弃用, 使用 history()
            first_message = await anext(thread.history(limit=1, oldest_first=True))
            if not first_message:
                log.warning(f"无法获取帖子 {thread.id} 的首楼消息。")
                return

            # 2. 构建文档
            # 清理标题中的换行符和回车符，以确保数据一致性
            title = thread.name.replace("\n", " ").replace("\r", " ")
            content = first_message.content

            # 2. 获取作者信息 (更稳健的方式)
            author_id = thread.owner_id
            author_name = "未知作者"
            if author_id:
                # 优先从缓存中获取
                author = thread.owner or thread.guild.get_member(author_id)
                if not author:
                    try:
                        # 缓存未命中，则通过 API 拉取
                        log.info(
                            f"缓存未命中，正在为帖子 {thread.id} 拉取作者信息 (ID: {author_id})..."
                        )
                        author = await thread.guild.fetch_member(author_id)
                    except discord.NotFound:
                        log.warning(
                            f"无法为帖子 {thread.id} 找到作者 (ID: {author_id})，可能已离开服务器。"
                        )
                    except discord.HTTPException as e:
                        log.error(
                            f"通过 API 获取作者 (ID: {author_id}) 信息时出错: {e}"
                        )

                if author:
                    # 使用 display_name，因为它能更好地反映用户在服务器中的昵称
                    author_name = author.display_name

            # 提取论坛频道的名称作为分类
            raw_category_name = thread.parent.name if thread.parent else "未知分类"
            category_name = regex_service.clean_channel_name(raw_category_name)
            document_text = content

            # 3. 文本分块
            chunks = create_text_chunks(document_text, max_chars=1000)
            if not chunks:
                log.warning(f"帖子 {thread.id} 的内容无法分块。")
                return

            # 4. 为每个块生成嵌入并准备数据
            ids_to_add = []
            documents_to_add = []
            embeddings_to_add = []
            metadatas_to_add = []

            beijing_created_at = thread.created_at.astimezone(BEIJING_TZ)

            for i, chunk in enumerate(chunks):
                chunk_id = f"{thread.id}:{i}"
                gemini_service = self._get_gemini_service()
                embedding = await gemini_service.generate_embedding(
                    text=chunk, title=title, task_type="retrieval_document"
                )
                if embedding:
                    ids_to_add.append(chunk_id)
                    documents_to_add.append(chunk)
                    embeddings_to_add.append(embedding)
                    metadatas_to_add.append(
                        {
                            "thread_id": thread.id,
                            "thread_name": title,
                            "author_name": author_name,
                            "author_id": author_id or 0,
                            "category_name": category_name,
                            "channel_id": thread.parent_id,
                            "guild_id": thread.guild.id,
                            "created_at": beijing_created_at.isoformat(),
                            "created_timestamp": beijing_created_at.timestamp(),
                        }
                    )

            # 5. 批量写入数据库
            if ids_to_add:
                self.vector_db_service.add_documents(
                    ids=ids_to_add,
                    documents=documents_to_add,
                    embeddings=embeddings_to_add,
                    metadatas=metadatas_to_add,
                )
                log.info(
                    f"成功将帖子 {thread.id} 的 {len(ids_to_add)} 个块添加到向量数据库。"
                )

        except Exception as e:
            log.error(f"处理帖子 {thread.id} 时发生错误: {e}", exc_info=True)

    async def get_oldest_indexed_thread_timestamp(self, channel_id: int) -> str | None:
        """
        获取指定频道中已索引的最旧帖子的创建时间戳。

        Args:
            channel_id (int): 目标论坛频道的ID。

        Returns:
            str | None: 最旧帖子的ISO 8601格式时间戳字符串，如果该频道没有任何帖子被索引，则返回None。
        """
        try:
            log.info(f"正在查询频道 {channel_id} 中已索引的最旧帖子...")
            # 使用 get 方法获取所有匹配频道的文档的元数据
            results = self.vector_db_service.get(
                where={"channel_id": channel_id}, include=["metadatas"]
            )

            metadatas = results.get("metadatas")
            if not metadatas:
                log.info(f"在频道 {channel_id} 中未找到任何已索引的帖子。")
                return None

            # 从元数据中提取所有的时间戳
            timestamps = [
                meta["created_at"] for meta in metadatas if "created_at" in meta
            ]

            if not timestamps:
                log.warning(f"频道 {channel_id} 的已索引帖子中缺少 created_at 元数据。")
                return None

            # 找到并返回最早的时间戳
            oldest_timestamp = min(timestamps)
            log.info(
                f"频道 {channel_id} 中最旧的已索引帖子的时间戳是: {oldest_timestamp}"
            )
            return oldest_timestamp

        except Exception as e:
            log.error(
                f"查询频道 {channel_id} 最旧帖子时间戳时发生错误: {e}", exc_info=True
            )
            return None

    async def search(
        self,
        query: str = None,
        n_results: int = 5,
        filters: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行高级语义搜索或按元数据浏览。
        - 如果提供了有效的 `query`，则执行语义搜索。
        - 如果 `query` 为 None 或空字符串，则按 `filters` 浏览，并按时间倒序返回最新结果。

        Args:
            query (str, optional): 搜索查询。
            n_results (int): 返回结果的数量。
            filters (Dict[str, Any], optional): 一个包含元数据过滤条件的字典。
                - `category_name` (str): 按指定的论坛频道名称进行过滤。
                - `author_id` (int): 按作者的Discord ID进行过滤。
                - `author_name` (str): 按作者的显示名称进行过滤。
                - `start_date` (str): 筛选发布日期在此日期之后的帖子 (格式: YYYY-MM-DD)。
                - `end_date` (str): 筛选发布日期在此日期之前的帖子 (格式: YYYY-MM-DD)。
        Returns:
            List[Dict[str, Any]]: 一个包含搜索结果字典的列表。
        """
        try:
            # 1. 构建 ChromaDB 的元数据过滤器 (where 子句)
            where_filter = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if value is None:
                        continue

                    if key == "start_date":
                        start_dt_naive = datetime.strptime(value, "%Y-%m-%d")
                        start_dt_aware = start_dt_naive.replace(tzinfo=BEIJING_TZ)
                        start_timestamp = start_dt_aware.timestamp()
                        conditions.append(
                            {"created_timestamp": {"$gte": start_timestamp}}
                        )
                    elif key == "end_date":
                        end_dt_naive = datetime.strptime(value, "%Y-%m-%d")
                        end_dt_aware = datetime.combine(end_dt_naive, time.max).replace(
                            tzinfo=BEIJING_TZ
                        )
                        end_timestamp = end_dt_aware.timestamp()
                        conditions.append(
                            {"created_timestamp": {"$lte": end_timestamp}}
                        )
                    else:
                        # 如果值是列表，使用 '$in' 进行 "或" 匹配
                        if isinstance(value, list):
                            conditions.append({key: {"$in": value}})
                        # 否则，使用 '$eq' 进行精确匹配
                        else:
                            conditions.append({key: {"$eq": value}})

                if len(conditions) > 1:
                    where_filter = {"$and": conditions}
                elif conditions:
                    where_filter = conditions[0]

            log.info(f"论坛搜索数据库过滤器 (where): {where_filter or '无'}")

            # 2. 根据是否有有效 query 决定执行语义搜索还是元数据浏览
            if query and query.strip():
                # --- 语义搜索逻辑 (需要 Gemini) ---
                if not self.is_ready():
                    log.error("论坛搜索服务（Gemini）尚未准备就绪，无法执行语义搜索。")
                    return []
                log.info(f"执行语义搜索，查询: '{query}'")
                gemini_service = self._get_gemini_service()
                query_embedding = await gemini_service.generate_embedding(
                    text=query, task_type="retrieval_query"
                )
                if not query_embedding:
                    log.warning("无法为查询生成嵌入向量。")
                    return []

                search_results = self.vector_db_service.search(
                    query_embedding=query_embedding,
                    n_results=n_results,
                    where_filter=where_filter,
                    max_distance=1.0,
                )
                return search_results
            else:
                # --- 元数据浏览逻辑 ---
                log.info("执行元数据浏览 (无查询关键词)。")
                if not where_filter:
                    log.warning("无关键词浏览模式下必须提供有效的过滤器。")
                    return []

                # 直接从数据库获取所有匹配的文档
                results = self.vector_db_service.get(
                    where=where_filter, include=["metadatas", "documents"]
                )
                ids = results.get("ids", [])
                metadatas = results.get("metadatas", [])
                documents = results.get("documents", [])

                if not ids:
                    return []

                # 重构结果以便排序
                reconstructed_results = [
                    {"id": id, "content": doc, "metadata": meta, "distance": 0.0}
                    for id, doc, meta in zip(ids, documents, metadatas)
                ]

                # 按创建时间倒序排序
                sorted_results = sorted(
                    reconstructed_results,
                    key=lambda x: x["metadata"].get("created_at", ""),
                    reverse=True,
                )

                # 返回最新的 n_results 个结果
                return sorted_results[:n_results]

        except Exception as e:
            log.error(f"执行论坛搜索时发生错误: {e}", exc_info=True)
            return []


# 全局实例
forum_search_service = ForumSearchService()
