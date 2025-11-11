# -*- coding: utf-8 -*-

import os
import sys
import asyncio
import logging
import re
import sqlite3
import argparse
from dotenv import load_dotenv

# --- 配置项目根路径 ---
# 这使得脚本可以从任何位置运行，同时能够正确导入 src 目录下的模块
# 获取当前脚本文件的绝对路径
current_script_path = os.path.abspath(__file__)
# 获取脚本所在目录的路径 (scripts)
script_dir = os.path.dirname(current_script_path)
# 获取项目根目录的路径 (Odysseia-Guidance)
project_root = os.path.dirname(script_dir)
# 将项目根目录添加到 sys.path
sys.path.insert(0, project_root)
# --- 路径配置结束 ---

# --- 环境变量加载 ---
# 必须在导入任何服务之前加载环境变量
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
    print(".env 文件已加载。")  # 使用 print 以便在日志配置前就能看到
else:
    print(".env 文件未找到，请确保 GEMINI_API_KEYS 已在环境中设置。")
# --- 环境变量加载结束 ---


# 现在可以安全地导入项目模块
from src.chat.services.gemini_service import gemini_service
from src.chat.services.vector_db_service import vector_db_service

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- 并发配置 ---
# 定义同时向 Gemini API 发出的最大并发请求数
# 这有助于在提高速度的同时，避免触发API的速率限制
CONCURRENCY_LIMIT = 16


# 定义知识库文件路径
KNOWLEDGE_FILE_PATH = os.path.join(
    project_root, "src", "chat", "features", "world_book", "data", "knowledge.yml"
)

# 定义世界之书数据库路径
WORLD_BOOK_DB_PATH = os.path.join(project_root, "data", "world_book.sqlite3")


def create_text_chunks(text: str, max_chars: int = 1000) -> list[str]:
    """
    根据句子边界将长文本分割成更小的块。
    该函数会尝试创建尽可能大但不超过 max_chars 的文本块。
    """
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


# --- 文本构建器 ---


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
    """为“社区成员”类别构建结构化文本。"""
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
    """为“社区信息”、“文化”、“事件”等通用类别构建结构化文本。"""
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
    """为“俚语”类别构建结构化文本。"""
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
        "社区知识": lambda e: _build_text_generic(e, "社区知识"),
    }

    builder_func = builders.get(category)

    if builder_func:
        return builder_func(entry)
    else:
        # 如果没有找到特定的构建器，则记录警告并使用默认的 content 转换
        log.warning(
            f"条目 '{entry.get('id')}' 的类别 '{category}' 没有找到特定的文本构建器，将使用默认内容。"
        )
        content = entry.get("content", "")
        return str(content) if isinstance(content, dict) else content


