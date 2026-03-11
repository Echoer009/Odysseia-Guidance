# -*- coding: utf-8 -*-

import asyncio
import logging
from typing import List, Dict, Any, Tuple, Optional
import discord
from datetime import datetime
from zoneinfo import ZoneInfo

from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)
from src.chat.services.regex_service import regex_service
from src.chat.config import chat_config as config

log = logging.getLogger(__name__)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class ForumSearchService:
    """
    核心服务，负责处理论坛帖子的索引和搜索。
    使用 ParadeDB (PostgreSQL + pgvector) 进行向量搜索和 BM25 全文搜索。
    """

    def __init__(self):
        self.ollama_embedding_service = None
        self.qwen_embedding_service = None
        self.vector_db_service = forum_vector_db_service

    def _get_ollama_embedding_service(self):
        """延迟导入 Ollama embedding 服务（BGE-M3）以避免循环导入。"""
        if self.ollama_embedding_service is None:
            from src.chat.services.ollama_embedding_service import (
                ollama_embedding_service,
            )

            self.ollama_embedding_service = ollama_embedding_service
        return self.ollama_embedding_service

    def _get_qwen_embedding_service(self):
        """延迟导入 Qwen embedding 服务以避免循环导入。"""
        if self.qwen_embedding_service is None:
            from src.chat.services.ollama_embedding_service import (
                qwen_embedding_service,
            )

            self.qwen_embedding_service = qwen_embedding_service
        return self.qwen_embedding_service

    async def _generate_dual_embeddings(
        self, document_text: str, title: str
    ) -> Tuple[Optional[List[float]], Optional[List[float]]]:
        """
        并行生成 BGE 和 Qwen 两种 embedding。
        会检查禁用状态，跳过被禁用的模型。

        Args:
            document_text: 文档文本
            title: 标题

        Returns:
            Tuple[bge_embedding, qwen_embedding]: 两种 embedding，如果生成失败或被禁用则为 None
        """
        from src.chat.utils.database import chat_db_manager

        # 获取禁用的模型列表
        try:
            disabled_str = await chat_db_manager.get_global_setting(
                "disabled_embedding_models"
            )
            disabled_models = (
                [m.strip() for m in disabled_str.split(",") if m.strip()]
                if disabled_str
                else []
            )
        except Exception:
            disabled_models = []

        bge_service = self._get_ollama_embedding_service()
        qwen_service = self._get_qwen_embedding_service()

        # 根据禁用状态决定是否生成 embedding
        tasks = []
        task_names = []

        if "bge" not in disabled_models:
            tasks.append(
                bge_service.generate_embedding(
                    text=document_text, title=title, task_type="retrieval_document"
                )
            )
            task_names.append("bge")
        else:
            log.debug("[FORUM_SEARCH] BGE 模型已禁用，跳过生成 embedding")

        if "qwen" not in disabled_models:
            tasks.append(
                qwen_service.generate_embedding(
                    text=document_text, title=title, task_type="retrieval_document"
                )
            )
            task_names.append("qwen")
        else:
            log.debug("[FORUM_SEARCH] Qwen 模型已禁用，跳过生成 embedding")

        # 并行生成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        bge_embedding: Optional[List[float]] = None
        qwen_embedding: Optional[List[float]] = None

        for i, name in enumerate(task_names):
            if isinstance(results[i], Exception):
                log.error(f"生成 {name} embedding 失败: {results[i]}")
            elif isinstance(results[i], list):
                if name == "bge":
                    bge_embedding = list(results[i])  # type: ignore
                elif name == "qwen":
                    qwen_embedding = list(results[i])  # type: ignore

        return bge_embedding, qwen_embedding

    def is_ready(self) -> bool:
        """检查服务是否已准备好。"""
        ollama_embedding_service = self._get_ollama_embedding_service()
        return (
            ollama_embedding_service.check_connection_sync()
            and self.vector_db_service.is_available()
        )

    async def process_thread(self, thread: discord.Thread):
        """
        处理单个论坛帖子，将其整帖内容向量化并存入 ParadeDB。
        注意：ParadeDB 使用单表结构，不进行文本分块。
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

            # 3. 获取作者信息 (更稳健的方式)
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

            # 4. 提取论坛频道的名称作为分类
            raw_category_name = thread.parent.name if thread.parent else "未知分类"
            category_name = regex_service.clean_channel_name(raw_category_name)

            # 5. 构建用于向量化的文本（标题 + 内容）
            # ParadeDB 使用整帖向量化，不进行分块
            document_text = f"{title}\n\n{content}"

            # 6. 并行生成两种 embedding（双写策略）
            bge_embedding, qwen_embedding = await self._generate_dual_embeddings(
                document_text, title
            )
            if not bge_embedding and not qwen_embedding:
                log.warning(f"无法为帖子 {thread.id} 生成任何嵌入向量。")
                return

            # 7. 构建源元数据
            source_metadata = {
                "thread_id": thread.id,
                "thread_name": title,
                "author_id": author_id or 0,
                "author_name": author_name,
                "category_name": category_name,
                "channel_id": thread.parent_id,
                "guild_id": thread.guild.id,
            }

            # 8. 写入 ParadeDB（双写两种 embedding）
            # Discord 的 created_at 是带时区的，需要转换为不带时区的 datetime
            created_at = (
                thread.created_at if thread.created_at else datetime.now(BEIJING_TZ)
            )
            if created_at.tzinfo is not None:
                created_at = created_at.replace(tzinfo=None)

            success = await self.vector_db_service.add_document(
                thread_id=thread.id,
                thread_name=title,
                content=content,
                author_id=author_id or 0,
                author_name=author_name,
                category_name=category_name,
                channel_id=thread.parent_id,
                guild_id=thread.guild.id,
                created_at=created_at,
                bge_embedding=bge_embedding,
                qwen_embedding=qwen_embedding,
                source_metadata=source_metadata,
            )

            if success:
                log.info(f"成功将帖子 {thread.id} 添加到 ParadeDB（双写 BGE + Qwen）。")
            else:
                log.warning(f"添加帖子 {thread.id} 到 ParadeDB 失败。")

        except Exception as e:
            log.error(f"处理帖子 {thread.id} 时发生错误: {e}", exc_info=True)

    async def add_documents_batch(
        self, ids: List[str], documents: List[str], metadatas: List[Dict[str, Any]]
    ):
        """
        从备份数据批量添加文档，包含向量化。
        这是为 --restore-from 功能设计的核心方法。
        注意：ParadeDB 使用单表结构，不进行文本分块。
        """
        if not self.is_ready():
            log.warning("论坛搜索服务尚未准备就绪，无法添加文档。")
            return

        for doc_id, document, metadata in zip(ids, documents, metadatas):
            try:
                # 1. 提取元数据
                title = metadata.get("thread_name", "")
                author_id = metadata.get("author_id", 0)
                author_name = metadata.get("author_name", "未知作者")
                category_name = metadata.get("category_name", "未知分类")
                channel_id = metadata.get("channel_id", 0)
                guild_id = metadata.get("guild_id", 0)

                # 2. 解析创建时间
                created_at_str = metadata.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(created_at_str)
                    except Exception:
                        created_at = datetime.now(BEIJING_TZ)
                else:
                    created_at = datetime.now(BEIJING_TZ)

                # 3. 构建用于向量化的文本（标题 + 内容）
                document_text = f"{title}\n\n{document}"

                # 4. 并行生成两种 embedding（双写策略）
                bge_embedding, qwen_embedding = await self._generate_dual_embeddings(
                    document_text, title
                )
                if not bge_embedding and not qwen_embedding:
                    log.warning(f"无法为文档 {doc_id} 生成任何嵌入向量。")
                    continue

                # 5. 写入 ParadeDB（双写两种 embedding）
                success = await self.vector_db_service.add_document(
                    thread_id=int(doc_id),
                    thread_name=title,
                    content=document,
                    author_id=author_id,
                    author_name=author_name,
                    category_name=category_name,
                    channel_id=channel_id,
                    guild_id=guild_id,
                    created_at=created_at,
                    bge_embedding=bge_embedding,
                    qwen_embedding=qwen_embedding,
                    source_metadata=metadata,
                )

                if success:
                    log.info(f"成功添加文档 {doc_id} 到 ParadeDB（双写 BGE + Qwen）。")
                else:
                    log.warning(f"添加文档 {doc_id} 到 ParadeDB 失败。")

            except Exception as e:
                log.error(
                    f"为文档 {doc_id} 添加到 ParadeDB 时发生错误: {e}", exc_info=True
                )

    async def get_oldest_indexed_thread_timestamp(self, channel_id: int) -> str | None:
        """
        获取指定频道中已索引的最旧帖子的创建时间戳。

        Args:
            channel_id (int): 目标论坛频道的ID。

        Returns:
            str | None: 最旧帖子的ISO 8601格式时间戳字符串，如果该频道没有任何帖子被索引，则返回None。
        """
        return await self.vector_db_service.get_oldest_indexed_thread_timestamp(
            channel_id
        )

    async def search(
        self,
        query: str | None = None,
        n_results: int = 5,
        filters: Dict[str, Any] | None = None,
        use_hybrid: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        执行高级搜索或按元数据浏览。
        - 如果 `use_hybrid=True` 且提供了有效的 `query`，则执行混合搜索（向量 + BM25）。
        - 如果 `use_hybrid=False` 且提供了有效的 `query`，则执行 BM25 全文搜索。
        - 如果 `query` 为 None 或空字符串，则按 `filters` 浏览，并按时间倒序返回最新结果。

        Args:
            query (str, optional): 搜索查询。
            n_results (int): 返回结果的数量（仅用于 BM25 搜索和浏览模式，混合搜索使用配置中的 HYBRID_SEARCH_FINAL_K）。
            filters (Dict[str, Any], optional): 一个包含元数据过滤条件的字典。
                - `category_name` (str): 按指定的论坛频道名称进行过滤。
                - `author_id` (int): 按作者的Discord ID进行过滤。
                - `author_name` (str): 按作者的显示名称进行过滤。
                - `start_date` (str): 筛选发布日期在此日期之后的帖子 (格式: YYYY-MM-DD)。
                - `end_date` (str): 筛选发布日期在此日期之前的帖子 (格式: YYYY-MM-DD)。
            use_hybrid (bool): 是否使用混合搜索（向量 + BM25）。
        Returns:
            List[Dict[str, Any]]: 一个包含搜索结果字典的列表。
        """
        try:
            # 1. 构建过滤条件
            where_filter = {}
            if filters:
                for key, value in filters.items():
                    if value is None:
                        continue

                    if key in [
                        "start_date",
                        "end_date",
                        "category_name",
                        "author_id",
                        "author_name",
                        "channel_id",
                    ]:
                        where_filter[key] = value

            log.info(f"论坛搜索数据库过滤器: {where_filter or '无'}")

            # 2. 根据是否有有效 query 决定执行混合搜索、BM25 搜索还是元数据浏览
            if query and query.strip():
                if use_hybrid:
                    # --- 混合搜索逻辑（向量 + BM25）---
                    if not self.is_ready():
                        log.info("RAG功能未启用：未配置API密钥，跳过混合搜索。")
                        return []
                    log.info(f"[FORUM_SEARCH] 执行混合搜索，查询: '{query}'")
                    # 根据配置选择对应的 embedding 服务
                    from src.chat.utils.database import chat_db_manager

                    try:
                        model = await chat_db_manager.get_global_setting(
                            "embedding_model"
                        )
                        if model == "qwen":
                            embedding_service = self._get_qwen_embedding_service()
                        else:
                            embedding_service = self._get_ollama_embedding_service()
                    except Exception:
                        embedding_service = self._get_ollama_embedding_service()

                    query_embedding = await embedding_service.generate_embedding(
                        text=query, task_type="retrieval_query"
                    )
                    if not query_embedding:
                        log.warning("[FORUM_SEARCH] 无法为查询生成嵌入向量。")
                        return []

                    search_results = await self.vector_db_service.search_hybrid(
                        query_embedding=query_embedding,
                        query_text=query,
                        where_filter=where_filter,
                        max_distance=config.FORUM_RAG_MAX_DISTANCE,
                    )

                    # 详细日志：打印混合搜索返回的结果
                    log.info(
                        f"[FORUM_SEARCH] 混合搜索返回 {len(search_results)} 条结果"
                    )
                    for i, result in enumerate(search_results):
                        metadata = result.get("metadata", {})
                        exact_match = result.get("exact_match", False)
                        rrf_score = result.get(
                            "rrf_score", result.get("distance", "N/A")
                        )
                        final_score = result.get("distance", "N/A")
                        log.info(
                            f"[FORUM_SEARCH] 结果 {i + 1}: "
                            f"thread_id={metadata.get('thread_id')}, "
                            f"thread_name='{metadata.get('thread_name')}', "
                            f"category='{metadata.get('category_name')}', "
                            f"author='{metadata.get('author_name')}', "
                            f"rrf_score={rrf_score}, "
                            f"final_score={final_score}, "
                            f"exact_match={'✓' if exact_match else '✗'}"
                        )
                    return search_results
                else:
                    # --- BM25 全文搜索逻辑 ---
                    log.info(f"[FORUM_SEARCH] 执行 BM25 全文搜索，查询: '{query}'")
                    search_results = await self.vector_db_service.search_bm25(
                        query=query,
                        n_results=n_results,
                        where_filter=where_filter,
                    )

                    # 详细日志：打印 BM25 搜索返回的结果
                    log.info(
                        f"[FORUM_SEARCH] BM25 搜索返回 {len(search_results)} 条结果"
                    )
                    for i, result in enumerate(search_results):
                        metadata = result.get("metadata", {})
                        log.info(
                            f"[FORUM_SEARCH] 结果 {i + 1}: "
                            f"thread_id={metadata.get('thread_id')}, "
                            f"thread_name='{metadata.get('thread_name')}', "
                            f"category='{metadata.get('category_name')}', "
                            f"author='{metadata.get('author_name')}', "
                            f"score={result.get('distance', 'N/A')}"
                        )
                    return search_results
            else:
                # --- 元数据浏览逻辑 ---
                log.info("执行元数据浏览 (无查询关键词)。")
                if not where_filter:
                    log.warning("无关键词浏览模式下必须提供有效的过滤器。")
                    return []

                # 直接从数据库获取所有匹配的文档
                import time

                start_time = time.monotonic()

                results = await self.vector_db_service.get(
                    where=where_filter if where_filter else None,
                    include=["metadatas"],
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
