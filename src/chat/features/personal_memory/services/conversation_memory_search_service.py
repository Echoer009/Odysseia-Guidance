# -*- coding: utf-8 -*-
"""
对话记忆搜索服务 - 检索相关历史对话

核心功能：
- 基于用户输入检索相关的历史对话块
- 使用混合搜索（向量 + BM25）
- 生成带时间标记的对话上下文
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import text

from src.database.database import AsyncSessionLocal
from src.chat.services.embedding_factory import (
    get_embedding_service,
    get_embedding_column,
    is_vector_enabled,
)
from src.chat.config import chat_config
from src.chat.features.personal_memory.services.conversation_block_service import (
    format_time_description,
)

log = logging.getLogger(__name__)


class ConversationMemorySearchService:
    """
    对话记忆搜索服务

    负责：
    - 检索与当前对话相关的历史对话块
    - 使用混合搜索（向量 + BM25）提高召回率
    - 生成带时间标记的对话上下文
    """

    def __init__(self):
        self.config = chat_config.CONVERSATION_MEMORY_CONFIG
        log.info(f"ConversationMemorySearchService 已初始化，配置: {self.config}")

    def _clean_fts_query(self, query: str) -> str:
        """
        清理全文搜索查询，移除可能导致 paradedb 解析错误的特殊字符。
        只保留字母、数字、中日韩统一表意文字和空格。
        """
        cleaned_query = re.sub(r"[^\w\s\u4e00-\u9fff]", "", query)
        log.debug(f"原始 FTS 查询: '{query}' -> 清理后: '{cleaned_query}'")
        return cleaned_query

    async def _hybrid_search_blocks(
        self,
        session,
        discord_id: str,
        query_text: str,
        query_vector: List[float],
        exclude_block_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行混合搜索（向量 + BM25）检索用户的对话块。
        使用 RRF (Reciprocal Rank Fusion) 融合向量搜索和 BM25 搜索结果。

        Args:
            session: 数据库会话
            discord_id: 用户 Discord ID
            query_text: 查询文本
            query_vector: 查询向量
            exclude_block_ids: 要排除的对话块 ID 列表

        Returns:
            检索结果列表
        """
        embedding_col = await get_embedding_column()
        embedding_model = "Qwen" if embedding_col == "qwen_embedding" else "BGE"

        # 混合搜索配置
        top_k_vector = self.config.get("top_k_vector", 10)
        top_k_fts = self.config.get("top_k_fts", 10)
        rrf_k = self.config.get("rrf_k", 60)
        final_k = self.config.get("retrieval_top_k", 3)
        max_vector_distance = self.config.get("max_vector_distance", 0.65)

        log.info(
            f"[对话记忆搜索] 用户: {discord_id} | Embedding模型: {embedding_model} | "
            f"搜索模式: 混合搜索 (向量 + BM25) | 向量列: {embedding_col} | "
            f"TOP_K_VECTOR: {top_k_vector} | TOP_K_FTS: {top_k_fts} | "
            f"RRF_K: {rrf_k} | FINAL_K: {final_k} | MAX_DISTANCE: {max_vector_distance} | "
            f"排除块: {exclude_block_ids}"
        )

        # 构建排除条件
        exclude_clause = ""
        if exclude_block_ids:
            exclude_clause = f"AND id NOT IN ({','.join(map(str, exclude_block_ids))})"

        # 混合搜索 SQL
        # 使用 RRF (Reciprocal Rank Fusion) 融合向量搜索和 BM25 搜索结果
        # 参考论坛搜索的实现方式
        sql_query = text(
            f"""
            WITH semantic_search AS (
                SELECT
                    id,
                    {embedding_col} <=> CAST(:query_vector AS halfvec) as vector_distance,
                    RANK() OVER (ORDER BY {embedding_col} <=> CAST(:query_vector AS halfvec)) as rank
                FROM conversation.conversation_blocks
                WHERE discord_id = :discord_id
                  AND {embedding_col} IS NOT NULL
                  {exclude_clause}
                ORDER BY {embedding_col} <=> CAST(:query_vector AS halfvec)
                LIMIT :top_k_vector
            ),
            keyword_search AS (
                SELECT
                    id,
                    RANK() OVER (ORDER BY paradedb.score(id) DESC) as rank
                FROM conversation.conversation_blocks
                WHERE discord_id = :discord_id
                  AND conversation_text @@@ :query_text
                  {exclude_clause}
                LIMIT :top_k_fts
            ),
            fused_ranks AS (
                SELECT
                    COALESCE(s.id, k.id) as id,
                    s.vector_distance,
                    (COALESCE(1.0 / (:rrf_k + s.rank), 0.0) + COALESCE(1.0 / (:rrf_k + k.rank), 0.0)) as rrf_score
                FROM semantic_search s
                FULL OUTER JOIN keyword_search k ON s.id = k.id
            )
            SELECT
                cb.id,
                cb.discord_id,
                cb.conversation_text,
                cb.start_time,
                cb.end_time,
                cb.message_count,
                fr.vector_distance,
                fr.rrf_score
            FROM fused_ranks fr
            JOIN conversation.conversation_blocks cb ON fr.id = cb.id
            WHERE (fr.vector_distance IS NULL OR fr.vector_distance <= :max_vector_distance)
            ORDER BY fr.rrf_score DESC
            LIMIT :final_k;
            """
        )

        try:
            result = await session.execute(
                sql_query,
                {
                    "discord_id": discord_id,
                    "query_text": query_text,
                    "query_vector": str(query_vector),
                    "top_k_vector": top_k_vector,
                    "top_k_fts": top_k_fts,
                    "rrf_k": rrf_k,
                    "final_k": final_k,
                    "max_vector_distance": max_vector_distance,
                },
            )
            rows = result.fetchall()
            log.info(f"[对话记忆搜索] 混合搜索返回 {len(rows)} 个结果")
            for i, row in enumerate(rows):
                vector_dist_str = (
                    f"{row.vector_distance:.4f}"
                    if row.vector_distance is not None
                    else "N/A"
                )
                log.debug(
                    f"[对话记忆搜索] 结果 {i + 1}: id={row.id}, "
                    f"vector_distance={vector_dist_str}, "
                    f"rrf_score={row.rrf_score:.6f}"
                )
            return [dict(row._mapping) for row in rows]
        except Exception as e:
            log.error(f"[对话记忆搜索] 搜索出错: {e}", exc_info=True)
            return []

    async def search(
        self,
        discord_id: str,
        query: str,
        exclude_block_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        检索与当前查询相关的历史对话块。

        Args:
            discord_id: 用户 Discord ID
            query: 用户当前的输入
            exclude_block_ids: 要排除的对话块 ID 列表（如刚创建的块）

        Returns:
            检索结果列表，每个结果包含：
            - id: 对话块 ID
            - conversation_text: 对话文本
            - start_time: 开始时间
            - end_time: 结束时间
            - time_description: 时间描述（如"3小时前"）
            - rrf_score: 相关性分数
        """
        log.info(
            f"收到对话记忆搜索请求: 用户={discord_id}, 查询='{query[:50]}...', 排除块={exclude_block_ids}"
        )

        # 检查是否启用对话记忆
        if not self.config.get("enabled", True):
            log.debug("对话记忆功能已禁用")
            return []

        # 检查是否启用向量模式
        if not is_vector_enabled():
            log.debug("向量模式已禁用，跳过对话记忆搜索")
            return []

        try:
            # 生成查询嵌入
            embedding_service = await get_embedding_service()
            query_embedding = await embedding_service.generate_embedding(
                text=query, task_type="retrieval_query"
            )
            if not query_embedding:
                log.error("查询嵌入生成失败")
                return []
        except Exception as e:
            log.error(f"生成查询嵌入时出错: {e}", exc_info=True)
            return []

        search_results = []
        try:
            cleaned_query = self._clean_fts_query(query)

            async with AsyncSessionLocal() as session:
                search_results = await self._hybrid_search_blocks(
                    session,
                    discord_id,
                    cleaned_query,
                    query_embedding,
                    exclude_block_ids,
                )
        except Exception as e:
            log.error(f"执行对话记忆搜索时出错: {e}", exc_info=True)
            return []

        # 格式化结果，添加时间描述
        formatted_results = []
        for res in search_results:
            start_time = res.get("start_time")
            end_time = res.get("end_time")

            # 处理时间类型
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            # 确保时间不为 None
            if start_time is None:
                start_time = datetime.now()
            if end_time is None:
                end_time = datetime.now()

            time_desc = format_time_description(start_time, end_time)

            formatted_results.append(
                {
                    "id": res.get("id"),
                    "conversation_text": res.get("conversation_text"),
                    "start_time": start_time,
                    "end_time": end_time,
                    "time_description": time_desc,
                    "message_count": res.get("message_count"),
                    "rrf_score": float(res.get("rrf_score", 0)),
                }
            )

        log.info(f"对话记忆搜索完成，返回 {len(formatted_results)} 个结果")
        return formatted_results

    def format_blocks_for_context(
        self,
        blocks: List[Dict[str, Any]],
    ) -> str:
        """
        将检索到的对话块格式化为 AI 上下文字符串。

        Args:
            blocks: 检索结果列表

        Returns:
            格式化后的上下文字符串
        """
        if not blocks:
            return ""

        if not self.config.get("show_time_marker", True):
            # 不显示时间标记
            parts = []
            for block in blocks:
                parts.append(f"--- [历史对话] ---\n{block['conversation_text']}")
            return "\n\n".join(parts)

        # 显示时间标记
        parts = []
        for block in blocks:
            time_desc = block.get("time_description", "某个时间")
            text = block.get("conversation_text", "")
            parts.append(f"--- [{time_desc}的对话] ---\n{text}")

        return "\n\n".join(parts)


# 创建单例
conversation_memory_search_service = ConversationMemorySearchService()
