import logging
from typing import Dict, Any
import os
import asyncio
from functools import wraps
import json

import psycopg2
from psycopg2.extras import DictCursor


def async_retry(retries=3, delay=5):
    """
    一个异步函数的重试装饰器。

    Args:
        retries (int): 最大重试次数。
        delay (int): 每次重试之间的延迟秒数。
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    log.warning(
                        f"函数 {func.__name__} 第 {attempt + 1} 次执行失败: {e}"
                    )
                    if attempt + 1 == retries:
                        log.error(
                            f"函数 {func.__name__} 在 {retries} 次尝试后最终失败。"
                        )
                        raise
                    await asyncio.sleep(delay)

        return wrapper

    return decorator


# 复制必要的函数，避免导入路径问题
def create_text_chunks(text: str, max_chars: int = 1000) -> list[str]:
    """
    根据句子边界将长文本分割成更小的块。
    该函数会尝试创建尽可能大但不超过 max_chars 的文本块。
    """
    import re

    if not text or not text.strip():
        return []

    text = text.strip()

    # 如果整个文本已经足够小，将其作为单个块返回。
    if len(text) <= max_chars:
        return [text]

    # 按句子分割文本。正则表达式包含中英文常见的句子结束符以及换行符。
    sentences = re.split(r"(?<=[。？！.!?\n])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return []

    final_chunks = []
    current_chunk = ""
    for sentence in sentences:
        # 如果单个句子超过 max_chars，它将自成一块。
        # 这是一种备用策略，理想情况下应通过格式良好的源数据来避免。
        if len(sentence) > max_chars:
            if current_chunk:
                final_chunks.append(current_chunk)
            final_chunks.append(sentence)
            current_chunk = ""
            continue

        # 如果添加下一个句子会超过 max_chars 限制，
        # 则完成当前块并开始一个新块。
        if len(current_chunk) + len(sentence) + 1 > max_chars:  # +1 是为了空格
            final_chunks.append(current_chunk)
            current_chunk = sentence
        else:
            # 否则，将句子添加到当前块。
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    # 将最后一个剩余的块添加到列表中。
    if current_chunk:
        final_chunks.append(current_chunk)

    return final_chunks


def _format_content_dict(content_dict: dict) -> list[str]:
    """将 content 字典格式化为多行的 ' - key: value' 字符串列表，并过滤掉不必要的字段。"""
    if not isinstance(content_dict, dict):
        return [f" - {content_dict}"]

    # 定义不应包含在向量化文档中的后端或敏感字段
    EXCLUDED_FIELDS = [
        "discord_id",
        "discord_number_id",  # 新增：过滤掉数字ID，防止泄露到RAG上下文
        "uploaded_by",
        "uploaded_by_name",  # 新增：过滤掉上传者姓名
        "update_target_id",
        "purchase_info",
        "item_id",
        "price",
    ]

    filtered_lines = []
    for key, value in content_dict.items():
        # 新增条件: 确保 value 不为空或 None，从而过滤掉 background: "" 这样的空字段
        if key not in EXCLUDED_FIELDS and value:
            filtered_lines.append(f" - {key}: {value}")

    return filtered_lines


def _build_text_community_member(entry: dict) -> str:
    """为"社区成员"类别构建结构化文本。"""
    text_parts = ["类别: 社区成员"]

    nicknames = entry.get("discord_nickname", [])
    if nicknames:
        text_parts.append("昵称:")
        text_parts.extend([f" - {name}" for name in nicknames])

    content_lines = _format_content_dict(entry.get("content", {}))
    if content_lines:
        text_parts.append("人物信息:")
        text_parts.extend(content_lines)

    return "\n".join(text_parts)


def _build_text_generic(entry: dict, category_name: str) -> str:
    """为"社区信息"、"文化"、"事件"等通用类别构建结构化文本。"""
    name = entry.get("name", entry.get("id", ""))
    text_parts = [f"类别: {category_name}", f"名称: {name}"]

    aliases = entry.get("aliases", [])
    if aliases:
        text_parts.append("别名:")
        text_parts.extend([f" - {alias}" for alias in aliases])

    content_lines = _format_content_dict(entry.get("content", {}))
    if content_lines:
        text_parts.append("描述:")
        text_parts.extend(content_lines)

    return "\n".join(text_parts)


def _build_text_slang(entry: dict) -> str:
    """为"俚语"类别构建结构化文本。"""
    name = entry.get("name", entry.get("id", ""))
    text_parts = ["类别: 俚语", f"名称: {name}"]

    aliases = entry.get("aliases", [])
    if aliases:
        text_parts.append("也称作:")
        text_parts.extend([f" - {alias}" for alias in aliases])

    refers_to = entry.get("refers_to", [])
    if refers_to:
        text_parts.append("通常指代:")
        text_parts.extend([f" - {item}" for item in refers_to])

    content_lines = _format_content_dict(entry.get("content", {}))
    if content_lines:
        text_parts.append("具体解释:")
        text_parts.extend(content_lines)

    return "\n".join(text_parts)


def _build_text_general_knowledge(entry: dict) -> str:
    """为"通用知识"类别构建结构化文本。"""
    name = entry.get("name", entry.get("title", ""))
    text_parts = [f"类别: 通用知识", f"名称: {name}"]

    content_dict = entry.get("content", {})
    if isinstance(content_dict, dict) and content_dict.get("description"):
        text_parts.append("描述:")
        text_parts.append(f" - {content_dict['description']}")

    return "\n".join(text_parts)


def build_document_text(entry: dict) -> str:
    """
    根据条目的类别，调用相应的函数来构建用于嵌入的文本文档。
    这是一个总调度函数。
    """
    category = entry.get("metadata", {}).get("category")

    # 将类别映射到相应的构建函数
    builders = {
        "社区成员": _build_text_community_member,
        "社区信息": lambda e: _build_text_generic(e, "社区信息"),
        "社区文化": lambda e: _build_text_generic(e, "社区文化"),
        "社区大事件": lambda e: _build_text_generic(e, "社区大事件"),
        "俚语": _build_text_slang,
        "通用知识": _build_text_general_knowledge,
    }

    builder_func = builders.get(category)

    if builder_func:
        return builder_func(entry)
    else:
        # 如果没有找到特定的构建器，则记录警告并使用默认的 content 转换
        import logging

        log = logging.getLogger(__name__)
        log.warning(
            f"条目 '{entry.get('id')}' 的类别 '{category}' 没有找到特定的文本构建器，将使用默认内容。"
        )
        content = entry.get("content", "")
        return str(content) if isinstance(content, dict) else content


log = logging.getLogger(__name__)


class IncrementalRAGService:
    """
    增量RAG处理服务，用于实时处理新添加的知识条目
    """

    def __init__(self):
        self.gemini_service = None
        self.parade_conn = None

    def _get_gemini_service(self):
        """延迟导入 Gemini 服务以避免循环导入。"""
        if self.gemini_service is None:
            from src.chat.services.gemini_service import gemini_service

            self.gemini_service = gemini_service
        return self.gemini_service

    def is_ready(self) -> bool:
        """检查服务是否已准备好（所有依赖项都可用）。"""
        gemini_service = self._get_gemini_service()
        return gemini_service.is_available()

    def _get_parade_connection(self):
        """获取 Parade DB 连接"""
        if self.parade_conn is None:
            try:
                if os.getenv("RUNNING_IN_DOCKER"):
                    db_host = "odysseia_pg_db"
                else:
                    db_host = "localhost"

                self.parade_conn = psycopg2.connect(
                    dbname=os.getenv("POSTGRES_DB", "braingirl_db"),
                    user=os.getenv("POSTGRES_USER", "user"),
                    password=os.getenv("POSTGRES_PASSWORD", "password"),
                    host=db_host,
                    port=os.getenv("DB_PORT", "5432"),
                )
                log.debug("成功连接到 Parade DB")
            except Exception as e:
                log.error(f"连接到 Parade DB 失败: {e}", exc_info=True)
                return None
        return self.parade_conn

    @async_retry(retries=3, delay=5)
    async def process_community_member(self, member_id: str) -> bool:
        """
        处理单个社区成员档案，将其添加到向量数据库

        Args:
            member_id: 社区成员的ID

        Returns:
            bool: 处理成功返回True，否则返回False
        """
        if not self.is_ready():
            log.warning("RAG服务尚未准备就绪，无法处理社区成员档案")
            return False

        # 从数据库获取成员信息
        log.debug(f"尝试处理社区成员档案: {member_id}")
        member_data = self._get_community_member_data(member_id)
        if not member_data:
            log.error(f"无法找到社区成员数据: {member_id}")
            return False
        log.debug(f"成功获取社区成员数据: {member_id}")

        # 构建RAG条目格式
        rag_entry = self._build_rag_entry_from_member(member_data)
        log.debug(f"为社区成员 {member_id} 构建RAG条目: {rag_entry.get('id')}")

        # 处理并添加到 Parade DB 向量数据库
        success = await self._process_single_entry_to_parade(rag_entry, "community")

        if success:
            log.info(f"成功将社区成员档案 {member_id} 添加到向量数据库")
        else:
            log.error(f"处理社区成员档案 {member_id} 时失败")

        return success

    def _get_community_member_data(self, member_id: str) -> Dict[str, Any] | None:
        """从 Parade DB 获取社区成员数据"""
        conn = self._get_parade_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                """
                SELECT id, external_id, discord_id, title, full_text, source_metadata
                FROM community.member_profiles
                WHERE id = %s
                """,
                (member_id,),
            )

            member_row = cursor.fetchone()

            if member_row:
                member_dict = dict(member_row)
                log.debug(f"从 Parade DB 获取社区成员 {member_id} 成功")

                # 解析 full_text 字段
                full_text = member_dict.get("full_text", "")
                if full_text:
                    try:
                        cleaned_full_text = full_text.strip()
                        if cleaned_full_text.startswith("{"):
                            content_data = json.loads(cleaned_full_text)
                        elif '{"name":' in cleaned_full_text:
                            # 提取 JSON 部分
                            json_start = cleaned_full_text.find("{")
                            json_end = cleaned_full_text.rfind("}") + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = cleaned_full_text[json_start:json_end]
                                content_data = json.loads(json_str)
                            else:
                                content_data = {}
                        else:
                            content_data = {}

                        member_dict["content"] = content_data
                    except (json.JSONDecodeError, TypeError) as e:
                        log.warning(
                            f"解析 community.member_profiles #{member_id} 的 full_text 失败: {e}"
                        )
                        member_dict["content"] = {}

                # 解析 source_metadata 字段
                source_metadata = member_dict.get("source_metadata")
                if source_metadata and not member_dict.get("content"):
                    try:
                        if isinstance(source_metadata, str):
                            # 尝试解析为 JSON
                            try:
                                metadata = json.loads(source_metadata)
                            except json.JSONDecodeError:
                                # 如果不是标准 JSON，尝试使用 ast.literal_eval 解析 Python 字典
                                import ast

                                metadata = ast.literal_eval(source_metadata)
                        else:
                            metadata = source_metadata

                        # 从 source_metadata 的 content_json 字段中提取数据
                        if "content_json" in metadata:
                            content_json_str = metadata["content_json"]
                            if isinstance(content_json_str, str):
                                content_data = json.loads(content_json_str)
                            else:
                                content_data = content_json_str
                            member_dict["content"] = content_data
                        else:
                            # 如果没有 content_json，使用 metadata 本身
                            member_dict["content"] = metadata
                    except (
                        json.JSONDecodeError,
                        TypeError,
                        ValueError,
                        SyntaxError,
                    ) as e:
                        log.warning(
                            f"解析 community.member_profiles #{member_id} 的 source_metadata 失败: {e}"
                        )
                        member_dict["content"] = {}

                # 如果没有解析出 content，创建一个空的
                if "content" not in member_dict:
                    member_dict["content"] = {}

                # 获取昵称（如果有的话）
                member_dict["discord_nickname"] = []

                return member_dict

        except Exception as e:
            log.error(f"从 Parade DB 获取社区成员数据时出错: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()

        return None

    def _build_rag_entry_from_member(
        self, member_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将社区成员数据构建为RAG条目格式"""
        rag_entry = {
            "id": member_data["id"],
            "title": member_data.get("title", member_data["id"]),
            "name": member_data.get("content", {}).get("name", "未命名"),
            "content": member_data.get("content", {}),
            "metadata": {
                "category": "社区成员",
                "source": "community_upload",
                "uploaded_by": member_data.get("content", {}).get("uploaded_by"),
                "uploaded_by_name": member_data.get("content", {}).get(
                    "uploaded_by_name"
                ),
            },
            "discord_nickname": member_data.get("discord_nickname", []),
        }
        log.debug(f"构建的社区成员 RAG 条目: {rag_entry['id']}")
        return rag_entry

    async def _process_single_entry_to_parade(
        self, entry: Dict[str, Any], table_type: str
    ) -> bool:
        """
        处理单个知识条目，生成嵌入并添加到 Parade DB 向量数据库

        Args:
            entry: 知识条目字典
            table_type: 表类型，'community' 或 'general_knowledge'

        Returns:
            bool: 处理成功返回True，否则返回False
        """
        if not self.is_ready():
            log.warning(f"Gemini 服务尚未准备就绪，无法处理条目 {entry.get('id')}")
            return False

        try:
            entry_id = entry.get("id", "未知ID")
            log.debug(f"开始处理单个条目到 Parade DB: {entry_id}")

            # 构建文档文本
            document_text = build_document_text(entry)
            if not document_text:
                log.error(f"无法为条目 {entry_id} 构建文档文本")
                return False

            log.debug(f"为条目 {entry_id} 构建文档文本成功，长度: {len(document_text)}")

            # 文本分块
            chunks = create_text_chunks(document_text, max_chars=1000)
            if not chunks:
                log.warning(f"条目 {entry_id} 的内容无法分块或分块后为空")
                return False

            log.debug(f"条目 {entry_id} 被分割成 {len(chunks)} 个块")

            # 首先删除旧的向量数据
            await self._delete_entry_from_parade(entry_id, table_type)

            # 为每个块生成嵌入并添加到 Parade DB
            success_count = 0
            conn = self._get_parade_connection()
            if not conn:
                return False

            cursor = conn.cursor()

            try:
                for chunk_index, chunk_content in enumerate(chunks):
                    log.debug(f"正在为块 {chunk_index} 生成嵌入向量...")

                    # 生成嵌入向量
                    gemini_service = self._get_gemini_service()
                    embedding = await gemini_service.generate_embedding(
                        text=chunk_content,
                        title=entry.get("title", entry_id),
                        task_type="retrieval_document",
                    )

                    if not embedding:
                        log.error(f"无法为块 {chunk_index} 生成嵌入向量")
                        raise Exception(f"无法为块 {chunk_index} 生成嵌入向量")

                    # 将嵌入向量转换为 PostgreSQL vector 类型要求的格式
                    # vector 类型需要数组格式，如 '[0.1, 0.2, 0.3]'
                    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

                    if table_type == "community":
                        # 插入到 community.member_chunks 表
                        cursor.execute(
                            """
                            INSERT INTO community.member_chunks
                            (profile_id, chunk_index, chunk_text, embedding)
                            VALUES (%s, %s, %s, %s::vector)
                            """,
                            (entry_id, chunk_index, chunk_content, embedding_str),
                        )
                    else:  # general_knowledge
                        # 插入到 general_knowledge.knowledge_chunks 表
                        cursor.execute(
                            """
                            INSERT INTO general_knowledge.knowledge_chunks
                            (document_id, chunk_index, chunk_text, embedding)
                            VALUES (%s, %s, %s, %s::vector)
                            """,
                            (entry_id, chunk_index, chunk_content, embedding_str),
                        )

                    success_count += 1
                    log.debug(f"成功为块 {chunk_index} 生成嵌入向量并存入 Parade DB")

                conn.commit()
                cursor.close()

                if success_count > 0:
                    log.info(
                        f"成功将 {success_count} 个文档块添加到 Parade DB 向量数据库，条目 {entry_id} 处理完成。"
                    )
                    return True
                else:
                    log.warning(
                        f"没有成功生成任何嵌入向量，条目 {entry_id} 未添加到 Parade DB 向量数据库"
                    )
                    return False

            except Exception as e:
                log.error(f"处理条目 {entry_id} 时发生错误: {e}", exc_info=True)
                if conn:
                    conn.rollback()
                if cursor:
                    cursor.close()
                return False

        except Exception as e:
            log.error(f"处理条目 {entry_id} 时发生错误: {e}", exc_info=True)
            return False

    async def _delete_entry_from_parade(self, entry_id: str, table_type: str) -> bool:
        """
        从 Parade DB 向量数据库中删除与指定条目ID相关的所有文档块。

        Args:
            entry_id: 要删除的主条目ID
            table_type: 表类型，'community' 或 'general_knowledge'

        Returns:
            bool: 删除成功返回True，否则返回False
        """
        try:
            conn = self._get_parade_connection()
            if not conn:
                return False

            cursor = conn.cursor()

            if table_type == "community":
                cursor.execute(
                    "DELETE FROM community.member_chunks WHERE profile_id = %s",
                    (entry_id,),
                )
                log.info(
                    f"从 community.member_chunks 表中删除了与 profile_id {entry_id} 相关的所有文档块"
                )
            else:  # general_knowledge
                cursor.execute(
                    "DELETE FROM general_knowledge.knowledge_chunks WHERE document_id = %s",
                    (entry_id,),
                )
                log.info(
                    f"从 general_knowledge.knowledge_chunks 表中删除了与 document_id {entry_id} 相关的所有文档块"
                )

            conn.commit()
            cursor.close()
            return True

        except Exception as e:
            log.error(
                f"从 Parade DB 删除条目 {entry_id} 的向量时发生错误: {e}", exc_info=True
            )
            return False

    @async_retry(retries=3, delay=5)
    async def process_general_knowledge(self, entry_id: str) -> bool:
        """
        处理单个通用知识条目，将其添加到向量数据库

        Args:
            entry_id: 通用知识条目的ID

        Returns:
            bool: 处理成功返回True，否则返回False
        """
        if not self.is_ready():
            log.warning("RAG服务尚未准备就绪，无法处理通用知识条目")
            return False

        log.debug(f"尝试处理通用知识条目: {entry_id}")
        # 从数据库获取通用知识条目
        entry_data = self._get_general_knowledge_data(entry_id)
        if not entry_data:
            log.error(f"无法找到通用知识条目: {entry_id}")
            return False
        log.debug(f"成功获取通用知识条目数据: {entry_id}")

        # 构建RAG条目格式
        rag_entry = self._build_rag_entry_from_general_knowledge(entry_data)
        log.debug(f"为通用知识条目 {entry_id} 构建RAG条目: {rag_entry.get('id')}")

        # 处理并添加到 Parade DB 向量数据库
        success = await self._process_single_entry_to_parade(
            rag_entry, "general_knowledge"
        )

        if success:
            log.info(f"成功将通用知识条目 {entry_id} 添加到向量数据库")
        else:
            log.error(f"处理通用知识条目 {entry_id} 时失败")

        return success

    def _get_general_knowledge_data(self, entry_id: str) -> Dict[str, Any] | None:
        """从 Parade DB 获取通用知识条目数据"""
        conn = self._get_parade_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(
                """
                SELECT id, external_id, title, full_text, source_metadata
                FROM general_knowledge.knowledge_documents
                WHERE id = %s
                """,
                (entry_id,),
            )

            entry_row = cursor.fetchone()

            if entry_row:
                entry_dict = dict(entry_row)
                log.debug(f"从 Parade DB 获取通用知识条目 {entry_id} 成功")

                # 解析 full_text 字段
                full_text = entry_dict.get("full_text", "")
                if full_text:
                    try:
                        cleaned_full_text = full_text.strip()
                        if cleaned_full_text.startswith("{"):
                            content_data = json.loads(cleaned_full_text)
                        else:
                            # 如果不是 JSON，直接作为文本内容
                            content_data = {"description": cleaned_full_text}
                        entry_dict["content"] = content_data
                    except (json.JSONDecodeError, TypeError) as e:
                        log.warning(
                            f"解析 general_knowledge.knowledge_documents #{entry_id} 的 full_text 失败: {e}"
                        )
                        entry_dict["content"] = {"description": cleaned_full_text}

                # 解析 source_metadata 字段
                source_metadata = entry_dict.get("source_metadata")
                if source_metadata and not entry_dict.get("content"):
                    try:
                        if isinstance(source_metadata, str):
                            # 尝试解析为 JSON
                            try:
                                metadata = json.loads(source_metadata)
                            except json.JSONDecodeError:
                                # 如果不是标准 JSON，尝试使用 ast.literal_eval 解析 Python 字典
                                import ast

                                metadata = ast.literal_eval(source_metadata)
                        else:
                            metadata = source_metadata
                        entry_dict["content"] = metadata
                    except (
                        json.JSONDecodeError,
                        TypeError,
                        ValueError,
                        SyntaxError,
                    ) as e:
                        log.warning(
                            f"解析 general_knowledge.knowledge_documents #{entry_id} 的 source_metadata 失败: {e}"
                        )
                        entry_dict["content"] = {}

                # 如果没有解析出 content，创建一个空的
                if "content" not in entry_dict:
                    entry_dict["content"] = {}

                return entry_dict

        except Exception as e:
            log.error(f"从 Parade DB 获取通用知识条目数据时出错: {e}", exc_info=True)
        finally:
            if cursor:
                cursor.close()

        return None

    def _build_rag_entry_from_general_knowledge(
        self, entry_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将通用知识数据构建为RAG条目格式"""
        content = entry_data.get("content", {})

        source_metadata = {}
        raw_source_metadata = entry_data.get("source_metadata")
        if isinstance(raw_source_metadata, str):
            try:
                source_metadata = json.loads(raw_source_metadata)
            except json.JSONDecodeError:
                pass
        elif isinstance(raw_source_metadata, dict):
            source_metadata = raw_source_metadata

        rag_entry = {
            "id": entry_data["id"],
            "title": entry_data.get("title", ""),
            "name": source_metadata.get("name", entry_data.get("title", "")),
            "content": content,
            "metadata": {
                "category": "通用知识",
                "source": "database",
                "contributor_id": source_metadata.get("contributor_id"),
                "created_at": str(entry_data.get("created_at", "")),
            },
        }
        log.debug(f"构建的通用知识 RAG 条目: {rag_entry['id']}")
        return rag_entry

    async def delete_entry(self, entry_id: str) -> bool:
        """
        从 Parade DB 向量数据库中删除与指定条目ID相关的所有文档块。

        Args:
            entry_id: 要删除的主条目ID

        Returns:
            bool: 删除成功返回True，否则返回False
        """
        try:
            log.info(
                f"开始在 Parade DB 向量数据库中删除与 entry_id '{entry_id}' 相关的所有文档块。"
            )

            # 尝试从 community.member_chunks 表中删除
            community_success = await self._delete_entry_from_parade(
                entry_id, "community"
            )

            # 尝试从 general_knowledge.knowledge_chunks 表中删除
            knowledge_success = await self._delete_entry_from_parade(
                entry_id, "general_knowledge"
            )

            # 如果至少有一个表删除成功，或者两个表都没有数据（也视为成功）
            if community_success or knowledge_success:
                log.info(
                    f"成功从 Parade DB 向量数据库中删除了与条目 {entry_id} 相关的文档块。"
                )
                return True
            else:
                log.warning(
                    f"在 Parade DB 向量数据库中没有找到与条目 {entry_id} 相关的文档块可供删除。"
                )
                return True  # 认为操作成功，因为目标状态（不存在）已达成

        except Exception as e:
            log.error(f"删除条目 {entry_id} 的向量时发生错误: {e}", exc_info=True)
            return False


# 全局实例
incremental_rag_service = IncrementalRAGService()
