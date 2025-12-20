# -*- coding: utf-8 -*-
import logging
import logging.handlers
from typing import List, Dict
from sqlalchemy import select, text

# 导入父文档和子文档的模型
from src.database.database import AsyncSessionLocal
from src.database.models import KnowledgeChunk, TutorialDocument

import os

# --- RAG 追踪日志系统 ---
LOG_DIR = "logs"
LOG_FILE_PATH = os.path.join(LOG_DIR, "tutorial_rag_trace.log")
os.makedirs(LOG_DIR, exist_ok=True)

rag_trace_logger = logging.getLogger("rag_trace")
rag_trace_logger.setLevel(logging.INFO)
rag_trace_logger.propagate = False

handler = logging.handlers.RotatingFileHandler(
    LOG_FILE_PATH,
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
formatter = logging.Formatter("%(asctime)s - %(message)s")
handler.setFormatter(formatter)

if not rag_trace_logger.handlers:
    rag_trace_logger.addHandler(handler)

log = logging.getLogger(__name__)

# 从全局配置导入 RAG 设置
from src.chat.config.chat_config import TUTORIAL_RAG_CONFIG


class TutorialSearchService:
    def __init__(self):
        log.info("TutorialSearchService 已初始化")
        # 将配置加载到实例属性中，方便访问
        self.config = TUTORIAL_RAG_CONFIG
        log.info(f"教程 RAG 配置已加载: {self.config}")

    async def _hybrid_search_with_rrf(
        self, session, query_text: str, query_vector: List[float]
    ) -> List[int]:
        """使用原生 SQL 在数据库中执行高效的混合搜索和 RRF 融合，返回最佳 chunk ID 列表。"""
        sql_query = text(
            """
            WITH semantic_search AS (
                SELECT id, RANK() OVER (ORDER BY embedding <=> :query_vector) as rank
                FROM tutorials.knowledge_chunks
                ORDER BY embedding <=> :query_vector
                LIMIT :top_k_vector
            ),
            keyword_search AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY pdb.score(id) DESC) as rank
                FROM tutorials.knowledge_chunks
                WHERE chunk_text @@@ :query_text
                LIMIT :top_k_fts
            )
            SELECT
                COALESCE(s.id, k.id) as id
            FROM semantic_search s
            FULL OUTER JOIN keyword_search k ON s.id = k.id
            ORDER BY
                (COALESCE(1.0 / (:rrf_k + s.rank), 0.0) + COALESCE(1.0 / (:rrf_k + k.rank), 0.0)) DESC
            LIMIT :final_k;
            """
        )
        result = await session.execute(
            sql_query,
            {
                "query_text": query_text,
                "query_vector": str(query_vector),
                "top_k_vector": self.config["TOP_K_VECTOR"],
                "top_k_fts": self.config["TOP_K_FTS"],
                "rrf_k": self.config["RRF_K"],
                "final_k": self.config["HYBRID_SEARCH_FINAL_K"],
            },
        )
        return [row[0] for row in result.fetchall()]

    async def _get_parent_docs_by_chunk_ids(
        self, session, ids: List[int]
    ) -> List[Dict[str, str]]:
        """
        根据 chunk ID 列表，获取其所属的、唯一的父文档的完整内容。
        """
        if not ids:
            return []

        # 1. 根据 chunk IDs 查询到它们所属的、唯一的父文档 ID
        unique_doc_ids_stmt = (
            select(KnowledgeChunk.document_id)
            .where(KnowledgeChunk.id.in_(ids))
            .distinct()
        )
        doc_ids_result = await session.execute(unique_doc_ids_stmt)
        unique_doc_ids = [row[0] for row in doc_ids_result.fetchall()]

        if not unique_doc_ids:
            return []

        # 新增：限制最终返回的父文档数量
        max_parent_docs = self.config["MAX_PARENT_DOCS"]
        if len(unique_doc_ids) > max_parent_docs:
            log.info(
                f"检索到的唯一父文档数量 ({len(unique_doc_ids)}) 超过上限 {max_parent_docs}，将进行截断。"
            )
            unique_doc_ids = unique_doc_ids[:max_parent_docs]

        # 2. 根据唯一的父文档 ID 列表，查询并返回完整的父文档内容和标题
        parent_docs_stmt = select(
            TutorialDocument.title, TutorialDocument.original_content
        ).where(TutorialDocument.id.in_(unique_doc_ids))
        parent_docs_result = await session.execute(parent_docs_stmt)

        return [
            {"title": row.title, "content": row.original_content}
            for row in parent_docs_result.all()
        ]

    async def search(self, query: str, user_id: str = "N/A") -> str:
        """
        执行 RAG 流程：混合搜索找到最佳子文档，然后返回其完整的父文档内容。
        """
        trace_log = ["--- RAG TRACE START ---", f"UserID: {user_id}", f"Query: {query}"]
        log.info(f"收到来自用户 '{user_id}' 的教程知识库搜索请求: '{query}'")

        try:
            from src.chat.services.gemini_service import gemini_service

            query_embedding = await gemini_service.generate_embedding(
                text=query, task_type="retrieval_query"
            )
            if not query_embedding:
                raise ValueError("Embedding 生成失败，返回为空。")
        except Exception as e:
            log.error(f"为查询 '{query}' 生成 embedding 时出错: {e}", exc_info=True)
            return "抱歉，我现在无法理解您的问题，请稍后再试。"

        final_parent_docs: List[Dict[str, str]] = []
        try:
            async with AsyncSessionLocal() as session:
                # 1. 混合搜索，找到最相关的 chunk ID
                best_chunk_ids = await self._hybrid_search_with_rrf(
                    session, query, query_embedding
                )
                trace_log.append(
                    f"Found best chunk IDs from DB (Top {len(best_chunk_ids)}): {best_chunk_ids}"
                )

                if not best_chunk_ids:
                    log.info(f"数据库内混合搜索未找到 '{query}' 的相关文档。")
                    return "我在教程知识库里没有找到关于这个问题的具体信息。您可以换个方式问问吗？"

                # 2. 根据 chunk IDs 获取其所属的完整父文档内容
                final_parent_docs = await self._get_parent_docs_by_chunk_ids(
                    session, best_chunk_ids
                )
                retrieved_titles = [doc["title"] for doc in final_parent_docs]
                trace_log.append(
                    f"Retrieved {len(final_parent_docs)} parent document(s): {retrieved_titles}"
                )

        except Exception as e:
            log.error(f"在数据库中执行搜索或获取父文档时出错: {e}", exc_info=True)
            return "抱歉，访问教程知识库时遇到问题，请联系管理员。"

        if not final_parent_docs:
            log.warning(f"找到了 chunk ID，但未能获取任何父文档。查询: '{query}'")
            return (
                "我在教程知识库里没有找到关于这个问题的具体信息。您可以换个方式问问吗？"
            )

        # 3. 格式化最终的上下文，将每个父文档作为独立的参考资料提供
        context_parts = []
        for i, doc in enumerate(final_parent_docs):
            context_parts.append(
                f"--- 参考资料 {i + 1}: {doc['title']} ---\n{doc['content']}"
            )

        context = "\n\n".join(context_parts)

        trace_log.append(
            f"Final Context: Provided {len(final_parent_docs)} full parent documents."
        )
        trace_log.append("--- RAG TRACE END ---")
        rag_trace_logger.info("\n".join(trace_log))

        # 新增：在主日志中也记录命中的文档标题，方便快速诊断
        retrieved_titles_str = ", ".join([doc["title"] for doc in final_parent_docs])
        log.info(
            f"为查询 '{query}' 检索到 {len(final_parent_docs)} 份父文档作为上下文。标题: [{retrieved_titles_str}]"
        )
        return context


# 创建服务的单例
tutorial_search_service = TutorialSearchService()
