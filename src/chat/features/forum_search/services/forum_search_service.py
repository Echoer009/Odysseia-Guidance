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
            tags = (
                ", ".join([tag.name for tag in thread.applied_tags])
                if thread.applied_tags
                else "无标签"
            )
            # 提取论坛频道的名称作为分类
            category_name = thread.parent.name if thread.parent else "未知分类"
            document_text = f"标题: {title}\n作者: {author_name}\n分类: {category_name}\n标签: {tags}\n内容: {content}"

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
                            "category_name": category_name,
                            "tags": tags,
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

    async def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        执行语义搜索。
        """
        if not self.is_ready():
            log.error("论坛搜索服务尚未准备就绪，无法执行搜索。")
            return []

        try:
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
                max_distance=1.0,  # 论坛搜索可以放宽距离限制
            )
            return search_results

        except Exception as e:
            log.error(f"执行论坛搜索时发生错误: {e}", exc_info=True)
            return []


# 全局实例
forum_search_service = ForumSearchService()