def load_general_knowledge_from_db() -> list:
    """
    从 world_book.sqlite3 数据库加载所有通用知识条目，并正确连接类别信息。
    返回一个字典列表，格式与 RAG 系统所需的标准格式一致。
    """
    db_entries = []
    try:
        with sqlite3.connect(WORLD_BOOK_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # 彻底修正: 使用 LEFT JOIN 查询来获取 category_name，并确保所有列名正确。
            query = """
            SELECT
                gk.id,
                gk.title,
                gk.name,
                gk.content_json,
                cat.name AS category_name,
                gk.contributor_id,
                gk.created_at
            FROM
                general_knowledge AS gk
            LEFT JOIN
                categories AS cat ON gk.category_id = cat.id
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            import json

            for row in rows:
                content_data = {}
                if row["content_json"]:
                    try:
                        content_data = json.loads(row["content_json"])
                    except json.JSONDecodeError:
                        log.warning(
                            f"条目 id='db_{row['id']}' 的 content_json 解析失败。"
                        )

                entry = {
                    "id": f"db_{row['id']}",
                    "title": row["title"] or row["name"],
                    "name": row["name"],
                    "content": content_data,
                    "metadata": {
                        "category": row["category_name"]
                        or "通用知识",  # 现在 category_name 是正确的
                        "source": "database",
                        "contributor_id": row["contributor_id"],
                        "created_at": row["created_at"],
                    },
                }
                db_entries.append(entry)

        log.info(f"成功从数据库加载了 {len(db_entries)} 个通用知识条目。")
    except sqlite3.Error as e:
        log.error(f"从数据库读取通用知识条目时出错: {e}")
    except Exception as e:
        log.error(f"处理数据库条目时发生未知错误: {e}", exc_info=True)

    return db_entries


def load_community_members_from_db() -> list:
    """
    从 world_book.sqlite3 数据库的 community_members 表中加载所有条目，
    并将其格式化为 RAG 系统所需的标准格式。
    """
    db_entries = []
    try:
        with sqlite3.connect(WORLD_BOOK_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row  # 允许通过列名访问数据
            cursor = conn.cursor()
            # 获取所有社区成员的核心信息
            cursor.execute("SELECT id, title, content_json FROM community_members")
            members = cursor.fetchall()

            import json

            for member_row in members:
                member_dict = dict(member_row)

                # 解析 content_json
                if member_dict.get("content_json"):
                    try:
                        member_dict["content"] = json.loads(member_dict["content_json"])
                    except json.JSONDecodeError:
                        member_dict["content"] = {}
                else:
                    member_dict["content"] = {}

                # 获取该成员的所有昵称
                nick_cursor = conn.cursor()
                nick_cursor.execute(
                    "SELECT nickname FROM member_discord_nicknames WHERE member_id = ?",
                    (member_dict["id"],),
                )
                nicknames = [row["nickname"] for row in nick_cursor.fetchall()]
                member_dict["discord_nickname"] = nicknames

                # 构建与增量服务一致的 RAG 条目格式
                entry = {
                    "id": member_dict["id"],
                    "title": member_dict.get("title", member_dict["id"]),
                    "name": member_dict.get("content", {}).get("name", "未命名"),
                    "content": member_dict.get("content", {}),
                    "metadata": {
                        "category": "社区成员",
                        "source": "community_upload",
                    },
                    "discord_nickname": member_dict.get("discord_nickname", []),
                }
                db_entries.append(entry)

        log.info(f"成功从数据库加载了 {len(db_entries)} 个社区成员档案。")
    except sqlite3.Error as e:
        log.error(f"从数据库读取社区成员档案时出错: {e}")
    except Exception as e:
        log.error(f"处理社区成员档案时发生未知错误: {e}", exc_info=True)

    return db_entries


async def sync_knowledge(knowledge_entries: list, data_type_name: str):
    """
    通用的知识同步函数，负责文本块生成、并发嵌入和数据写入。
    """
    if not knowledge_entries:
        log.info(f"没有找到需要同步的 {data_type_name} 数据。")
        return [], []

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = []
    chunk_details = []  # 用于在并发执行后将结果映射回原始数据

    # 任务准备：遍历所有条目和块，创建异步任务
    log.info("开始准备并发嵌入任务...")
    for entry in knowledge_entries:
        if not all(k in entry for k in ["id", "content", "metadata"]):
            log.warning(f"跳过格式不正确的条目: {entry}")
            continue

        original_id = str(entry["id"])
        entry_title = entry.get("title", original_id)
        document_text = build_document_text(entry)
        chunks = create_text_chunks(document_text, max_chars=1000)

        if not chunks:
            log.warning(f"条目 id='{original_id}' 的内容无法分块，跳过。")
            continue

        for chunk_index, chunk_content in enumerate(chunks):
            chunk_id = f"{original_id}:{chunk_index}"

            # 定义一个带信号量控制的协程
            async def generate_with_semaphore(
                text, title, task_type="retrieval_document"
            ):
                async with semaphore:
                    return await gemini_service.generate_embedding(
                        text=text, title=title, task_type=task_type
                    )

            task = asyncio.create_task(
                generate_with_semaphore(chunk_content, entry_title)
            )
            tasks.append(task)
            chunk_details.append(
                {
                    "id": chunk_id,
                    "document": chunk_content,
                    "metadata": entry["metadata"],
                }
            )

    log.info(
        f"任务准备完成，总共创建了 {len(tasks)} 个嵌入任务。开始并发处理（限制: {CONCURRENCY_LIMIT}）..."
    )

    # 并发执行所有任务
    embedding_results = await asyncio.gather(*tasks, return_exceptions=True)

    log.info("所有嵌入任务已执行完毕，开始处理结果...")

    # 结果处理：将成功的结果整理用于批量添加
    ids_to_add = []
    documents_to_add = []
    embeddings_to_add = []
    metadatas_to_add = []

    for i, result in enumerate(embedding_results):
        detail = chunk_details[i]
        if isinstance(result, Exception):
            log.error(f"块 {detail['id']} 的嵌入任务失败: {result}")
        elif result:
            ids_to_add.append(detail["id"])
            documents_to_add.append(detail["document"])
            embeddings_to_add.append(result)
            metadatas_to_add.append(detail["metadata"])
        else:
            log.warning(f"块 {detail['id']} 未能生成嵌入向量，已跳过。")

    # 6. 将数据批量添加到向量数据库
    if ids_to_add:
        log.info(
            f"准备将 {len(ids_to_add)} 个 {data_type_name} 文档块批量写入向量数据库..."
        )
        vector_db_service.add_documents(
            ids=ids_to_add,
            documents=documents_to_add,
            embeddings=embeddings_to_add,
            metadatas=metadatas_to_add,
        )
    else:
        log.warning(f"没有成功为 {data_type_name} 生成任何嵌入向量，无需更新数据库。")

    return ids_to_add, embedding_results


async def run_sync_all():
    """模式: all - 完全重建整个向量数据库。"""
    log.info("--- 模式: all - 开始完全重建向量数据库 ---")
    log.info("正在重建向量数据库集合以确保数据同步...")
    vector_db_service.recreate_collection()
    if not vector_db_service.is_available():
        log.error("重建集合后，VectorDBService 变为不可用。脚本终止。")
        return
    log.info("集合重建成功。")

    db_knowledge_entries = load_general_knowledge_from_db()
    member_entries = load_community_members_from_db()
    all_entries = db_knowledge_entries + member_entries

    ids_added, results = await sync_knowledge(all_entries, "所有知识")

    log.info("--- 全量重建完成 ---")
    log.info(f"处理摘要:")
    log.info(f"  - 总共处理了 {len(all_entries)} 个知识条目。")
    log.info(f"  - 成功生成并存储了 {len(ids_added)} 个文本块。")
    log.info(f"  - {len(results) - len(ids_added)} 个文本块未能成功处理。")


async def run_sync_members():
    """模式: member - 精准同步社区成员数据。"""
    log.info("--- 模式: member - 开始精准同步社区成员数据 ---")

    old_ids = vector_db_service.get_ids_by_metadata(
        filter_dict={"category": "社区成员"}
    )
    log.info(f"在向量数据库中找到了 {len(old_ids)} 个旧的社区成员文本块。")

    if old_ids:
        vector_db_service.delete_documents(ids=old_ids)
        log.info(f"已成功删除 {len(old_ids)} 个旧文本块。")

    latest_entries = load_community_members_from_db()
    ids_added, results = await sync_knowledge(latest_entries, "社区成员")

    log.info("--- 社区成员同步完成 ---")
    deleted_member_ids = {chunk_id.split(":")[0] for chunk_id in old_ids}
    added_member_ids = {chunk_id.split(":")[0] for chunk_id in ids_added}
    unreplenished_ids = deleted_member_ids - added_member_ids

    log.info(f"处理摘要:")
    log.info(
        f"  - 删除了 {len(old_ids)} 个旧文本块 (来自 {len(deleted_member_ids)} 个成员)。"
    )
    log.info(
        f"  - 新增了 {len(ids_added)} 个新文本块 (来自 {len(added_member_ids)} 个成员)。"
    )
    if unreplenished_ids:
        log.warning(
            f"  - {len(unreplenished_ids)} 个成员的旧数据已被彻底清除: {', '.join(sorted(list(unreplenished_ids)))}"
        )


async def run_sync_general():
    """模式: general - 精准同步通用知识数据。"""
    log.info("--- 模式: general - 开始精准同步通用知识数据 ---")

    # ChromaDB 的 `where` 过滤器尚不支持 `$ne` (不等于) 操作。
    # 因此，我们需要获取所有ID，再减去成员ID，来得到通用知识ID。
    all_ids = vector_db_service.get_all_ids()
    member_ids = set(
        vector_db_service.get_ids_by_metadata(filter_dict={"category": "社区成员"})
    )
    old_ids = [id_ for id_ in all_ids if id_ not in member_ids]
    log.info(f"在向量数据库中找到了 {len(old_ids)} 个旧的通用知识文本块。")

    if old_ids:
        vector_db_service.delete_documents(ids=old_ids)
        log.info(f"已成功删除 {len(old_ids)} 个旧文本块。")

    latest_entries = load_general_knowledge_from_db()
    ids_added, results = await sync_knowledge(latest_entries, "通用知识")

    log.info("--- 通用知识同步完成 ---")
    log.info(f"处理摘要:")
    log.info(f"  - 删除了 {len(old_ids)} 个旧文本块。")
    log.info(f"  - 新增了 {len(ids_added)} 个新文本块。")


async def main():
    """主函数，解析参数并根据模式执行相应的同步任务。"""
    parser = argparse.ArgumentParser(description="向量数据库索引同步脚本。")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["all", "member", "general"],
        required=True,
        help="同步模式: 'all' (完全重建), 'member' (仅同步社区成员), 'general' (仅同步通用知识)。",
    )
    args = parser.parse_args()

    if not gemini_service.is_available() or not vector_db_service.is_available():
        log.error("一个或多个核心服务不可用，脚本终止。")
        return

    if args.mode == "all":
        await run_sync_all()
    elif args.mode == "member":
        await run_sync_members()
    elif args.mode == "general":
        await run_sync_general()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("脚本被用户中断。")
    except Exception as e:
        log.error(f"脚本执行期间发生未捕获的错误: {e}", exc_info=True)
