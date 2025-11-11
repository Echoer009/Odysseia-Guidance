import logging
from typing import Optional, List, Dict, Any
import sqlite3
import json
import os

import asyncio

# 导入新的服务依赖
from src.chat.services.gemini_service import GeminiService, gemini_service
from src.chat.services.vector_db_service import VectorDBService, vector_db_service
from src import config
from src.chat.config import chat_config
from src.chat.features.world_book.services.incremental_rag_service import (
    incremental_rag_service,
)

log = logging.getLogger(__name__)

# 定义数据库文件路径
DB_PATH = os.path.join(config.DATA_DIR, "world_book.sqlite3")


class WorldBookService:
    """
    使用向量数据库进行语义搜索，以查找相关的世界书条目。
    同时支持通过 Discord ID 直接从 SQLite 数据库查找用户档案。
    """

    def __init__(self, gemini_svc: GeminiService, vector_db_svc: VectorDBService):
        self.gemini_service = gemini_svc
        self.vector_db_service = vector_db_svc
        log.info("WorldBookService (RAG + SQLite version) 初始化完成。")

    def _get_db_connection(self):
        """建立并返回一个新的 SQLite 数据库连接。"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到世界书数据库 '{DB_PATH}' 失败: {e}", exc_info=True)
            return None

    def get_profile_by_discord_id(self, discord_id: str) -> Optional[Dict[str, Any]]:
        """
        根据 Discord 数字 ID 精确查找社区成员的档案。

        Args:
            discord_id: 用户的 Discord 数字 ID (字符串格式)。

        Returns:
            如果找到匹配的成员，则返回该成员的完整条目字典，否则返回 None。
        """
        if not discord_id:
            return None

        conn = self._get_db_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM community_members WHERE discord_number_id = ?",
                (str(discord_id),),
            )
            member_row = cursor.fetchone()

            if not member_row:
                return None

            member_dict = dict(member_row)
            log.debug(
                f"成功通过 Discord ID '{discord_id}' 找到了社区成员 '{member_dict.get('id')}' 的档案。"
            )
            log.debug(f"数据库原始数据 (member_row): {member_row}")

            # 获取关联的昵称
            cursor.execute(
                "SELECT nickname FROM member_discord_nicknames WHERE member_id = ?",
                (member_dict["id"],),
            )
            nicknames = [row["nickname"] for row in cursor.fetchall()]
            member_dict["discord_nickname"] = nicknames

            # 解析 content_json
            if member_dict.get("content_json"):
                member_dict["content"] = json.loads(member_dict["content_json"])
                del member_dict["content_json"]

            log.debug(f"解析后的用户档案 (member_dict): {member_dict}")
            return member_dict
        except sqlite3.Error as e:
            log.error(
                f"通过 Discord ID '{discord_id}' 查找档案时发生数据库错误: {e}",
                exc_info=True,
            )
            return None
        finally:
            if conn:
                conn.close()

    def is_ready(self) -> bool:
        """检查服务是否已准备好（所有依赖项都可用）。"""
        return (
            self.vector_db_service.is_available() and self.gemini_service.is_available()
        )

    async def find_entries(
        self,
        latest_query: str,
        user_id: int,
        guild_id: int,
        user_name: str,  # 新增：接收提问者的名字
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        n_results: int = chat_config.RAG_N_RESULTS_DEFAULT,
        max_distance: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """
        根据用户的最新问题和可选的对话历史，总结查询并查找相关的世界书条目。

        Args:
            latest_query: 用户最新的原始消息。
            user_id: 用户的 Discord ID。
            guild_id: 服务器的 Discord ID。
            conversation_history: (可选) 用于生成查询的特定对话历史。
            n_results: 要返回的结果数量。
            max_distance: RAG 搜索的距离阈值，用于过滤不相关的结果。

        Returns:
            一个包含最相关条目信息的字典列表。
        """
        if not self.is_ready() or not latest_query:
            if not latest_query:
                log.debug("latest_query 为空，跳过 RAG 搜索。")
            else:
                log.warning("WorldBookService 尚未准备就绪，无法执行 find_entries。")
            return []

        # 2. 使用 GeminiService 总结对话历史以生成查询
        # 在将历史记录传递给RAG总结器之前，移除最后一条由系统注入的上下文提示
        history_for_rag = conversation_history.copy() if conversation_history else []
        if history_for_rag and history_for_rag[-1].get("role") == "model":
            # 通过一个独特的标记来识别这条系统消息
            if (
                "我会按好感度和上下文综合回复"
                in history_for_rag[-1].get("parts", [""])[0]
            ):
                history_for_rag.pop()
                log.debug("已为RAG总结移除系统注入的上下文提示。")

        # --- RAG 查询总结 ---
        if config.RAG_QUERY_REWRITING_ENABLED:
            # 1. 准备对话历史，最多取最近3轮
            history_for_summary = (
                history_for_rag[-3:] if len(history_for_rag) > 3 else history_for_rag
            )
            log.info(
                f"准备为RAG总结查询。原始查询: '{latest_query}', 使用对话历史轮数: {len(history_for_summary)}"
            )

            # 2. 调用总结服务
            summarized_query = await self.gemini_service.summarize_for_rag(
                latest_query=latest_query,
                user_name=user_name,
                conversation_history=history_for_summary,
            )

            # 3. 处理总结结果
            if summarized_query:
                log.info(f"RAG 总结查询成功: '{summarized_query}'")
            else:
                # 如果总结失败，回退到使用格式化后的原始查询
                from src.chat.services.regex_service import regex_service

                clean_query = regex_service.clean_user_input(latest_query)
                summarized_query = f"[{user_name}]: {clean_query}"
                log.warning(
                    f"RAG 查询总结失败，将回退到使用格式化的原始查询: '{summarized_query}'"
                )
        else:
            # 如果禁用了查询重写，直接使用格式化的原始查询
            from src.chat.services.regex_service import regex_service

            clean_query = regex_service.clean_user_input(latest_query)
            summarized_query = f"[{user_name}]: {clean_query}"
            log.info(
                f"RAG查询重写功能已禁用，使用格式化的原始查询: '{summarized_query}'"
            )

        # 4. 确保查询字符串不为空
        if not summarized_query.strip():
            log.warning(f"最终查询为空，无法进行RAG搜索 (user_id: {user_id})")
            return []

        # 3. 为总结出的查询生成嵌入
        # 添加额外的空值检查，防止 clewdr 422 错误
        if not summarized_query or not summarized_query.strip():
            log.warning(
                f"总结后的查询为空或只包含空白字符，跳过嵌入生成: '{summarized_query}'"
            )
            return []

        query_embedding = await self.gemini_service.generate_embedding(
            text=summarized_query, task_type="RETRIEVAL_QUERY"
        )
        log.debug(f"RAG 查询嵌入生成状态: {'成功' if query_embedding else '失败'}")

        if not query_embedding:
            log.error("无法为 RAG 查询生成嵌入。")
            return []

        # 4. 执行向量搜索
        try:
            search_results = self.vector_db_service.search(
                query_embedding=query_embedding,
                n_results=n_results,
                max_distance=max_distance,
            )

            if search_results:
                search_brief = [
                    f"{r['id']}({r['distance']:.4f})" for r in search_results
                ]
                log.debug(f"RAG 搜索简报 (ID 和 距离): {search_brief}")
            else:
                log.debug("RAG 搜索未返回任何结果。")

            return search_results
        except Exception as e:
            log.error(f"在 RAG 搜索过程中发生错误: {e}", exc_info=True)
            return []

    def add_general_knowledge(
        self,
        title: str,
        name: str,
        content_text: str,
        category_name: str,
        contributor_id: int = None,
    ) -> bool:
        """
        向 general_knowledge 表添加一个新的知识条目。

        Args:
            title: 知识条目的标题
            name: 知识条目的名称
            content_text: 知识条目的内容文本
            category_name: 知识条目的类别名称
            contributor_id: 贡献者的 Discord ID (可选)

        Returns:
            bool: 添加成功返回 True，否则返回 False
        """
        log.info(
            f"尝试添加通用知识条目: title='{title}', name='{name}', category='{category_name}'"
        )
        conn = self._get_db_connection()
        if not conn:
            log.error("数据库连接不可用，无法添加知识条目。")
            return False

        try:
            cursor = conn.cursor()

            # 1. 检查或创建类别
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
            category_row = cursor.fetchone()

            if category_row:
                category_id = category_row[0]
                log.debug(f"类别 '{category_name}' 已存在，ID: {category_id}")
            else:
                # 如果类别不存在，则创建新类别
                cursor.execute(
                    "INSERT INTO categories (name) VALUES (?)", (category_name,)
                )
                category_id = cursor.lastrowid
                log.info(f"创建了新类别: {category_name} (ID: {category_id})")

            # 2. 准备内容数据
            # 根据 build_vector_index.py 中的处理方式，我们需要将内容组织成字典格式
            # 这里我们简单地将文本内容作为 "description" 字段
            content_dict = {"description": content_text}
            content_json = json.dumps(content_dict, ensure_ascii=False)
            log.debug(f"知识条目内容 JSON: {content_json}")

            # 3. 生成唯一的条目 ID
            # 使用标题和时间戳生成一个唯一ID
            import time
            import re

            # 清理标题，只保留字母、数字、中文和下划线，用作ID的一部分
            clean_title = re.sub(r"[^\w\u4e00-\u9fff]", "_", title)[:50]  # 限制长度
            entry_id = f"{clean_title}_{int(time.time())}"
            log.debug(f"生成的知识条目 ID: {entry_id}")

            # 4. 插入新条目
            cursor.execute(
                """
                INSERT INTO general_knowledge (id, title, name, content_json, category_id, contributor_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
                (entry_id, title, name, content_json, category_id, contributor_id),
            )

            conn.commit()
            log.info(f"成功添加知识条目: {entry_id} ({title}) 到类别 {category_name}")

            # 异步调用增量RAG服务，将新条目添加到向量数据库
            log.info(f"正在为新知识条目 {entry_id} 创建异步向量化任务...")
            asyncio.create_task(
                incremental_rag_service.process_general_knowledge(entry_id)
            )

            return True

        except sqlite3.Error as e:
            log.error(f"添加知识条目时发生数据库错误: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        except Exception as e:
            log.error(f"添加知识条目时发生未知错误: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()


# 使用已导入的全局服务实例来创建 WorldBookService 的单例
world_book_service = WorldBookService(gemini_service, vector_db_service)
