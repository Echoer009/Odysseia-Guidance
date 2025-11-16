import os
import sys
import sqlite3
import uuid
import json
import asyncio
import logging
import re
from pathlib import Path
from dotenv import load_dotenv

# --- 配置项目根路径 ---
current_script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(current_script_path)
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)
# --- 路径配置结束 ---

# --- 环境变量加载 ---
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
    print(".env 文件已加载。")
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
CONCURRENCY_LIMIT = 16

# --- 路径定义 ---
RAG_INPUT_DIR = Path("knowledge_data_rag_ready")
DB_PATH = Path("data/world_book.sqlite3")
TARGET_CATEGORY_NAME = "通用知识"


def create_text_chunks(text: str, max_chars: int = 1000) -> list[str]:
    """根据句子边界将长文本分割成更小的块。"""
    if not text or not text.strip():
        return []
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[。？！.!?\n])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return []
    final_chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current_chunk:
                final_chunks.append(current_chunk)
            final_chunks.append(sentence)
            current_chunk = ""
            continue
        if len(current_chunk) + len(sentence) + 1 > max_chars:
            final_chunks.append(current_chunk)
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    if current_chunk:
        final_chunks.append(current_chunk)
    return final_chunks


def get_or_create_category_id(cursor, category_name):
    """获取或创建类别ID"""
    cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
    result = cursor.fetchone()
    if result:
        return result
    else:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        return cursor.lastrowid


async def process_and_vectorize_rag_files():
    """处理RAG文件，将其导入SQLite数据库，并进行向量化。"""
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        log.info(f"创建数据库目录: {DB_PATH.parent}")

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    entries_to_vectorize = []

    try:
        category_id = get_or_create_category_id(cursor, TARGET_CATEGORY_NAME)
        log.info(f"获取到类别 '{TARGET_CATEGORY_NAME}' 的ID: {category_id}")

        for filename in os.listdir(RAG_INPUT_DIR):
            if filename.endswith(".txt"):
                file_path = os.path.join(RAG_INPUT_DIR, filename)
                log.info(f"\n正在处理文件: {file_path}")

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                chunks = content.split("---RAG-CHUNK---")

                for i, chunk in enumerate(chunks):
                    chunk = chunk.strip()
                    if not chunk:
                        continue

                    lines = chunk.split("\n")
                    title = lines[0].replace("### **", "").replace("**", "").strip()
                    body = "\n".join(lines[1:]).strip()

                    cursor.execute(
                        "SELECT id FROM general_knowledge WHERE title = ?", (title,)
                    )
                    existing_entry = cursor.fetchone()

                    if existing_entry:
                        log.warning(f"  - 块 '{title}' 在SQLite中已存在，跳过插入。")
                        entry_id = existing_entry
                    else:
                        entry_id = str(uuid.uuid4())
                        content_json = json.dumps({"text": body})
                        cursor.execute(
                            """
                            INSERT INTO general_knowledge (id, title, name, content_json, category_id, status)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (
                                entry_id,
                                title,
                                title,
                                content_json,
                                category_id,
                                "approved",
                            ),
                        )
                        log.info(f"  - 块 '{title}' 已成功插入SQLite。")

                    entries_to_vectorize.append(
                        {
                            "id": entry_id,
                            "title": title,
                            "body": body,
                            "category": TARGET_CATEGORY_NAME,
                        }
                    )

        conn.commit()
        log.info("\n所有文件处理完毕，SQLite数据库已更新。")

    except sqlite3.Error as e:
        log.error(f"数据库操作失败: {e}")
        conn.rollback()
    finally:
        conn.close()

    # --- 开始向量化 ---
    if not entries_to_vectorize:
        log.warning("没有找到需要向量化的新条目。")
        return

    log.info(f"\n--- 开始对 {len(entries_to_vectorize)} 个条目进行向量化 ---")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = []
    chunk_details = []

    for entry in entries_to_vectorize:
        original_id = f"db_{entry['id']}"
        entry_title = entry["title"]
        document_text = (
            f"类别: {entry['category']}\n名称: {entry_title}\n描述:\n{entry['body']}"
        )
        chunks = create_text_chunks(document_text, max_chars=1000)

        if not chunks:
            log.warning(f"条目 id='{original_id}' 的内容无法分块，跳过。")
            continue

        for chunk_index, chunk_content in enumerate(chunks):
            chunk_id = f"{original_id}:{chunk_index}"

            async def generate_with_semaphore(text, title):
                async with semaphore:
                    return await gemini_service.generate_embedding(
                        text=text, title=title, task_type="retrieval_document"
                    )

            task = asyncio.create_task(
                generate_with_semaphore(chunk_content, entry_title)
            )
            tasks.append(task)
            chunk_details.append(
                {
                    "id": chunk_id,
                    "document": chunk_content,
                    "metadata": {"category": entry["category"], "source": "database"},
                }
            )

    log.info(f"任务准备完成，总共创建了 {len(tasks)} 个嵌入任务。开始并发处理...")
    embedding_results = await asyncio.gather(*tasks, return_exceptions=True)
    log.info("所有嵌入任务已执行完毕，开始处理结果...")

    ids_to_add, docs_to_add, embeds_to_add, metadatas_to_add = [], [], [], []
    for i, result in enumerate(embedding_results):
        detail = chunk_details[i]
        if isinstance(result, Exception):
            log.error(f"块 {detail['id']} 的嵌入任务失败: {result}")
        elif result:
            ids_to_add.append(detail["id"])
            docs_to_add.append(detail["document"])
            embeds_to_add.append(result)
            metadatas_to_add.append(detail["metadata"])
        else:
            log.warning(f"块 {detail['id']} 未能生成嵌入向量，已跳过。")

    if ids_to_add:
        log.info(f"准备将 {len(ids_to_add)} 个文档块批量写入向量数据库...")
        vector_db_service.add_documents(
            ids=ids_to_add,
            documents=docs_to_add,
            embeddings=embeds_to_add,
            metadatas=metadatas_to_add,
        )
    else:
        log.warning("没有成功生成任何嵌入向量，无需更新向量数据库。")


async def main():
    if not gemini_service.is_available() or not vector_db_service.is_available():
        log.error("一个或多个核心服务不可用，脚本终止。")
        return
    await process_and_vectorize_rag_files()


if __name__ == "__main__":
    log.info("开始将RAG知识块导入World Book数据库并进行向量化...")
    try:
        asyncio.run(main())
        log.info("脚本执行完毕。")
    except KeyboardInterrupt:
        log.info("脚本被用户中断。")
    except Exception as e:
        log.error(f"脚本执行期间发生未捕获的错误: {e}", exc_info=True)
