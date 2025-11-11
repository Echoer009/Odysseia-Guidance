import logging
from typing import Dict, Any
import sqlite3
import os

from src import config
from src.chat.services.gemini_service import gemini_service
from src.chat.services.vector_db_service import vector_db_service


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


def _format_content_dict(content_dict: dict) -> str:
    """将 content 字典格式化为多行的 ' - key: value' 字符串列表，并过滤掉不必要的字段。"""
    if not isinstance(content_dict, dict):
        return [f" - {content_dict}"]

    # 定义不应包含在向量化文档中的后端或敏感字段
    EXCLUDED_FIELDS = [
        "discord_id",
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
    text_parts = [f"类别: 俚语", f"名称: {name}"]

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
        self.gemini_service = gemini_service
        self.vector_db_service = vector_db_service
        self.db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")

    def is_ready(self) -> bool:
        """检查服务是否已准备好（所有依赖项都可用）。"""
        return (
            self.vector_db_service.is_available() and self.gemini_service.is_available()
        )

    def _get_db_connection(self):
        """获取数据库连接"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到世界书数据库失败: {e}", exc_info=True)
            return None

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

        # 处理并添加到向量数据库
        success = await self._process_single_entry(rag_entry)

        if success:
            log.info(f"成功将社区成员档案 {member_id} 添加到向量数据库")
        else:
            log.error(f"处理社区成员档案 {member_id} 时失败")

        return success

    def _get_community_member_data(self, member_id: str) -> Dict[str, Any]:
        """从数据库获取社区成员数据"""
        conn = self._get_db_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, discord_number_id, content_json FROM community_members WHERE id = ?",
                (member_id,),
            )
            member_row = cursor.fetchone()

            if member_row:
                member_dict = dict(member_row)

                # 解析content_json
                import json

                if member_dict.get("content_json"):
                    member_dict["content"] = json.loads(member_dict["content_json"])
                    del member_dict["content_json"]

                # 获取关联的昵称
                cursor.execute(
                    "SELECT nickname FROM member_discord_nicknames WHERE member_id = ?",
                    (member_id,),
                )
                nicknames = [row["nickname"] for row in cursor.fetchall()]
                member_dict["discord_nickname"] = nicknames
                log.debug(f"获取社区成员 {member_id} 的昵称: {nicknames}")

                return member_dict

        except Exception as e:
            log.error(f"获取社区成员数据时出错: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

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

    async def _process_single_entry(self, entry: Dict[str, Any]) -> bool:
        """
        处理单个知识条目，生成嵌入并添加到向量数据库

        Args:
            entry: 知识条目字典

        Returns:
            bool: 处理成功返回True，否则返回False
        """
        if not self.is_ready():
            log.warning(f"RAG服务尚未准备就绪，无法处理条目 {entry.get('id')}")
            return False

        try:
            entry_id = entry.get("id", "未知ID")
            log.debug(f"开始处理单个条目: {entry_id}")

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

            # 为每个块生成嵌入并添加到向量数据库
            ids_to_add = []
            documents_to_add = []
            embeddings_to_add = []
            metadatas_to_add = []

            for chunk_index, chunk_content in enumerate(chunks):
                chunk_id = f"{entry_id}:{chunk_index}"
                log.debug(f"正在为块 {chunk_id} 生成嵌入向量...")

                # 生成嵌入向量
                embedding = await self.gemini_service.generate_embedding(
                    text=chunk_content,
                    title=entry.get("title", entry_id),
                    task_type="retrieval_document",
                )

                if embedding:
                    ids_to_add.append(chunk_id)
                    documents_to_add.append(chunk_content)
                    embeddings_to_add.append(embedding)
                    metadatas_to_add.append(entry.get("metadata", {}))
                    log.debug(f"成功为块 {chunk_id} 生成嵌入向量")
                else:
                    log.error(f"无法为块 {chunk_id} 生成嵌入向量")

            # 批量添加到向量数据库
            if ids_to_add:
                log.debug(f"尝试将 {len(ids_to_add)} 个文档块添加到向量数据库...")
                self.vector_db_service.add_documents(
                    ids=ids_to_add,
                    documents=documents_to_add,
                    embeddings=embeddings_to_add,
                    metadatas=metadatas_to_add,
                )
                log.info(
                    f"成功将 {len(ids_to_add)} 个文档块添加到向量数据库，条目 {entry_id} 处理完成。"
                )
                return True
            else:
                log.warning(
                    f"没有成功生成任何嵌入向量，条目 {entry_id} 未添加到向量数据库"
                )
                return False

        except Exception as e:
            log.error(f"处理条目 {entry_id} 时发生错误: {e}", exc_info=True)
            return False

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

        # 处理并添加到向量数据库
        success = await self._process_single_entry(rag_entry)

        if success:
            log.info(f"成功将通用知识条目 {entry_id} 添加到向量数据库")
        else:
            log.error(f"处理通用知识条目 {entry_id} 时失败")

        return success

    def _get_general_knowledge_data(self, entry_id: str) -> Dict[str, Any]:
        """从数据库获取通用知识条目数据"""
        conn = self._get_db_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT gk.id, gk.title, gk.name, gk.content_json, c.name as category_name "
                "FROM general_knowledge gk "
                "LEFT JOIN categories c ON gk.category_id = c.id "
                "WHERE gk.id = ?",
                (entry_id,),
            )
            entry_row = cursor.fetchone()

            if entry_row:
                entry_dict = dict(entry_row)
                log.debug(f"从数据库获取通用知识条目 {entry_id} 成功。")
                return entry_dict

        except Exception as e:
            log.error(f"获取通用知识条目数据时出错: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

        return None

    def _build_rag_entry_from_general_knowledge(
        self, entry_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将通用知识数据构建为RAG条目格式"""
        # 从 content_json 中提取内容文本
        content_text = ""
        if entry_data.get("content_json"):
            try:
                import json

                content_dict = json.loads(entry_data["content_json"])
                content_text = content_dict.get("description", "")
            except (json.JSONDecodeError, TypeError):
                content_text = entry_data.get("content_json", "")

        rag_entry = {
            "id": f"db_{entry_data['id']}",
            "title": entry_data.get("title", entry_data.get("name", entry_data["id"])),
            "name": entry_data.get("name", entry_data["id"]),
            "content": content_text,
            "metadata": {
                "category": entry_data.get("category_name", "通用知识"),
                "source": "database",
                "contributor_id": entry_data.get("contributor_id"),
                "created_at": entry_data.get("created_at"),
            },
        }
        log.debug(f"构建的通用知识 RAG 条目: {rag_entry['id']}")
        return rag_entry

    async def delete_entry(self, entry_id: str) -> bool:
        """
        从向量数据库中删除与指定条目ID相关的所有文档块。

        Args:
            entry_id: 要删除的主条目ID (例如 community_members 的 id)。

        Returns:
            bool: 删除成功返回True，否则返回False。
        """
        if not self.is_ready():
            log.warning(f"RAG服务尚未准备就绪，无法删除条目 {entry_id}")
            return False

        try:
            # ChromaDB 的 get 方法可以按 ID 前缀过滤
            # 我们需要找到所有以 "entry_id:" 开头的文档
            # 注意：ChromaDB 的 get() 方法目前不直接支持前缀搜索。
            # 我们需要获取所有文档然后自己过滤，或者使用 where 查询。
            # 一个更高效的方法是，如果知道分块数量，就直接生成ID。
            # 但我们不知道，所以采用 where 查询。

            # 为了避免潜在的SQL注入风险（尽管这里不是SQL），我们使用 where 子句
            # ChromaDB 的 ID 是字符串，所以 entry_id 必须是字符串
            str_entry_id = str(entry_id)

            # 使用 get 方法获取与主 ID 相关的所有条目
            # 我们只需要 id 字段来执行删除
            # 备用策略：获取集合中的所有ID，然后在本地进行过滤。
            # 这在集合很大时效率很低。
            all_ids = self.vector_db_service.get_all_ids()
            # 检查原始 ID 和带 'db_' 前缀的 ID
            prefixed_id = f"db_{str_entry_id}"
            ids_to_delete = [
                doc_id
                for doc_id in all_ids
                if doc_id.startswith(f"{str_entry_id}:")
                or doc_id.startswith(f"{prefixed_id}:")
            ]
            if not ids_to_delete:
                log.warning(
                    f"在向量数据库中没有找到与条目 {entry_id} 相关的文档块可供删除。"
                )
                return True  # 认为操作成功，因为目标状态（不存在）已达成

            log.debug(
                f"找到 {len(ids_to_delete)} 个与条目 {entry_id} 相关的文档块，准备删除: {ids_to_delete}"
            )

            self.vector_db_service.delete_documents(ids=ids_to_delete)

            log.info(
                f"成功删除了与条目 {entry_id} 相关的 {len(ids_to_delete)} 个文档块。"
            )
            return True

        except Exception as e:
            log.error(f"删除条目 {entry_id} 的向量时发生错误: {e}", exc_info=True)
            return False


# 全局实例
incremental_rag_service = IncrementalRAGService()
