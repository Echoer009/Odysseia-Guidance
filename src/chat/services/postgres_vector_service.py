# -*- coding: utf-8 -*-
import logging
import json
import asyncpg
from typing import List, Dict, Any, Optional

from src.config import PG_HOST, PG_PORT, PG_DATABASE, PG_USER, PG_PASSWORD

log = logging.getLogger(__name__)


class PostgresVectorService:
    """
    使用 asyncpg 连接池与 PostgreSQL (pgvector) 交互的服务。
    """

    def __init__(self):
        self._pool = None

    async def initialize(self):
        """
        异步初始化数据库连接池。必须在使用服务前调用。
        """
        if self._pool:
            return
        try:
            self._pool = await asyncpg.create_pool(
                host=PG_HOST,
                port=PG_PORT,
                database=PG_DATABASE,
                user=PG_USER,
                password=PG_PASSWORD,
                min_size=2,
                max_size=10,
            )
            log.info("成功创建 PostgreSQL (pgvector) 数据库连接池。")
        except Exception as e:
            log.error(f"创建 PostgreSQL 连接池失败: {e}", exc_info=True)
            self._pool = None

    def is_available(self) -> bool:
        """检查连接池是否已成功初始化。"""
        return self._pool is not None

    async def search(
        self,
        table_name: str,
        query_embedding: List[float],
        n_results: int = 5,
        max_distance: float = 0.7,
        where_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        在指定的表中执行向量相似度搜索或元数据过滤。
        - 如果提供了 query_embedding，则执行相似度搜索。
        - 如果 query_embedding 为 None，则仅根据 where_filter 进行过滤和排序。
        """
        if not self.is_available():
            log.error("PostgresVectorService 不可用，无法执行搜索。")
            return []

        params = []
        param_idx = 1

        # -- 构建 WHERE 子句 ---
        where_clauses = []
        if query_embedding:
            where_clauses.append(f"(embedding <=> ${param_idx}) <= ${param_idx + 1}")
            params.extend([json.dumps(query_embedding), max_distance])
            param_idx += 2

        if where_filter:
            # 简化的过滤器转换，目前只支持 AND 连接的精确匹配
            for key, value in where_filter.items():
                where_clauses.append(f"(metadata->>'{key}')::text = ${param_idx}")
                params.append(
                    str(value)
                )  # JSONB ->> 返回 text，所以需要将 value 转为字符串
                param_idx += 1

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # -- 构建 ORDER BY 子句 ---
        if query_embedding:
            order_by_sql = f"ORDER BY embedding <=> $1"
        else:
            # 如果没有查询向量，则按时间戳倒序排序
            order_by_sql = "ORDER BY (metadata->>'created_timestamp')::float DESC"

        # -- 构建完整查询 ---
        query = f"""
            SELECT
                id,
                document,
                metadata,
                {(f"embedding <=> ${params.index(json.dumps(query_embedding)) + 1} AS distance") if query_embedding else "0.0 AS distance"}
            FROM {table_name}
            WHERE {where_sql}
            {order_by_sql}
            LIMIT ${param_idx};
        """
        params.append(n_results)

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

            results = [
                {
                    "id": row["id"],
                    "content": row["document"],
                    "metadata": json.loads(row["metadata"])
                    if isinstance(row["metadata"], str)
                    else row["metadata"],
                    "distance": row["distance"],
                }
                for row in rows
            ]
            return results
        except Exception as e:
            log.error(f"在表 '{table_name}' 中执行向量搜索时出错: {e}", exc_info=True)
            return []

    async def add_vectors(
        self,
        table_name: str,
        ids: List[str],
        vectors: List[List[float]],
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ):
        """批量添加向量、文档和元数据到指定的表中。"""
        if not self._pool:
            log.error("连接池未初始化。")
            return

        # 将元数据字典转换为 JSON 字符串
        metadata_json_list = [json.dumps(m, ensure_ascii=False) for m in metadatas]

        # pgvector 要求向量是字符串格式 '[...]'
        vector_strings = [str(v) for v in vectors]

        records_to_insert = list(
            zip(ids, vector_strings, documents, metadata_json_list)
        )

        query = f"""
            INSERT INTO {table_name} (id, embedding, document, metadata)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                document = EXCLUDED.document,
                metadata = EXCLUDED.metadata;
        """

        try:
            async with self._pool.acquire() as conn:
                # 使用 executemany 进行批量插入/更新
                await conn.executemany(query, records_to_insert)
            log.info(
                f"成功向表 '{table_name}' 中添加/更新了 {len(records_to_insert)} 条向量数据。"
            )
        except Exception as e:
            log.error(f"向表 '{table_name}' 中批量添加向量时出错: {e}", exc_info=True)

    async def get_min_timestamp(
        self, table_name: str, where_filter: Dict[str, Any]
    ) -> Optional[str]:
        """获取满足条件的记录中，created_at 最小的时间戳。"""
        if not self.is_available():
            return None

        params = []
        param_idx = 1
        where_clauses = []
        if where_filter:
            for key, value in where_filter.items():
                where_clauses.append(f"(metadata->>'{key}')::text = ${param_idx}")
                params.append(str(value))
                param_idx += 1

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT MIN(metadata->>'created_at') as min_created_at
            FROM {table_name}
            WHERE {where_sql};
        """
        try:
            async with self._pool.acquire() as conn:
                min_timestamp = await conn.fetchval(query, *params)
            return min_timestamp
        except Exception as e:
            log.error(f"在表 '{table_name}' 中查询最小时间戳时出错: {e}", exc_info=True)
            return None


# 全局实例
postgres_vector_service = PostgresVectorService()
