# -*- coding: utf-8 -*-
import logging
import re
from typing import Any, List, Dict

from sqlalchemy import text
from src.database.database import AsyncSessionLocal
from src.chat.services.ollama_embedding_service import (
    ollama_embedding_service,
    qwen_embedding_service,
)
from src.chat.config import chat_config
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)


async def get_embedding_column() -> str:
    """根据数据库配置返回当前使用的 embedding 列名"""
    try:
        model = await chat_db_manager.get_global_setting("embedding_model")
        return "qwen_embedding" if model == "qwen" else "bge_embedding"
    except Exception:
        return "bge_embedding"  # 默认使用 BGE


async def get_embedding_service():
    """根据数据库配置返回当前使用的 embedding 服务实例"""
    try:
        model = await chat_db_manager.get_global_setting("embedding_model")
        if model == "qwen":
            return qwen_embedding_service
        return ollama_embedding_service
    except Exception:
        return ollama_embedding_service  # 默认使用 BGE


class KnowledgeSearchService:
    """
    提供对社区成员和通用知识的混合搜索功能。
    使用 ParadeDB 的 BM25 和向量搜索能力。
    """

    def __init__(self):
        log.info("KnowledgeSearchService 已初始化")
        # 从配置中加载参数
        self.config = {
            "TOP_K_VECTOR": chat_config.WORLD_BOOK_RAG_CONFIG.get("TOP_K_VECTOR", 10),
            "TOP_K_FTS": chat_config.WORLD_BOOK_RAG_CONFIG.get("TOP_K_FTS", 10),
            "RRF_K": chat_config.WORLD_BOOK_RAG_CONFIG.get("RRF_K", 60),
            "HYBRID_SEARCH_FINAL_K": chat_config.WORLD_BOOK_RAG_CONFIG.get(
                "HYBRID_SEARCH_FINAL_K", 5
            ),
        }
        log.info(f"KnowledgeSearchService 配置: {self.config}")

    def _clean_fts_query(self, query: str) -> str:
        """
        清理全文搜索查询，移除可能导致 paradedb 解析错误的特殊字符。
        只保留字母、数字、中日韩统一表意文字和空格。
        """
        # 正则表达式匹配所有非（字母、数字、CJK字符、空格）的字符
        cleaned_query = re.sub(r"[^\w\s\u4e00-\u9fff]", "", query)
        log.debug(f"原始 FTS 查询: '{query}' -> 清理后: '{cleaned_query}'")
        return cleaned_query

    async def _hybrid_search_chunks(
        self, session, query_text: str, query_vector: List[float]
    ) -> List[Dict[str, Any]]:
        """
        在 community.member_chunks 和 general_knowledge.knowledge_chunks
        两个表中执行混合搜索，并返回融合排序后的 chunk 结果。
        """
        # 根据配置选择使用哪个 embedding 列
        embedding_col = await get_embedding_column()
        # 记录当前搜索配置
        embedding_model = "Qwen" if embedding_col == "qwen_embedding" else "BGE"
        log.info(
            f"[知识库搜索配置] Embedding模型: {embedding_model} | 搜索模式: 混合搜索 (向量 + BM25) | "
            f"向量列: {embedding_col} | TOP_K_VECTOR: {self.config['TOP_K_VECTOR']} | "
            f"TOP_K_FTS: {self.config['TOP_K_FTS']} | RRF_K: {self.config['RRF_K']} | FINAL_K: {self.config['HYBRID_SEARCH_FINAL_K']}"
        )
        # SQL 查询同时搜索两个 chunks 表
        sql_query = text(
            f"""
            WITH semantic_search AS (
                -- 社区成员向量搜索
                (SELECT
                    'community' as source_table,
                    profile_id as document_id,
                    chunk_text,
                    RANK() OVER (ORDER BY {embedding_col} <=> :query_vector) as rank
                FROM community.member_chunks
                ORDER BY {embedding_col} <=> :query_vector
                LIMIT :top_k_vector)
                UNION ALL
                -- 通用知识向量搜索
                (SELECT
                    'general_knowledge' as source_table,
                    document_id,
                    chunk_text,
                    RANK() OVER (ORDER BY {embedding_col} <=> :query_vector) as rank
                FROM general_knowledge.knowledge_chunks
                ORDER BY {embedding_col} <=> :query_vector
                LIMIT :top_k_vector)
            ),
            keyword_search AS (
                -- 社区成员 BM25 搜索 (使用 paradedb.score)
                (SELECT
                    'community' as source_table,
                    id as document_id, -- 统一ID字段名
                    chunk_text,
                    RANK() OVER (ORDER BY paradedb.score(id) DESC) as rank
                FROM community.member_chunks
                WHERE chunk_text @@@ :query_text
                LIMIT :top_k_fts)
                UNION ALL
                -- 通用知识 BM25 搜索 (使用 paradedb.score)
                (SELECT
                    'general_knowledge' as source_table,
                    id as document_id, -- 统一ID字段名
                    chunk_text,
                    RANK() OVER (ORDER BY paradedb.score(id) DESC) as rank
                FROM general_knowledge.knowledge_chunks
                WHERE chunk_text @@@ :query_text
                LIMIT :top_k_fts)
            ),
            -- 使用 RRF (Reciprocal Rank Fusion) 融合排名
            fused_ranks AS (
                SELECT
                    COALESCE(s.document_id, k.document_id) as document_id,
                    COALESCE(s.source_table, k.source_table) as source_table,
                    COALESCE(s.chunk_text, k.chunk_text) as chunk_text,
                    (COALESCE(1.0 / (:rrf_k + s.rank), 0.0) + COALESCE(1.0 / (:rrf_k + k.rank), 0.0)) as rrf_score
                FROM semantic_search s
                FULL OUTER JOIN keyword_search k ON s.document_id = k.document_id AND s.chunk_text = k.chunk_text
            )
            SELECT *
            FROM fused_ranks
            ORDER BY rrf_score DESC
            LIMIT :final_k;
            """
        )
        log.info(
            f"执行混合搜索: query_text='{query_text[:100]}...', final_k={self.config['HYBRID_SEARCH_FINAL_K']}"
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
        # SQLAlchemy 2.x 的 Row 对象需要通过 ._mapping 转换为字典
        rows = result.fetchall()
        log.info(f"混合搜索返回 {len(rows)} 个结果")
        return [dict(row._mapping) for row in rows]

    async def search(self, query: str) -> List[Dict[str, Any]]:
        """
        执行完整的 RAG 混合搜索流程。
        1. 生成查询嵌入。
        2. 在 chunks 表中进行混合搜索。
        3. (暂定)直接返回 chunks 内容，因为我们的场景下，chunk 可能就是全部。
        """
        log.info(f"收到知识库混合搜索请求: '{query}'")

        try:
            # 根据配置选择对应的 embedding 服务
            embedding_service = await get_embedding_service()
            query_embedding = await embedding_service.generate_embedding(
                text=query, task_type="retrieval_query"
            )
            if not query_embedding:
                raise ValueError("Embedding 生成失败，返回为空。")
        except Exception as e:
            log.error(f"为查询 '{query}' 生成 embedding 时出错: {e}", exc_info=True)
            return []

        search_results = []
        try:
            # 清理用于全文搜索的查询文本
            cleaned_fts_query = self._clean_fts_query(query)

            async with AsyncSessionLocal() as session:
                search_results = await self._hybrid_search_chunks(
                    session, cleaned_fts_query, query_embedding
                )
                log.info(f"混合搜索 RRF 结果: {search_results}")

        except Exception as e:
            log.error(f"在数据库中执行混合搜索时出错: {e}", exc_info=True)
            return []

        if not search_results:
            log.info(f"知识库混合搜索未找到 '{query}' 的相关文档。")
            return []

        # 转换为 world_book_service 期望的格式
        # 'content' 字段直接使用 chunk_text
        formatted_results = []
        for res in search_results:
            rrf_score = float(res["rrf_score"])  # 确保为浮点数
            formatted_results.append(
                {
                    "id": res.get("document_id"),
                    "content": res.get("chunk_text"),
                    "distance": 1.0 - rrf_score,  # 将rrf_score转换为类似距离的度量
                    "metadata": {"source_table": res.get("source_table")},
                }
            )

        return formatted_results


# 创建服务的单例
knowledge_search_service = KnowledgeSearchService()
