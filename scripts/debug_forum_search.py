# -*- coding: utf-8 -*-
"""
论坛搜索交互式调试脚本

用于模拟 bot 调用论坛搜索工具，实时调试搜索参数。
支持三种搜索模式：
1. 混合搜索 (Hybrid Search) - 向量 + BM25，使用 RRF 融合
2. BM25 全文搜索
3. 向量搜索

使用方法：
    python scripts/debug_forum_search.py
"""

import asyncio
import logging
import sys
import os
from typing import Optional, List, Dict, Any
from sqlalchemy import text

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.database import AsyncSessionLocal
from src.chat.config.chat_config import (
    FORUM_RAG_CONFIG,
    FORUM_RAG_MAX_DISTANCE,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)

# 允许的频道名称列表
ALLOWED_CATEGORIES = [
    "世界书",
    "全性向",
    "其他区",
    "制卡工具区",
    "女性向",
    "工具区",
    "插件",
    "教程",
    "深渊区",
    "男性向",
    "纯净区",
    "美化",
    "预设",
    "️其它工具区",
]


class ForumSearchDebugger:
    """论坛搜索调试器"""

    def __init__(self):
        self.ollama_embedding_service = None
        self.default_config = {
            "top_k_vector": FORUM_RAG_CONFIG.get("TOP_K_VECTOR", 20),
            "top_k_fts": FORUM_RAG_CONFIG.get("TOP_K_FTS", 20),
            "rrf_k": FORUM_RAG_CONFIG.get("RRF_K", 60),
            "final_k": FORUM_RAG_CONFIG.get("HYBRID_SEARCH_FINAL_K", 5),
            "max_distance": FORUM_RAG_MAX_DISTANCE,
            "use_hybrid": True,
            "exact_match_boost": FORUM_RAG_CONFIG.get("EXACT_MATCH_BOOST", 1000.0),
        }
        self.config = self.default_config.copy()

    def _get_ollama_embedding_service(self):
        """延迟导入 Ollama embedding 服务"""
        if self.ollama_embedding_service is None:
            from src.chat.services.ollama_embedding_service import (
                ollama_embedding_service,
            )

            self.ollama_embedding_service = ollama_embedding_service
        return self.ollama_embedding_service

    async def check_services(self) -> bool:
        """检查服务是否可用"""
        print("\n🔍 检查服务状态...")

        # 检查数据库连接
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            print("  ✅ 数据库连接正常")
        except Exception as e:
            print(f"  ❌ 数据库连接失败: {e}")
            return False

        # 检查 Ollama 服务
        try:
            ollama_service = self._get_ollama_embedding_service()
            if ollama_service.check_connection_sync():
                print("  ✅ Ollama Embedding 服务正常")
            else:
                print("  ❌ Ollama Embedding 服务不可用")
                return False
        except Exception as e:
            print(f"  ❌ Ollama 服务检查失败: {e}")
            return False

        return True

    def print_config(self):
        """打印当前配置"""
        print("\n📋 当前搜索配置:")
        print(f"  - 向量搜索 Top-K: {self.config['top_k_vector']}")
        print(f"  - BM25 搜索 Top-K: {self.config['top_k_fts']}")
        print(f"  - RRF 常数 K: {self.config['rrf_k']}")
        print(f"  - 最终返回数量: {self.config['final_k']}")
        print(f"  - 最大距离阈值: {self.config['max_distance']}")
        print(f"  - 精确匹配加成: {self.config.get('exact_match_boost', 1000.0)}")
        print(
            f"  - 搜索模式: {'混合搜索' if self.config['use_hybrid'] else 'BM25 全文搜索'}"
        )

    def print_categories(self):
        """打印可用的频道分类"""
        print("\n📂 可用的频道分类:")
        for i, cat in enumerate(ALLOWED_CATEGORIES, 1):
            print(f"  {i:2}. {cat}")

    async def search_hybrid(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行混合搜索（向量 + BM25）
        """
        ollama_service = self._get_ollama_embedding_service()

        # 生成查询向量
        print("\n🔄 正在生成查询向量...")
        query_embedding = await ollama_service.generate_embedding(
            text=query, task_type="retrieval_query"
        )
        if not query_embedding:
            print("  ❌ 无法生成查询向量")
            return []

        print(f"  ✅ 向量生成完成 (维度: {len(query_embedding)})")

        # 执行混合搜索
        print("\n🔍 执行混合搜索...")
        import time

        start_time = time.monotonic()

        # 构建自定义 SQL 查询以获取详细分数
        from sqlalchemy import text

        async with AsyncSessionLocal() as session:
            sql_query = text(
                """
                WITH semantic_search AS (
                    SELECT
                        ft.id,
                        ft.thread_id,
                        ft.thread_name,
                        ft.author_name,
                        ft.author_id,
                        ft.category_name,
                        ft.channel_id,
                        ft.guild_id,
                        ft.created_at,
                        ft.embedding <=> CAST(:query_vector AS halfvec) as vector_distance,
                        RANK() OVER (ORDER BY ft.embedding <=> CAST(:query_vector AS halfvec)) as vector_rank
                    FROM forum.forum_threads ft
                    WHERE ft.embedding IS NOT NULL
                    ORDER BY ft.embedding <=> CAST(:query_vector AS halfvec)
                    LIMIT :top_k_vector
                ),
                keyword_search AS (
                    SELECT
                        ft.id,
                        ft.thread_id,
                        ft.thread_name,
                        ft.author_name,
                        ft.author_id,
                        ft.category_name,
                        ft.channel_id,
                        ft.guild_id,
                        ft.created_at,
                        paradedb.score(ft.id) as bm25_score,
                        RANK() OVER (ORDER BY paradedb.score(ft.id) DESC) as bm25_rank
                    FROM forum.forum_threads ft
                    WHERE ft.content @@@ :query_text
                    LIMIT :top_k_fts
                ),
                fused_ranks AS (
                    SELECT
                        COALESCE(s.id, k.id) as id,
                        COALESCE(s.thread_id, k.thread_id) as thread_id,
                        COALESCE(s.thread_name, k.thread_name) as thread_name,
                        COALESCE(s.author_name, k.author_name) as author_name,
                        COALESCE(s.author_id, k.author_id) as author_id,
                        COALESCE(s.category_name, k.category_name) as category_name,
                        COALESCE(s.channel_id, k.channel_id) as channel_id,
                        COALESCE(s.guild_id, k.guild_id) as guild_id,
                        COALESCE(s.created_at, k.created_at) as created_at,
                        s.vector_distance,
                        s.vector_rank,
                        k.bm25_score,
                        k.bm25_rank,
                        (COALESCE(1.0 / (:rrf_k + s.vector_rank), 0.0) + COALESCE(1.0 / (:rrf_k + k.bm25_rank), 0.0)) as rrf_score
                    FROM semantic_search s
                    FULL OUTER JOIN keyword_search k ON s.id = k.id
                )
                SELECT
                    fr.*,
                    fr.rrf_score,
                    CASE 
                        WHEN ft.content ILIKE '%' || :query_text || '%' 
                             OR ft.thread_name ILIKE '%' || :query_text || '%' THEN 1 
                        ELSE 0 
                    END as exact_match,
                    (fr.rrf_score + CASE 
                        WHEN ft.content ILIKE '%' || :query_text || '%' 
                             OR ft.thread_name ILIKE '%' || :query_text || '%' THEN :exact_match_boost 
                        ELSE 0.0 
                    END) as final_score
                FROM fused_ranks fr
                JOIN forum.forum_threads ft ON fr.id = ft.id
                WHERE (fr.vector_distance IS NULL OR fr.vector_distance <= :max_distance)
                ORDER BY final_score DESC
                LIMIT :final_k
                """
            )

            params = {
                "query_vector": str(query_embedding),
                "query_text": query,
                "top_k_vector": self.config["top_k_vector"],
                "top_k_fts": self.config["top_k_fts"],
                "rrf_k": self.config["rrf_k"],
                "final_k": self.config["final_k"],
                "max_distance": self.config["max_distance"],
                "exact_match_boost": self.config.get("exact_match_boost", 1000.0),
            }

            # 添加过滤条件
            if filters:
                conditions = []
                for key, value in filters.items():
                    if value is None:
                        continue
                    if key == "category_name":
                        if isinstance(value, list):
                            placeholders = ", ".join(
                                [f":cat_{i}" for i in range(len(value))]
                            )
                            conditions.append(f"fr.category_name IN ({placeholders})")
                            for i, v in enumerate(value):
                                params[f"cat_{i}"] = v
                        else:
                            conditions.append("fr.category_name = :category_name")
                            params["category_name"] = value
                    elif key == "author_id":
                        conditions.append("fr.author_id = :author_id")
                        params["author_id"] = value
                    elif key == "start_date":
                        conditions.append("fr.created_at >= :start_date")
                        params["start_date"] = value
                    elif key == "end_date":
                        conditions.append("fr.created_at <= :end_date")
                        params["end_date"] = value

                if conditions:
                    sql_query = text(
                        sql_query.text.replace(
                            "ORDER BY fr.rrf_score DESC",
                            " AND ".join(conditions) + " ORDER BY fr.rrf_score DESC",
                        )
                    )

            result = await session.execute(sql_query, params)
            rows = result.fetchall()

        duration = time.monotonic() - start_time
        print(f"  ⏱️ 搜索耗时: {duration:.4f} 秒")

        return [dict(row._mapping) for row in rows]

    async def search_bm25(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行 BM25 全文搜索
        """
        print("\n🔍 执行 BM25 全文搜索...")
        import time

        start_time = time.monotonic()

        from sqlalchemy import text

        async with AsyncSessionLocal() as session:
            sql_query = text(
                """
                SELECT
                    ft.id,
                    ft.thread_id,
                    ft.thread_name,
                    ft.author_name,
                    ft.author_id,
                    ft.category_name,
                    ft.channel_id,
                    ft.guild_id,
                    ft.created_at,
                    paradedb.score(ft.id) as bm25_score
                FROM forum.forum_threads ft
                WHERE ft.content @@@ :query
                """
            )

            params: Dict[str, Any] = {"query": query}
            conditions = []

            if filters:
                for key, value in filters.items():
                    if value is None:
                        continue
                    if key == "category_name":
                        if isinstance(value, list):
                            placeholders = ", ".join(
                                [f":cat_{i}" for i in range(len(value))]
                            )
                            conditions.append(f"ft.category_name IN ({placeholders})")
                            for i, v in enumerate(value):
                                params[f"cat_{i}"] = v
                        else:
                            conditions.append("ft.category_name = :category_name")
                            params["category_name"] = value
                    elif key == "author_id":
                        conditions.append("ft.author_id = :author_id")
                        params["author_id"] = value
                    elif key == "start_date":
                        conditions.append("ft.created_at >= :start_date")
                        params["start_date"] = value
                    elif key == "end_date":
                        conditions.append("ft.created_at <= :end_date")
                        params["end_date"] = value

            if conditions:
                sql_query = text(sql_query.text + " AND " + " AND ".join(conditions))

            sql_query = text(
                sql_query.text
                + """
                ORDER BY bm25_score DESC
                LIMIT :limit
                """
            )
            params["limit"] = self.config["final_k"]

            result = await session.execute(sql_query, params)
            rows = result.fetchall()

        duration = time.monotonic() - start_time
        print(f"  ⏱️ 搜索耗时: {duration:.4f} 秒")

        return [dict(row._mapping) for row in rows]

    async def search_vector_only(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        执行纯向量搜索
        """
        ollama_service = self._get_ollama_embedding_service()

        # 生成查询向量
        print("\n🔄 正在生成查询向量...")
        query_embedding = await ollama_service.generate_embedding(
            text=query, task_type="retrieval_query"
        )
        if not query_embedding:
            print("  ❌ 无法生成查询向量")
            return []

        print(f"  ✅ 向量生成完成 (维度: {len(query_embedding)})")

        print("\n🔍 执行向量搜索...")
        import time

        start_time = time.monotonic()

        async with AsyncSessionLocal() as session:
            sql_query = text(
                """
                SELECT
                    ft.id,
                    ft.thread_id,
                    ft.thread_name,
                    ft.author_name,
                    ft.author_id,
                    ft.category_name,
                    ft.channel_id,
                    ft.guild_id,
                    ft.created_at,
                    ft.embedding <=> CAST(:query_vector AS halfvec) as vector_distance
                FROM forum.forum_threads ft
                WHERE ft.embedding IS NOT NULL
                    AND ft.embedding <=> CAST(:query_vector AS halfvec) <= :max_distance
                """
            )

            params: Dict[str, Any] = {
                "query_vector": str(query_embedding),
                "max_distance": self.config["max_distance"],
            }
            conditions = []

            if filters:
                for key, value in filters.items():
                    if value is None:
                        continue
                    if key == "category_name":
                        if isinstance(value, list):
                            placeholders = ", ".join(
                                [f":cat_{i}" for i in range(len(value))]
                            )
                            conditions.append(f"ft.category_name IN ({placeholders})")
                            for i, v in enumerate(value):
                                params[f"cat_{i}"] = v
                        else:
                            conditions.append("ft.category_name = :category_name")
                            params["category_name"] = value
                    elif key == "author_id":
                        conditions.append("ft.author_id = :author_id")
                        params["author_id"] = value
                    elif key == "start_date":
                        conditions.append("ft.created_at >= :start_date")
                        params["start_date"] = value
                    elif key == "end_date":
                        conditions.append("ft.created_at <= :end_date")
                        params["end_date"] = value

            if conditions:
                sql_query = text(sql_query.text + " AND " + " AND ".join(conditions))

            sql_query = text(
                sql_query.text
                + """
                ORDER BY vector_distance ASC
                LIMIT :limit
                """
            )
            params["limit"] = self.config["final_k"]

            result = await session.execute(sql_query, params)
            rows = result.fetchall()

        duration = time.monotonic() - start_time
        print(f"  ⏱️ 搜索耗时: {duration:.4f} 秒")

        return [dict(row._mapping) for row in rows]

    def print_results(self, results: List[Dict[str, Any]], search_type: str = "hybrid"):
        """打印搜索结果"""
        if not results:
            print("\n❌ 没有找到匹配的结果")
            return

        print(f"\n✅ 找到 {len(results)} 条结果:")
        print("=" * 80)

        for i, result in enumerate(results, 1):
            thread_id = result.get("thread_id", "N/A")
            thread_name = result.get("thread_name", "未知标题")
            author_name = result.get("author_name", "未知作者")
            category_name = result.get("category_name", "未知分类")
            created_at = result.get("created_at")
            guild_id = result.get("guild_id", "N/A")

            # 格式化时间
            if created_at:
                if isinstance(created_at, str):
                    created_str = created_at[:19]  # 截取到秒
                else:
                    created_str = created_at.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_str = "N/A"

            # 构建链接
            if guild_id and thread_id:
                thread_url = f"https://discord.com/channels/{guild_id}/{thread_id}"
            else:
                thread_url = "N/A"

            print(f"\n📌 结果 #{i}")
            print(f"  📖 标题: {thread_name}")
            print(f"  👤 作者: {author_name}")
            print(f"  📂 分类: {category_name}")
            print(f"  📅 时间: {created_str}")
            print(f"  🔗 链接: {thread_url}")

            # 打印分数
            if search_type == "hybrid":
                rrf_score = result.get("rrf_score", 0)
                final_score = result.get("final_score", rrf_score)
                exact_match = result.get("exact_match", 0)
                vector_distance = result.get("vector_distance")
                vector_rank = result.get("vector_rank")
                bm25_score = result.get("bm25_score")
                bm25_rank = result.get("bm25_rank")

                print("  📊 分数详情:")
                # 精确匹配标志
                if exact_match:
                    print("     🎯 精确匹配: ✓ (已加成)")
                print(f"     最终分数: {final_score:.6f}")
                print(f"     RRF 综合分数: {rrf_score:.6f}")
                if vector_distance is not None:
                    print(f"     向量距离: {vector_distance:.6f} (排名: {vector_rank})")
                else:
                    print("     向量距离: N/A (未进入向量搜索结果)")
                if bm25_score is not None:
                    print(f"     BM25 分数: {bm25_score:.6f} (排名: {bm25_rank})")
                else:
                    print("     BM25 分数: N/A (未进入全文搜索结果)")

            elif search_type == "bm25":
                bm25_score = result.get("bm25_score", 0)
                print(f"  📊 BM25 分数: {bm25_score:.6f}")

            elif search_type == "vector":
                vector_distance = result.get("vector_distance", 0)
                similarity = 1 - vector_distance
                print(f"  📊 向量距离: {vector_distance:.6f}")
                print(f"     相似度: {similarity:.6f}")

            print("-" * 80)

    def parse_filters(self, filter_input: str) -> Dict[str, Any]:
        """解析过滤条件输入"""
        filters = {}
        if not filter_input.strip():
            return filters

        # 格式: key=value,key=value
        parts = filter_input.split(",")
        for part in parts:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()

            if key == "category_name":
                # 支持多个分类，用 | 分隔
                if "|" in value:
                    filters[key] = [v.strip() for v in value.split("|")]
                else:
                    filters[key] = value
            elif key == "author_id":
                try:
                    filters[key] = int(value)
                except ValueError:
                    print(f"  ⚠️ 无效的 author_id: {value}")
            elif key in ["start_date", "end_date"]:
                filters[key] = value

        return filters


def print_help():
    """打印帮助信息"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        论坛搜索交互式调试工具                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 命令说明:                                                                     ║
║   <关键词>              - 使用当前模式搜索帖子                                 ║
║   /hybrid <关键词>      - 使用混合搜索 (向量 + BM25)                          ║
║   /bm25 <关键词>        - 使用 BM25 全文搜索                                  ║
║   /vector <关键词>      - 使用纯向量搜索                                      ║
║   /config               - 查看当前配置                                        ║
║   /set <参数> <值>      - 修改配置参数                                        ║
║   /categories           - 查看可用的频道分类                                  ║
║   /filter <条件>        - 设置过滤条件                                        ║
║   /clear                - 清除过滤条件                                        ║
║   /help                 - 显示此帮助信息                                      ║
║   /quit 或 /exit        - 退出程序                                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 过滤条件格式:                                                                 ║
║   category_name=预设,author_id=123456,start_date=2024-01-01                 ║
║   多个分类用 | 分隔: category_name=预设|教程|插件                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ 可配置参数:                                                                   ║
║   top_k_vector  - 向量搜索返回的初始结果数量 (默认: 20)                       ║
║   top_k_fts     - BM25 搜索返回的初始结果数量 (默认: 20)                      ║
║   rrf_k         - RRF 算法中的排名常数 (默认: 60)                             ║
║   final_k       - 最终返回的帖子数量 (默认: 5)                                ║
║   max_distance  - 最大距离阈值 (默认: 0.4)                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")


async def main():
    """主函数"""
    print("\n🚀 论坛搜索交互式调试工具")
    print("=" * 50)

    debugger = ForumSearchDebugger()

    # 检查服务
    if not await debugger.check_services():
        print("\n❌ 服务检查失败，请确保数据库和 Ollama 服务正常运行")
        return

    debugger.print_config()
    print_help()

    current_filters = {}

    while True:
        try:
            user_input = input("\n🔍 请输入搜索命令 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n👋 再见!")
            break

        if not user_input:
            continue

        # 解析命令
        if user_input.startswith("/"):
            parts = user_input.split(maxsplit=2)
            cmd = parts[0].lower()

            if cmd in ["/quit", "/exit"]:
                print("👋 再见!")
                break

            elif cmd == "/help":
                print_help()

            elif cmd == "/config":
                debugger.print_config()
                if current_filters:
                    print(f"\n🔍 当前过滤条件: {current_filters}")

            elif cmd == "/categories":
                debugger.print_categories()

            elif cmd == "/set":
                if len(parts) < 3:
                    print("⚠️ 用法: /set <参数> <值>")
                    continue
                param = parts[1]
                try:
                    value = (
                        int(parts[2]) if param != "max_distance" else float(parts[2])
                    )
                    if param in debugger.config:
                        debugger.config[param] = value
                        print(f"✅ 已设置 {param} = {value}")
                    else:
                        print(f"⚠️ 未知参数: {param}")
                except ValueError:
                    print(f"⚠️ 无效的值: {parts[2]}")

            elif cmd == "/filter":
                if len(parts) < 2:
                    print("⚠️ 用法: /filter <条件>")
                    print("   示例: /filter category_name=预设,author_id=123456")
                    continue
                current_filters = debugger.parse_filters(parts[1])
                print(f"✅ 已设置过滤条件: {current_filters}")

            elif cmd == "/clear":
                current_filters = {}
                print("✅ 已清除过滤条件")

            elif cmd == "/hybrid":
                if len(parts) < 2:
                    print("⚠️ 用法: /hybrid <关键词>")
                    continue
                query = parts[1]
                results = await debugger.search_hybrid(query, current_filters)
                debugger.print_results(results, "hybrid")

            elif cmd == "/bm25":
                if len(parts) < 2:
                    print("⚠️ 用法: /bm25 <关键词>")
                    continue
                query = parts[1]
                results = await debugger.search_bm25(query, current_filters)
                debugger.print_results(results, "bm25")

            elif cmd == "/vector":
                if len(parts) < 2:
                    print("⚠️ 用法: /vector <关键词>")
                    continue
                query = parts[1]
                results = await debugger.search_vector_only(query, current_filters)
                debugger.print_results(results, "vector")

            else:
                print(f"⚠️ 未知命令: {cmd}")
                print("   输入 /help 查看可用命令")

        else:
            # 默认使用混合搜索
            results = await debugger.search_hybrid(user_input, current_filters)
            debugger.print_results(results, "hybrid")


if __name__ == "__main__":
    asyncio.run(main())
