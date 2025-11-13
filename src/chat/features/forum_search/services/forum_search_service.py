# -*- coding: utf-8 -*-

import logging
from typing import List, Dict, Any
import discord

from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)
from src.chat.features.world_book.services.incremental_rag_service import (
    create_text_chunks,
)

log = logging.getLogger(__name__)


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
            author_name = thread.owner.name if thread.owner else "未知作者"
            # 将标签处理为字符串列表
            tags_list = [tag.name for tag in thread.applied_tags]
            # 为了文档可读性，创建一个逗号分隔的字符串版本
            tags_str_for_doc = ", ".join(tags_list) if tags_list else "无标签"
            # 为了元数据过滤，创建一个管道分隔的字符串，如果无标签则为None
            tags_for_meta = f"|{'|'.join(tags_list)}|" if tags_list else None

            # 提取论坛频道的名称作为分类
            category_name = thread.parent.name if thread.parent else "未知分类"
            document_text = f"标题: {title}\n作者: {author_name}\n分类: {category_name}\n标签: {tags_str_for_doc}\n内容: {content}"

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
                            "author_id": thread.owner.id
                            if thread.owner
                            else 0,  # 新增：作者ID
                            "category_name": category_name,
                            "tags": tags_for_meta,  # 使用特殊格式的字符串以便于过滤
                            "channel_id": thread.parent_id,
                            "guild_id": thread.guild.id,
                            "created_at": thread.created_at.isoformat(),
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
        self, query: str, n_results: int = 5, filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        执行高级语义搜索，支持多种元数据过滤。

        Args:
            query (str): 搜索查询。
            n_results (int): 返回结果的数量。
            filters (Dict[str, Any], optional): 一个包含元数据过滤条件的字典。
                - key 是元数据字段名 (例如 "category_name", "author_id", "tags")。
                - value 可以是直接匹配的值，或是一个用于范围/包含查询的字典。
                - 对于 "tags", value 应为列表，查询将检查是否包含任一标签。
                示例:
                {
                    "category_name": "男性向",
                    "author_id": 1234567890,
                    "tags": ["角色卡", "原创"]
                }
        Returns:
            List[Dict[str, Any]]: 搜索结果列表。
        """
        if not self.is_ready():
            log.error("论坛搜索服务尚未准备就绪，无法执行搜索。")
            return []

        try:
            # 1. 构建数据库查询的元数据过滤条件 (where 子句)
            where_clause = {}
            tags_to_filter = None
            if filters:
                # 提取标签用于后续在代码中过滤，因为DB不支持我们需要的复杂查询
                if "tags" in filters:
                    tags_to_filter = filters.pop("tags")

                for key, value in filters.items():
                    if value is not None:
                        # 对于其他字段，我们进行直接相等匹配
                        where_clause[key] = value

            log.info(f"论坛搜索数据库过滤器 (where): {where_clause}")
            if tags_to_filter:
                log.info(f"论坛搜索应用层过滤器 (tags): {tags_to_filter}")

            # 2. 从向量数据库获取初步结果
            gemini_service = self._get_gemini_service()
            query_embedding = await gemini_service.generate_embedding(
                text=query, task_type="retrieval_query"
            )
            if not query_embedding:
                log.warning("无法为查询生成嵌入向量。")
                return []

            # 为了进行二次过滤，我们需要请求更多的结果
            n_results_for_db = n_results * 5 if tags_to_filter else n_results

            search_results_list = self.vector_db_service.search(
                query_embedding=query_embedding,
                n_results=n_results_for_db,
                max_distance=1.0,
            )

            # 3. 在应用层进行元数据和标签的二次过滤
            final_results_list = []
            if search_results_list:
                # 3.1. 首先处理 where_clause 过滤
                if where_clause:
                    intermediate_results = []
                    for item in search_results_list:
                        metadata = item.get("metadata", {})
                        if all(
                            metadata.get(key) == value
                            for key, value in where_clause.items()
                        ):
                            intermediate_results.append(item)
                    search_results_list = intermediate_results

                # 3.2. 接着处理标签过滤
                if tags_to_filter:
                    required_tags = set(t.lower() for t in tags_to_filter)
                    for item in search_results_list:
                        if len(final_results_list) >= n_results:
                            break  # 已找到足够的结果
                        metadata = item.get("metadata", {})
                        if (
                            metadata
                            and metadata.get("tags")
                            and isinstance(metadata["tags"], str)
                        ):
                            available_tags = set(
                                t.lower()
                                for t in metadata["tags"].strip("|").split("|")
                            )
                            if required_tags.issubset(available_tags):
                                final_results_list.append(item)
                else:
                    # 如果没有标签过滤，直接取所需数量的结果
                    final_results_list = search_results_list[:n_results]

            # 4. 将过滤和截断后的结果列表转换为 ChromaDB 风格的字典
            if not final_results_list:
                return {}

            search_results = {
                "ids": [[res["id"] for res in final_results_list]],
                "documents": [[res["content"] for res in final_results_list]],
                "metadatas": [[res["metadata"] for res in final_results_list]],
                "distances": [[res["distance"] for res in final_results_list]],
            }

            return search_results

        except Exception as e:
            log.error(f"执行论坛搜索时发生错误: {e}", exc_info=True)
            return []


# 全局实例
forum_search_service = ForumSearchService()
