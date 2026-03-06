# -*- coding: utf-8 -*-

import logging
from typing import List, Dict, Any
import discord
from datetime import datetime
from zoneinfo import ZoneInfo

from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)
from src.chat.features.world_book.services.incremental_rag_service import (
    create_text_chunks,
)
from src.chat.services.regex_service import regex_service
from src.chat.config import chat_config as config

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
            chunks_data = []

            beijing_created_at = (
                thread.created_at.astimezone(BEIJING_TZ)
                if thread.created_at
                else datetime.now(BEIJING_TZ)
            )

            for i, chunk in enumerate(chunks):
                gemini_service = self._get_gemini_service()
                embedding = await gemini_service.generate_embedding(
                    text=chunk, title=title, task_type="retrieval_document"
                )
                if embedding:
                    chunks_data.append(
                        {
                            "chunk_index": i,
                            "chunk_text": chunk,
                            "embedding": embedding,
                        }
                    )

            # 5. 写入数据库
            if chunks_data:
                await self.vector_db_service.add_documents(
                    thread_id=str(thread.id),
                    thread_name=title,
                    author_name=author_name,
                    author_id=str(author_id) if author_id else "",
                    category_name=category_name,
                    channel_id=str(thread.parent_id),
                    guild_id=str(thread.guild.id),
                    created_at=beijing_created_at,
                    created_timestamp=beijing_created_at.timestamp(),
                    original_content=content,
                    chunks_data=chunks_data,
                )
                log.info(
                    f"成功将帖子 {thread.id} 的 {len(chunks_data)} 个块添加到向量数据库。"
                )

        except Exception as e:
            log.error(f"处理帖子 {thread.id} 时发生错误: {e}", exc_info=True)

    async def add_documents_batch(
        self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]]
    ):
        """
        从备份数据批量添加文档，包含重新分块和向量化。
        这是为 --restore-from 功能设计的核心方法。
        """
        if not self.is_ready():
            log.warning("论坛搜索服务尚未准备就绪，无法添加文档。")
            return

        gemini_service = self._get_gemini_service()

        for doc_id, document, metadata in zip(ids, documents, metadatas):
            try:
                # 1. 文本分块 (与 process_thread 逻辑保持一致)
                chunks = create_text_chunks(document, max_chars=1000)
                if not chunks:
                    log.warning(f"文档 {doc_id} 的内容无法分块，已跳过。")
                    continue

                # 2. 为每个块生成嵌入
                chunks_data = []
                for i, chunk in enumerate(chunks):
                    embedding = await gemini_service.generate_embedding(
                        text=chunk,
                        title=metadata.get("thread_name", ""),
                        task_type="retrieval_document",
                    )
                    if embedding:
                        chunks_data.append(
                            {
                                "chunk_index": i,
                                "chunk_text": chunk,
                                "embedding": embedding,
                            }
                        )

                # 3. 写入数据库 (使用新 API)
                if chunks_data:
                    # 解析 created_at 时间
                    created_at_str = metadata.get("created_at")
                    created_at = datetime.now(BEIJING_TZ)
                    created_timestamp = created_at.timestamp()
                    if created_at_str:
                        try:
                            if isinstance(created_at_str, (int, float)):
                                created_at = datetime.fromtimestamp(
                                    created_at_str, BEIJING_TZ
                                )
                                created_timestamp = float(created_at_str)
                            else:
                                created_at = datetime.fromisoformat(created_at_str)
                                if created_at.tzinfo is None:
                                    created_at = created_at.replace(tzinfo=BEIJING_TZ)
                                created_timestamp = float(created_at.timestamp())
                        except Exception as e:
                            log.warning(
                                f"无法解析文档 {doc_id} 的 created_at: {e}，使用当前时间"
                            )

                    await self.vector_db_service.add_documents(
                        thread_id=str(doc_id),
                        thread_name=metadata.get("thread_name", ""),
                        author_name=metadata.get("author_name", ""),
                        author_id=str(metadata.get("author_id", "")),
                        category_name=metadata.get("category_name", ""),
                        channel_id=str(metadata.get("channel_id", "")),
                        guild_id=str(metadata.get("guild_id", "")),
                        created_at=created_at,
                        created_timestamp=created_timestamp,
                        original_content=document,
                        chunks_data=chunks_data,
                    )
                    log.info(
                        f"成功将文档 {doc_id} 的 {len(chunks_data)} 个块添加到向量数据库。"
                    )

            except Exception as e:
                log.error(f"为文档 {doc_id} 生成嵌入时发生错误: {e}", exc_info=True)

        log.info(f"成功将 {len(ids)} 个原始文档添加到向量数据库。")

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
            # 使用新的 API 方法
            oldest_timestamp = (
                await self.vector_db_service.get_oldest_indexed_thread_timestamp(
                    channel_id=str(channel_id)
                )
            )

            if oldest_timestamp:
                log.info(
                    f"频道 {channel_id} 中最旧的已索引帖子的时间戳是: {oldest_timestamp}"
                )
            else:
                log.info(f"在频道 {channel_id} 中未找到任何已索引的帖子。")

            return oldest_timestamp

        except Exception as e:
            log.error(
                f"查询频道 {channel_id} 最旧帖子时间戳时发生错误: {e}", exc_info=True
            )
            return None

    async def search(
        self,
        query: str | None = None,
        n_results: int = 5,
        filters: Dict[str, Any] | None = None,
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
            # 1. 构建过滤器（直接传递给 PostgreSQL）
            # ChromaDB 的 $eq, $in, $gte, $lte 语法需要转换为 SQLAlchemy 语法
            # ForumVectorDBService 的 search 方法会自动处理这些转换
            filters_dict = filters if filters else {}

            log.info(f"论坛搜索数据库过滤器: {filters_dict or '无'}")

            # 2. 根据是否有有效 query 决定执行语义搜索还是元数据浏览
            if query and query.strip():
                # --- 语义搜索逻辑 (需要 Gemini) ---
                if not self.is_ready():
                    log.info("RAG功能未启用：未配置API密钥，跳过语义搜索。")
                    return []
                log.info(f"执行语义搜索，查询: '{query}'")
                gemini_service = self._get_gemini_service()
                query_embedding = await gemini_service.generate_embedding(
                    text=query, task_type="retrieval_query"
                )
                if not query_embedding:
                    log.warning("无法为查询生成嵌入向量。")
                    return []

                search_results = await self.vector_db_service.search(
                    query_embedding=query_embedding,
                    n_results=n_results,
                    max_distance=config.FORUM_RAG_MAX_DISTANCE,
                    filters=filters_dict,
                )
                # 移除正文内容以减少 Token 消耗和日志干扰
                for result in search_results:
                    result.pop("content", None)
                return search_results
            else:
                # --- 元数据浏览逻辑 ---
                log.info("执行元数据浏览 (无查询关键词)。")
                if not filters_dict:
                    log.warning("无关键词浏览模式下必须提供有效的过滤器。")
                    return []

                # 直接从数据库获取所有匹配的文档
                log.info(
                    f"[FORUM_SEARCH] 准备调用 vector_db.get 进行元数据浏览。过滤器: {filters_dict}。"
                )
                import time

                start_time = time.monotonic()

                results = await self.vector_db_service.get(
                    filters=filters_dict,
                    limit=n_results,
                )

                duration = time.monotonic() - start_time
                ids = results.get("ids", [])
                metadatas = results.get("metadatas", [])
                log.info(
                    f"[FORUM_SEARCH] vector_db.get 调用完成，耗时: {duration:.4f} 秒，返回了 {len(ids)} 条原始记录。"
                )

                if not ids:
                    return []

                # 重构结果以便排序
                # 确保 metadatas 不为 None（虽然 .get() 已提供默认值）
                metadatas = metadatas or []
                reconstructed_results = [
                    {"id": id, "metadata": meta, "distance": 0.0}
                    for id, meta in zip(ids, metadatas)
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
