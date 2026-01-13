import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, func

# --- Path and Module Configuration ---
import os
import sys
import argparse
from pathlib import Path

current_script_path = os.path.abspath(__file__)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Project Imports ---
from src.database.database import AsyncSessionLocal
from src.database.models import (
    GeneralKnowledgeDocument,
    GeneralKnowledgeChunk,
    CommunityMemberProfile,
    CommunityMemberChunk,
)
from src.chat.services.gemini_service import gemini_service

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- Concurrency Configuration ---
CONCURRENCY_LIMIT = 5
CHUNK_SIZE = 500


def chunk_text(text: str) -> list[str]:
    """简单的文本分块函数。"""
    if not text:
        return []
    return [text[i : i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]


async def process_documents(
    db_session: AsyncSession, documents, doc_type: str, chunk_model, doc_id_field: str
):
    """通用处理函数，用于处理文档并生成带向量的 chunks。"""
    log.info(f"--- 开始处理 {len(documents)} 个 {doc_type} ---")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = []
    all_chunks_to_create = []

    async def get_embedding_with_semaphore(text: str, title: str):
        async with semaphore:
            try:
                return await gemini_service.generate_embedding(
                    text=text, title=title, task_type="retrieval_document"
                )
            except Exception as e:
                log.error(
                    f"为标题 '{title}' 的文本块生成向量时出错: {e}", exc_info=True
                )
                return None

    for doc in documents:
        full_text = doc.full_text or ""
        title = doc.title or "无标题"
        text_chunks = chunk_text(str(full_text))

        for i, chunk_content in enumerate(text_chunks):
            task = asyncio.create_task(
                get_embedding_with_semaphore(chunk_content, title)
            )
            tasks.append(
                {"doc": doc, "index": i, "content": chunk_content, "task": task}
            )

    log.info(f"已为 {doc_type} 创建 {len(tasks)} 个 embedding 任务，开始并发处理...")

    embedding_results = await asyncio.gather(
        *[t["task"] for t in tasks], return_exceptions=True
    )

    log.info("Embedding 任务完成，开始整理结果...")

    successful_chunks = 0
    for i, result in enumerate(embedding_results):
        task_info = tasks[i]
        doc = task_info["doc"]

        if isinstance(result, Exception):
            log.error(
                f"为 {doc_type} ID {doc.id} 的 chunk {task_info['index']} 生成向量失败: {result}"
            )
        elif result:
            chunk_data = {
                doc_id_field: doc.id,
                "chunk_text": task_info["content"],
                "chunk_index": task_info["index"],
                "embedding": result,
            }
            new_chunk = chunk_model(**chunk_data)
            all_chunks_to_create.append(new_chunk)
            successful_chunks += 1
        else:
            log.warning(
                f"为 {doc_type} ID {doc.id} 的 chunk {task_info['index']} 未能生成向量，已跳过。"
            )

    log.info(
        f"成功为 {len(documents)} 个 {doc_type} 创建了 {successful_chunks} 个 chunks。"
    )

    return all_chunks_to_create


async def main():
    """主执行函数。"""
    parser = argparse.ArgumentParser(
        description="重新对数据库中的知识和成员档案进行分块和向量化。"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式，只处理每个类别的5个随机样本，并且不清空现有数据。",
    )
    args = parser.parse_args()

    if args.debug:
        log.info("--- [调试模式] 脚本启动 ---")
    else:
        log.info("--- [全量模式] 脚本启动 ---")

    if not gemini_service.is_available():
        log.error("Gemini 服务不可用。请检查 API 密钥。正在中止。")
        return

    async with AsyncSessionLocal() as session:
        if not args.debug:
            log.info("1. 正在清理旧的 chunk 数据...")
            await session.execute(
                text(
                    "TRUNCATE TABLE general_knowledge.knowledge_chunks RESTART IDENTITY;"
                )
            )
            await session.execute(
                text("TRUNCATE TABLE community.member_chunks RESTART IDENTITY;")
            )
            await session.commit()
            log.info("   旧 chunk 数据清理完毕。")

        # 2. 获取文档
        log.info("2. 正在获取文档...")
        if args.debug:
            log.info("   [调试模式] 随机选择 5 个通用知识文档和 5 个社区成员档案。")

            # 使用 func.random() 进行数据库级别的随机排序
            gk_stmt = select(GeneralKnowledgeDocument).order_by(func.random()).limit(5)
            gk_documents = (await session.execute(gk_stmt)).scalars().all()

            cm_stmt = select(CommunityMemberProfile).order_by(func.random()).limit(5)
            cm_profiles = (await session.execute(cm_stmt)).scalars().all()

            log.info(f"   - 选择了 {len(gk_documents)} 个通用知识文档。")
            log.info(f"   - 选择了 {len(cm_profiles)} 个社区成员档案。")
        else:
            log.info("   [全量模式] 获取所有通用知识文档和社区成员档案。")
            gk_docs_result = await session.execute(select(GeneralKnowledgeDocument))
            gk_documents = gk_docs_result.scalars().all()
            cm_profiles_result = await session.execute(select(CommunityMemberProfile))
            cm_profiles = cm_profiles_result.scalars().all()

        all_new_chunks = []

        # 3. 处理通用知识
        if gk_documents:
            log.info(f"3. 开始处理 {len(gk_documents)} 个通用知识文档...")
            gk_chunks = await process_documents(
                session,
                gk_documents,
                "通用知识文档",
                GeneralKnowledgeChunk,
                "document_id",
            )
            all_new_chunks.extend(gk_chunks)
        else:
            log.info("3. 未找到通用知识文档。")

        # 4. 处理社区成员档案
        if cm_profiles:
            log.info(f"4. 开始处理 {len(cm_profiles)} 个社区成员档案...")
            cm_chunks = await process_documents(
                session, cm_profiles, "社区成员档案", CommunityMemberChunk, "profile_id"
            )
            all_new_chunks.extend(cm_chunks)
        else:
            log.info("4. 未找到社区成员档案。")

        # 5. 批量插入所有新 chunks
        if all_new_chunks:
            log.info(f"5. 准备将总共 {len(all_new_chunks)} 个新 chunks 写入数据库...")
            if args.debug:
                log.info(
                    "   [调试模式] 数据将直接添加，旧数据不会被删除。注意：如果重复运行，可能会产生重复的chunks。"
                )
            session.add_all(all_new_chunks)
            await session.commit()
            log.info("   写入成功！")
        else:
            log.warning("5. 没有生成任何新的 chunks 可供写入。")

    log.info(f"--- 任务完成 ({'调试模式' if args.debug else '全量模式'}) ---")


if __name__ == "__main__":
    asyncio.run(main())
