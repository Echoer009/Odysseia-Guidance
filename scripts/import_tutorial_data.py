import os
import sys
import asyncio
import logging
import re
from pathlib import Path
import yaml
import argparse

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.future import select

# --- Path Configuration ---
current_script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(current_script_path)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Project Module Imports ---
from src.database.models import TutorialDocument, KnowledgeChunk
from src.database.database import AsyncSessionLocal
from src.chat.services.gemini_service import gemini_service

# --- Environment Loading ---
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
    print(".env file loaded.")
else:
    print(".env file not found.")

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- Concurrency & Directory Configuration ---
CONCURRENCY_LIMIT = 5
PARENT_DOCS_DIR = Path(project_root) / "tutorial" / "refined_v2"
CHUNKS_DIR = Path(project_root) / "tutorial" / "refined_chunks"


def parse_front_matter(content: str):
    """从文件内容中解析 YAML Front Matter。"""
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1])
                main_content = parts[2].strip()
                return metadata, main_content
            except yaml.YAMLError as e:
                log.error(f"解析 Front Matter 出错: {e}")
    return {}, content


def slugify_for_lookup(text: str) -> str:
    """一个精确匹配 split_md_by_subheadings.py 输出目录名的 slugify 函数。"""
    text = re.sub(r"^\d+(\.\d+)*\s*", "", text)
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5_]", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_")
    return text.lower()


async def process_single_parent_document(
    db_session: AsyncSession,
    parent_file_path: Path,
    existing_doc: TutorialDocument | None = None,
):
    """处理单个父文档及其所有子文档（chunks）。"""
    log.info(f"--- 开始处理父文档: {parent_file_path.name} ---")

    parent_content = parent_file_path.read_text(encoding="utf-8")
    metadata, _ = parse_front_matter(parent_content)

    if not metadata:
        log.warning(f"父文档 {parent_file_path.name} 中缺少 Front Matter，已跳过。")
        return

    parent_title = metadata.get("title", parent_file_path.stem)

    if existing_doc:
        log.info(
            f"正在更新现有文档记录: '{existing_doc.title}' (ID: {existing_doc.id})"
        )
        existing_doc.title = parent_title
        existing_doc.original_content = parent_content
        existing_doc.category = metadata.get("category", "Uncategorized")
        existing_doc.tags = metadata.get("tags", [])
        doc = existing_doc
    else:
        doc = TutorialDocument(
            title=parent_title,
            original_content=parent_content,
            category=metadata.get("category", "Uncategorized"),
            tags=metadata.get("tags", []),
            author="System",
            source_url=str(parent_file_path.relative_to(project_root)),
        )
        db_session.add(doc)

    await db_session.flush()
    log.info(
        f"已{'更新' if existing_doc else '创建'}父文档记录: '{doc.title}' (ID: {doc.id})"
    )

    chunk_subdir_name = slugify_for_lookup(parent_file_path.stem)
    chunk_subdir = CHUNKS_DIR / chunk_subdir_name

    if not chunk_subdir.is_dir():
        log.warning(
            f"未找到 '{parent_file_path.name}' 对应的 chunk 目录: {chunk_subdir}"
        )
        return

    chunk_files = list(chunk_subdir.glob("*.md"))
    log.info(f"在 {chunk_subdir} 中找到 {len(chunk_files)} 个 chunk 文件。")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = []

    async def get_embedding_with_semaphore(text: str, title: str):
        async with semaphore:
            return await gemini_service.generate_embedding(
                text=text, title=title, task_type="retrieval_document"
            )

    chunk_contents = [p.read_text(encoding="utf-8") for p in chunk_files]

    for chunk_text in chunk_contents:
        _, chunk_main_content = parse_front_matter(chunk_text)
        task = asyncio.create_task(
            get_embedding_with_semaphore(chunk_main_content, parent_title)
        )
        tasks.append(task)

    embedding_results = await asyncio.gather(*tasks, return_exceptions=True)

    successful_chunks = 0
    for i, result in enumerate(embedding_results):
        if isinstance(result, Exception):
            log.error(f"Chunk {i + 1}/{len(chunk_files)} 生成 embedding 失败: {result}")
        elif result:
            _, chunk_main_content = parse_front_matter(chunk_contents[i])
            chunk_record = KnowledgeChunk(
                document_id=doc.id,
                chunk_text=chunk_main_content,
                chunk_order=i,
                embedding=result,
            )
            db_session.add(chunk_record)
            successful_chunks += 1
        else:
            log.warning(
                f"Chunk {i + 1}/{len(chunk_files)} 未返回 embedding。正在跳过。"
            )

    log.info(
        f"成功为 '{parent_title}' 导入了 {successful_chunks}/{len(chunk_files)} 个 chunk。"
    )


