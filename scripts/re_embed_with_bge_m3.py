# -*- coding: utf-8 -*-
"""使用 bge-m3 模型重新生成所有 embedding 的脚本

此脚本用于将所有知识库和论坛帖子的 embedding 从 gemini-embedding-001 (3072维)
迁移到本地的 bge-m3 模型 (1024维)。

运行前请确保：
1. Ollama 服务已启动并运行 bge-m3 模型
2. 数据库迁移脚本已执行 (alembic upgrade head)
3. .env 文件中的数据库配置正确
"""

import asyncio
import logging
import argparse
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, func

# --- Path and Module Configuration ---
import os
import sys
from pathlib import Path

# 设置 Docker 环境下的 Ollama 地址
os.environ.setdefault("OLLAMA_BASE_URL", "http://ollama:11434")
os.environ.setdefault("OLLAMA_MODEL", "bge-m3")

current_script_path = os.path.abspath(__file__)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Project Imports ---
from src.database.database import AsyncSessionLocal
from src.database.models import (
    TutorialDocument,
    KnowledgeChunk,
    GeneralKnowledgeDocument,
    GeneralKnowledgeChunk,
    CommunityMemberProfile,
    CommunityMemberChunk,
)
from src.chat.services.ollama_embedding_service import OllamaEmbeddingService

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- Concurrency Configuration ---
CONCURRENCY_LIMIT = 3  # bge-m3 模型较大，限制并发数避免内存溢出


async def update_tutorial_embeddings(
    ollama_service: OllamaEmbeddingService,
    session: AsyncSession,
    limit: Optional[int] = None,
    offset: int = 0,
) -> int:
    """更新教程文档的 embedding"""
    log.info("开始处理教程文档...")

    # 获取所有 chunk
    query = select(KnowledgeChunk).order_by(KnowledgeChunk.id)
    if limit:
        query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    chunks = result.scalars().all()

    log.info(f"找到 {len(chunks)} 个教程 chunk")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    success_count = 0

    async def update_chunk(chunk: KnowledgeChunk):
        nonlocal success_count
        async with semaphore:
            try:
                embedding = await ollama_service.generate_embedding(
                    text=str(chunk.chunk_text), task_type="retrieval_document"
                )
                if embedding:
                    chunk.embedding = embedding  # type: ignore
                    success_count += 1
                    return True
            except Exception as e:
                log.error(f"处理教程 chunk {chunk.id} 失败: {e}")
            return False

    # 批量更新
    tasks = [update_chunk(chunk) for chunk in chunks]
    await asyncio.gather(*tasks)

    await session.commit()
    log.info(f"教程文档处理完成，成功更新 {success_count}/{len(chunks)} 个 chunk")
    return success_count


async def update_general_knowledge_embeddings(
    ollama_service: OllamaEmbeddingService,
    session: AsyncSession,
    limit: Optional[int] = None,
    offset: int = 0,
) -> int:
    """更新通用知识的 embedding"""
    log.info("开始处理通用知识文档...")

    query = select(GeneralKnowledgeChunk).order_by(GeneralKnowledgeChunk.id)
    if limit:
        query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    chunks = result.scalars().all()

    log.info(f"找到 {len(chunks)} 个通用知识 chunk")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    success_count = 0

    async def update_chunk(chunk: GeneralKnowledgeChunk):
        nonlocal success_count
        async with semaphore:
            try:
                embedding = await ollama_service.generate_embedding(
                    text=str(chunk.chunk_text), task_type="retrieval_document"
                )
                if embedding:
                    chunk.embedding = embedding  # type: ignore
                    success_count += 1
                    return True
            except Exception as e:
                log.error(f"处理通用知识 chunk {chunk.id} 失败: {e}")
            return False

    tasks = [update_chunk(chunk) for chunk in chunks]
    await asyncio.gather(*tasks)

    await session.commit()
    log.info(f"通用知识处理完成，成功更新 {success_count}/{len(chunks)} 个 chunk")
    return success_count


async def update_community_member_embeddings(
    ollama_service: OllamaEmbeddingService,
    session: AsyncSession,
    limit: Optional[int] = None,
    offset: int = 0,
) -> int:
    """更新社区成员档案的 embedding"""
    log.info("开始处理社区成员档案...")

    query = select(CommunityMemberChunk).order_by(CommunityMemberChunk.id)
    if limit:
        query = query.limit(limit).offset(offset)

    result = await session.execute(query)
    chunks = result.scalars().all()

    log.info(f"找到 {len(chunks)} 个社区成员 chunk")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    success_count = 0

    async def update_chunk(chunk: CommunityMemberChunk):
        nonlocal success_count
        async with semaphore:
            try:
                embedding = await ollama_service.generate_embedding(
                    text=str(chunk.chunk_text), task_type="retrieval_document"
                )
                if embedding:
                    chunk.embedding = embedding  # type: ignore
                    success_count += 1
                    return True
            except Exception as e:
                log.error(f"处理社区成员 chunk {chunk.id} 失败: {e}")
            return False

    tasks = [update_chunk(chunk) for chunk in chunks]
    await asyncio.gather(*tasks)

    await session.commit()
    log.info(f"社区成员档案处理完成，成功更新 {success_count}/{len(chunks)} 个 chunk")
    return success_count


async def main():
    """主执行函数"""
    parser = argparse.ArgumentParser(
        description="使用 bge-m3 模型重新生成所有 embedding"
    )
    parser.add_argument(
        "--type",
        choices=["all", "tutorial", "gk", "community"],
        default="all",
        help="指定要处理的数据类型，默认为 all",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="限制处理的数量，用于测试"
    )
    parser.add_argument(
        "--offset", type=int, default=0, help="起始偏移量，用于分批处理"
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        help="Ollama 服务地址",
    )
    args = parser.parse_args()

    log.info("=== bge-m3 Embedding 迁移脚本启动 ===")
    log.info(f"数据类型: {args.type}")
    log.info(f"限制数量: {args.limit if args.limit else '无限制'}")
    log.info(f"起始偏移: {args.offset}")
    log.info(f"Ollama 地址: {args.ollama_url}")

    # 初始化 Ollama 服务
    ollama_service = OllamaEmbeddingService(base_url=args.ollama_url)

    # 检查连接
    if not await ollama_service.check_connection():
        log.error("无法连接到 Ollama 服务，请确保服务已启动")
        return

    log.info("Ollama 服务连接成功")

    total_success = 0

    async with AsyncSessionLocal() as session:
        if args.type in ["all", "tutorial"]:
            total_success += await update_tutorial_embeddings(
                ollama_service, session, args.limit, args.offset
            )

        if args.type in ["all", "gk"]:
            total_success += await update_general_knowledge_embeddings(
                ollama_service, session, args.limit, args.offset
            )

        if args.type in ["all", "community"]:
            total_success += await update_community_member_embeddings(
                ollama_service, session, args.limit, args.offset
            )

    log.info(f"=== 迁移完成，共成功更新 {total_success} 个 embedding ===")


if __name__ == "__main__":
    asyncio.run(main())
