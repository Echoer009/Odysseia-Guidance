# -*- coding: utf-8 -*-
import logging
import logging.handlers
from typing import Any, List, Dict
from sqlalchemy import select, text

# 导入父文档和子文档的模型
from src.database.database import AsyncSessionLocal
from src.database.models import KnowledgeChunk, TutorialDocument

import os

# 导入新的帖子设置服务
from src.chat.features.tutorial_search.services.thread_settings_service import (
    thread_settings_service,
)

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
        self,
        session,
        query_text: str,
        query_vector: List[float],
        thread_id: int | None,
        search_mode: str = "ISOLATED",
    ) -> List:
        """使用原生 SQL 在数据库中执行高效的混合搜索和 RRF 融合，返回最佳 chunk 及其分数。"""
        # We need to join with tutorial_documents to get the thread_id
        sql_query = text(
            """
            WITH semantic_search AS (
                SELECT
                    kc.id,
                    RANK() OVER (ORDER BY kc.embedding <=> :query_vector) as rank,
                    td.thread_id
                FROM tutorials.knowledge_chunks kc
                JOIN tutorials.tutorial_documents td ON kc.document_id = td.id
                ORDER BY kc.embedding <=> :query_vector
                LIMIT :top_k_vector
            ),
            keyword_search AS (
                SELECT
                    kc.id,
                    ROW_NUMBER() OVER (ORDER BY pdb.score(kc.id) DESC) as rank,
                    td.thread_id
                FROM tutorials.knowledge_chunks kc
                JOIN tutorials.tutorial_documents td ON kc.document_id = td.id
                WHERE kc.chunk_text @@@ :query_text
                LIMIT :top_k_fts
            )
            SELECT
                COALESCE(s.id, k.id) as id,
                (CASE WHEN COALESCE(s.thread_id, k.thread_id) = :thread_id THEN 1 ELSE 0 END) as is_thread_match,
                (COALESCE(1.0 / (:rrf_k + s.rank), 0.0) + COALESCE(1.0 / (:rrf_k + k.rank), 0.0)) as rrf_score
            FROM semantic_search s
            FULL OUTER JOIN keyword_search k ON s.id = k.id
            """
        )

        # 根据搜索模式添加过滤条件
        if search_mode == "ISOLATED":
            # 隔离模式：只搜索当前帖子（thread_id匹配）和基础库（thread_id为NULL）
            sql_query = text(
                sql_query.text
                + """
                WHERE COALESCE(s.thread_id, k.thread_id) = :thread_id
                   OR COALESCE(s.thread_id, k.thread_id) IS NULL
                ORDER BY
                    is_thread_match DESC,
                    rrf_score DESC
                LIMIT :final_k;
                """
            )
        else:
            # 优先模式：搜索所有教程，但当前帖子优先
            sql_query = text(
                sql_query.text
                + """
                ORDER BY
                    is_thread_match DESC,
                    rrf_score DESC
                LIMIT :final_k;
                """
            )
        result = await session.execute(
            sql_query,
            {
                "query_text": query_text,
                "query_vector": str(query_vector),
                "thread_id": str(thread_id) if thread_id is not None else None,
                "top_k_vector": self.config["TOP_K_VECTOR"],
                "top_k_fts": self.config["TOP_K_FTS"],
                "rrf_k": self.config["RRF_K"],
                "final_k": self.config["HYBRID_SEARCH_FINAL_K"],
            },
        )
        return result.fetchall()

    async def _get_parent_docs_by_chunk_ids(
        self, session, ids: List[int]
    ) -> List[Dict[str, str]]:
        """
        根据 chunk ID 列表，获取其所属的、唯一的父文档的完整内容。
        这个实现确保了在去重和截断时，保持原始传入 `ids` 列表的顺序。
        """
        if not ids:
            return []

        log.info(f"父文档获取：收到排序后的 chunk IDs: {ids}")

        # 1. 根据 chunk IDs 查询它们所属的父文档 ID。
        # 这里不直接在SQL中使用DISTINCT，因为那可能会丢失我们想要的顺序。
        doc_ids_stmt = select(KnowledgeChunk.document_id).where(
            KnowledgeChunk.id.in_(ids)
        )

        # 2. 使用CASE语句在SQL层面强制排序，确保返回的doc_id顺序与chunk_id的优先级一致
        order_case = text(
            "CASE "
            + " ".join(
                [
                    f"WHEN tutorials.knowledge_chunks.id = {id_} THEN {i}"
                    for i, id_ in enumerate(ids)
                ]
            )
            + " END"
        )
        doc_ids_stmt = doc_ids_stmt.order_by(order_case)

        doc_ids_result = await session.execute(doc_ids_stmt)
        # 获取所有相关的 doc_id，保持数据库返回的顺序
        ordered_doc_ids = [row[0] for row in doc_ids_result.fetchall()]
        log.info(
            f"父文档获取：从数据库按 chunk 优先级获取的 doc IDs: {ordered_doc_ids}"
        )

        # 3. 在 Python 中进行有序去重
        unique_doc_ids = list(dict.fromkeys(ordered_doc_ids))
        log.info(f"父文档获取：有序去重后的唯一 doc IDs: {unique_doc_ids}")

        if not unique_doc_ids:
            return []

        # 4. 截断，只保留最高优先级的父文档
        max_parent_docs = self.config["MAX_PARENT_DOCS"]
        if len(unique_doc_ids) > max_parent_docs:
            truncated_ids = unique_doc_ids[:max_parent_docs]
            log.info(
                f"检索到的唯一父文档数量 ({len(unique_doc_ids)}) 超过上限 {max_parent_docs}，"
                f"将截断为: {truncated_ids}"
            )
            unique_doc_ids = truncated_ids

        # 5. 根据最终确定的、唯一的、排序后的、截断后的父文档 ID 列表，查询并返回完整的父文档内容和标题
        parent_docs_stmt = select(
            TutorialDocument.title, TutorialDocument.original_content
        ).where(TutorialDocument.id.in_(unique_doc_ids))

        # 同样，在这里也强制排序，以确保最终输出的上下文顺序与优先级一致
        final_order_case = text(
            "CASE "
            + " ".join(
                [
                    f"WHEN tutorials.tutorial_documents.id = {id_} THEN {i}"
                    for i, id_ in enumerate(unique_doc_ids)
                ]
            )
            + " END"
        )
        parent_docs_stmt = parent_docs_stmt.order_by(final_order_case)

        parent_docs_result = await session.execute(parent_docs_stmt)

        return [
            {"title": row.title, "content": row.original_content}
            for row in parent_docs_result.all()
        ]

    async def search(
        self, query: str, user_id: str = "N/A", thread_id: int | None = None
    ) -> List[Dict[str, Any]]:
        """
        执行 RAG 流程：混合搜索找到最佳子文档，然后返回其完整的父文档内容列表。
        每个文档是一个包含 title, content, thread_id 的字典。
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
            return []

        final_parent_docs: List[Dict[str, str]] = []
        try:
            # 获取当前帖子的搜索模式
            current_search_mode = await thread_settings_service.get_search_mode(
                str(thread_id)
            )
            log.info(f"帖子 {thread_id} 的搜索模式: {current_search_mode}")

            async with AsyncSessionLocal() as session:
                # 1. 混合搜索，找到最相关的 chunk ID
                search_results = await self._hybrid_search_with_rrf(
                    session, query, query_embedding, thread_id, current_search_mode
                )
                log.info(
                    f"混合搜索 RRF 结果 (id, is_thread_match, rrf_score): {search_results}"
                )
                best_chunk_ids = [res.id for res in search_results]

                trace_log.append(
                    f"Found best chunk IDs from DB (Top {len(best_chunk_ids)}): {best_chunk_ids}"
                )

                if not best_chunk_ids:
                    log.info(f"数据库内混合搜索未找到 '{query}' 的相关文档。")
                    return []

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
            return []

        if not final_parent_docs:
            log.warning(f"找到了 chunk ID，但未能获取任何父文档。查询: '{query}'")
            return []

        # 3. 直接返回包含完整信息的文档列表
        trace_log.append(
            f"Returning {len(final_parent_docs)} full parent documents to be formatted by PromptService."
        )
        trace_log.append("--- RAG TRACE END ---")
        rag_trace_logger.info("\n".join(trace_log))

        # 新增：在主日志中也记录命中的文档标题，方便快速诊断
        retrieved_titles_str = ", ".join([doc["title"] for doc in final_parent_docs])
        log.info(
            f"为查询 '{query}' 检索到 {len(final_parent_docs)} 份父文档。标题: [{retrieved_titles_str}]"
        )
        return final_parent_docs


# 创建服务的单例
tutorial_search_service = TutorialSearchService()