async def process_selective_update(db_session: AsyncSession, filenames: list[str]):
    """处理指定文件的更新，保留父文档ID。"""
    log.info(f"--- 开始精准替换模式，处理 {len(filenames)} 个文件 ---")
    for filename in filenames:
        parent_file_path = PARENT_DOCS_DIR / filename
        if not parent_file_path.exists():
            log.error(f"文件未找到: {parent_file_path}，已跳过。")
            continue

        source_url_to_find = str(parent_file_path.relative_to(project_root))
        stmt = select(TutorialDocument).where(
            TutorialDocument.source_url == source_url_to_find
        )
        result = await db_session.execute(stmt)
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            log.info(f"找到现有文档 (ID: {existing_doc.id})。正在清理其旧的 chunks...")
            delete_chunks_stmt = KnowledgeChunk.__table__.delete().where(
                KnowledgeChunk.document_id == existing_doc.id
            )
            await db_session.execute(delete_chunks_stmt)
            await db_session.flush()
            log.info(f"文档 ID {existing_doc.id} 的旧 chunks 已被删除。")
        else:
            log.info(f"未找到路径为 '{source_url_to_find}' 的记录，将创建新文档。")

        await process_single_parent_document(
            db_session, parent_file_path, existing_doc=existing_doc
        )
        await db_session.commit()
        log.info(f"'{filename}' 处理完成。")


async def main():
    parser = argparse.ArgumentParser(description="教程数据导入脚本。")
    parser.add_argument(
        "--update",
        nargs="+",
        metavar="FILENAME",
        help="指定一个或多个要精准替换的 .md 文件名。如果使用此选项，将只更新这些文件。",
    )
    args = parser.parse_args()

    if not gemini_service.is_available():
        log.error("Gemini 服务不可用。请检查 API 密钥。正在中止。")
        return

    if not PARENT_DOCS_DIR.is_dir():
        log.error(f"父文档目录未找到: {PARENT_DOCS_DIR}")
        return

    async with AsyncSessionLocal() as session:
        if args.update:
            await process_selective_update(session, args.update)
        else:
            log.info("--- 开始全新数据导入过程 ---")
            log.info("1. 正在清理 'tutorials' schema 中的旧数据...")
            await session.execute(
                text(
                    "TRUNCATE TABLE tutorials.knowledge_chunks, tutorials.tutorial_documents RESTART IDENTITY;"
                )
            )
            log.info("   旧数据清理完毕。")

            parent_doc_files = list(PARENT_DOCS_DIR.glob("*.md"))

            def sort_key(p: Path):
                match = re.search(r"^(\d+)", p.name)
                return int(match.group(1)) if match else float("inf")

            parent_doc_files.sort(key=sort_key)
            log.info(
                f"2. 在 {PARENT_DOCS_DIR} 中找到 {len(parent_doc_files)} 个父文档，并已按数字顺序排序。"
            )

            for parent_file in parent_doc_files:
                await process_single_parent_document(
                    session, parent_file, existing_doc=None
                )
                await session.commit()
            log.info("--- 所有文档处理完毕，数据导入过程结束。---")


if __name__ == "__main__":
    asyncio.run(main())
