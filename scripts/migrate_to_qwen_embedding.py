# -*- coding: utf-8 -*-
"""交互式 Qwen3-Embedding 迁移脚本

此脚本用于将所有知识库和论坛帖子的 embedding 迁移到 Qwen3-Embedding 模型。
脚本会填充新的 qwen_embedding 列，不影响现有的 bge_embedding 列。

运行前请确保：
1. Ollama 服务已启动并运行 qwen3-embedding:0.6b 模型
2. 数据库迁移脚本已执行 (alembic upgrade head)
3. .env 文件中的数据库配置正确

使用方法：
    python scripts/migrate_to_qwen_embedding.py
"""

import asyncio
import logging
import sys
import os
import time
from pathlib import Path
from typing import TypeVar, Type

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, func

# 尝试导入 tqdm，如果不可用则使用简单的进度显示
try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("提示: 安装 tqdm 可以获得更好的进度条体验 (pip install tqdm)")

# --- Path and Module Configuration ---
current_script_path = os.path.abspath(__file__)
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# --- Project Imports ---
from src.database.database import AsyncSessionLocal
from src.database.models import (
    KnowledgeChunk,
    GeneralKnowledgeChunk,
    CommunityMemberChunk,
    ForumThread,
)
from src.chat.services.ollama_embedding_service import OllamaEmbeddingService

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# --- Concurrency Configuration ---
CONCURRENCY_LIMIT = 5  # Qwen3-Embedding-0.6B 模型较小，可以适当增加并发数
BATCH_SIZE = 50  # 批量提交的大小

# 泛型类型变量
T = TypeVar("T")


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════════╗
║                    Qwen3-Embedding-0.6B 迁移脚本                              ║
║                                                                              ║
║  此脚本将为以下数据类型生成 Qwen embedding:                                    ║
║  1. 教程文档 (Tutorial Knowledge Chunks)                                     ║
║  2. 通用知识 (General Knowledge Chunks)                                      ║
║  3. 社区成员档案 (Community Member Chunks)                                   ║
║  4. 论坛帖子 (Forum Threads)                                                 ║
║                                                                              ║
║  新的 qwen_embedding 列将被填充，不影响现有的 bge_embedding 列。               ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def print_separator():
    """打印分隔线"""
    print("-" * 80)


async def check_ollama_connection(ollama_service: OllamaEmbeddingService) -> bool:
    """检查 Ollama 服务连接"""
    print("\n📡 正在检查 Ollama 服务连接...")
    connected = await ollama_service.check_connection()
    if connected:
        print(f"✅ Ollama 服务连接成功！模型: {ollama_service.model}")
        return True
    else:
        print(f"❌ 无法连接到 Ollama 服务: {ollama_service.base_url}")
        print("   请确保 Ollama 服务已启动并运行 qwen3-embedding-0.6b 模型")
        return False


async def get_pending_count(
    session: AsyncSession, model_class: Type[T], column_name: str
) -> int:
    """获取待处理的记录数量（embedding 为空的记录）"""
    count_query = (
        select(func.count())
        .select_from(model_class)
        .where(text(f"{column_name} IS NULL"))
    )
    result = await session.execute(count_query)
    return result.scalar() or 0


async def get_total_count(session: AsyncSession, model_class: Type[T]) -> int:
    """获取总记录数量"""
    count_query = select(func.count()).select_from(model_class)
    result = await session.execute(count_query)
    return result.scalar() or 0


async def show_statistics(session: AsyncSession) -> dict:
    """显示各表的统计信息"""
    print("\n📊 数据库统计信息:")
    print_separator()

    stats = {}

    # 教程文档
    total = await get_total_count(session, KnowledgeChunk)
    pending = await get_pending_count(session, KnowledgeChunk, "qwen_embedding")
    stats["tutorial"] = {"total": total, "pending": pending, "done": total - pending}
    print(
        f"  📚 教程文档 (KnowledgeChunk): 总计 {total}, 待处理 {pending}, 已完成 {total - pending}"
    )

    # 通用知识
    total = await get_total_count(session, GeneralKnowledgeChunk)
    pending = await get_pending_count(session, GeneralKnowledgeChunk, "qwen_embedding")
    stats["gk"] = {"total": total, "pending": pending, "done": total - pending}
    print(
        f"  📖 通用知识 (GeneralKnowledgeChunk): 总计 {total}, 待处理 {pending}, 已完成 {total - pending}"
    )

    # 社区成员
    total = await get_total_count(session, CommunityMemberChunk)
    pending = await get_pending_count(session, CommunityMemberChunk, "qwen_embedding")
    stats["community"] = {"total": total, "pending": pending, "done": total - pending}
    print(
        f"  👥 社区成员 (CommunityMemberChunk): 总计 {total}, 待处理 {pending}, 已完成 {total - pending}"
    )

    # 论坛帖子
    total = await get_total_count(session, ForumThread)
    pending = await get_pending_count(session, ForumThread, "qwen_embedding")
    stats["forum"] = {"total": total, "pending": pending, "done": total - pending}
    print(
        f"  💬 论坛帖子 (ForumThread): 总计 {total}, 待处理 {pending}, 已完成 {total - pending}"
    )

    print_separator()
    return stats


def get_user_choice() -> dict:
    """获取用户的选择"""
    print("\n🔧 请选择要处理的数据类型:")
    print("  1. 全部 (所有数据类型)")
    print("  2. 仅教程文档")
    print("  3. 仅通用知识")
    print("  4. 仅社区成员")
    print("  5. 仅论坛帖子")
    print("  6. 自定义选择")
    print("  0. 退出")
    print()

    while True:
        choice = input("请输入选项 (0-6): ").strip()

        if choice == "0":
            return {"exit": True}
        elif choice == "1":
            return {"tutorial": True, "gk": True, "community": True, "forum": True}
        elif choice == "2":
            return {"tutorial": True}
        elif choice == "3":
            return {"gk": True}
        elif choice == "4":
            return {"community": True}
        elif choice == "5":
            return {"forum": True}
        elif choice == "6":
            return get_custom_choice()
        else:
            print("❌ 无效选项，请重新输入")


def get_custom_choice() -> dict:
    """获取自定义选择"""
    result = {}

    print("\n请选择要处理的数据类型 (y/n):")

    tutorial = input("  处理教程文档? (y/n): ").strip().lower()
    result["tutorial"] = tutorial == "y"

    gk = input("  处理通用知识? (y/n): ").strip().lower()
    result["gk"] = gk == "y"

    community = input("  处理社区成员? (y/n): ").strip().lower()
    result["community"] = community == "y"

    forum = input("  处理论坛帖子? (y/n): ").strip().lower()
    result["forum"] = forum == "y"

    # 询问批次大小
    batch_input = input(f"\n  批次大小 (默认 {BATCH_SIZE}): ").strip()
    if batch_input.isdigit() and int(batch_input) > 0:
        result["batch_size"] = int(batch_input)

    # 询问并发数
    concurrency_input = input(f"  并发数 (默认 {CONCURRENCY_LIMIT}): ").strip()
    if concurrency_input.isdigit() and int(concurrency_input) > 0:
        result["concurrency"] = int(concurrency_input)

    return result


def confirm_proceed(stats: dict, choices: dict) -> bool:
    """确认是否继续执行"""
    total_pending = 0
    for key in ["tutorial", "gk", "community", "forum"]:
        if choices.get(key, False):
            total_pending += stats.get(key, {}).get("pending", 0)

    if total_pending == 0:
        print("\n✅ 所有选中的数据类型都已处理完成，无需迁移。")
        return False

    print(f"\n⚠️  即将处理 {total_pending} 条记录")
    print("   这可能需要一些时间，请耐心等待...")

    confirm = input("\n确认开始迁移? (y/n): ").strip().lower()
    return confirm == "y"


async def migrate_table(
    ollama_service: OllamaEmbeddingService,
    session: AsyncSession,
    model_class: Type[T],
    text_column: str,
    embedding_column: str,
    table_name: str,
    batch_size: int = BATCH_SIZE,
    concurrency: int = CONCURRENCY_LIMIT,
    total_pending: int = 0,
) -> int:
    """
    迁移单个表的 embedding

    Args:
        ollama_service: Ollama embedding 服务
        session: 数据库会话
        model_class: SQLAlchemy 模型类
        text_column: 文本列名
        embedding_column: embedding 列名
        table_name: 表显示名称
        batch_size: 批次大小
        concurrency: 并发数
        total_pending: 待处理总数（用于进度条）

    Returns:
        成功处理的记录数
    """
    print(f"\n🔄 开始处理 {table_name}...")

    # 先重新查询实际的待处理数量，确保准确
    actual_pending = await get_pending_count(session, model_class, embedding_column)
    print(
        f"   待处理记录数: {actual_pending} (初始统计: {total_pending}), "
        f"批次大小: {batch_size}, 并发数: {concurrency}"
    )

    # 使用实际查询到的数量作为进度条总数
    if actual_pending == 0:
        print(f"✅ {table_name} 无待处理记录，跳过")
        return 0

    semaphore = asyncio.Semaphore(concurrency)
    success_count = 0
    error_count = 0
    processed_count = 0
    start_time = time.time()
    batch_times = []  # 记录每批处理时间用于估算剩余时间

    # 创建进度条 - 使用实际待处理数量
    if HAS_TQDM and actual_pending > 0:
        pbar = tqdm(
            total=actual_pending,
            desc="处理进度",
            unit="条",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        )
    else:
        pbar = None

    while True:
        batch_start = time.time()

        # 获取一批待处理的记录
        # 使用 getattr 获取 id 属性，避免类型检查错误
        id_column = getattr(model_class, "id")

        # 使用 SQLAlchemy 列对象而不是 text() 来确保正确的查询
        embedding_col = getattr(model_class, embedding_column)
        query = (
            select(model_class)
            .where(embedding_col.is_(None))
            .order_by(id_column)
            .limit(batch_size)
        )

        result = await session.execute(query)
        records = result.scalars().all()

        if not records:
            break

        batch_success = 0
        processed_ids = []  # 记录本批处理的 ID

        async def process_record(record):
            nonlocal batch_success
            async with semaphore:
                try:
                    # 获取文本内容
                    text_content = getattr(record, text_column)
                    if not text_content:
                        log.warning(f"记录 {record.id} 文本内容为空，跳过")
                        return False

                    # 生成 embedding
                    embedding = await ollama_service.generate_embedding(
                        text=str(text_content), task_type="retrieval_document"
                    )

                    if embedding:
                        setattr(record, embedding_column, embedding)
                        batch_success += 1
                        processed_ids.append(record.id)
                        return True
                    else:
                        log.warning(f"记录 {record.id} 生成 embedding 返回空值")
                        return False
                except Exception as e:
                    log.error(f"处理记录 {record.id} 失败: {e}")
                    return False

        # 并发处理这批记录
        tasks = [process_record(record) for record in records]
        await asyncio.gather(*tasks)

        # 提交这批更改
        await session.commit()

        # 清除 session 缓存，确保下次查询看到最新数据
        session.expire_all()

        success_count += batch_success
        error_count += len(records) - batch_success
        processed_count += len(records)

        # 记录批次处理时间
        batch_time = time.time() - batch_start
        batch_times.append(batch_time)

        # 更新进度条
        if pbar:
            pbar.update(len(records))
        else:
            # 简单进度显示
            elapsed = time.time() - start_time
            rate = processed_count / elapsed if elapsed > 0 else 0
            remaining = (actual_pending - processed_count) / rate if rate > 0 else 0

            # 格式化时间
            def format_time(seconds):
                if seconds < 60:
                    return f"{int(seconds)}秒"
                elif seconds < 3600:
                    return f"{int(seconds / 60)}分{int(seconds % 60)}秒"
                else:
                    return f"{int(seconds / 3600)}小时{int((seconds % 3600) / 60)}分"

            print(
                f"   📝 进度: {processed_count}/{actual_pending} ({100 * processed_count / actual_pending:.1f}%) | "
                f"成功: {success_count}, 失败: {error_count} | "
                f"速度: {rate:.1f} 条/秒 | "
                f"剩余: {format_time(remaining)}"
            )

    if pbar:
        pbar.close()

    elapsed_total = time.time() - start_time
    avg_rate = processed_count / elapsed_total if elapsed_total > 0 else 0

    print(f"✅ {table_name} 处理完成:")
    print(f"   - 成功: {success_count}, 失败: {error_count}")
    print(f"   - 总耗时: {elapsed_total:.1f}秒, 平均速度: {avg_rate:.2f} 条/秒")
    return success_count


async def run_migration(
    choices: dict, ollama_service: OllamaEmbeddingService, stats: dict
):
    """执行迁移"""
    batch_size = choices.get("batch_size", BATCH_SIZE)
    concurrency = choices.get("concurrency", CONCURRENCY_LIMIT)

    print("\n🚀 开始迁移...")
    print(f"   批次大小: {batch_size}")
    print(f"   并发数: {concurrency}")
    print_separator()

    total_success = 0
    total_start_time = time.time()

    async with AsyncSessionLocal() as session:
        if choices.get("tutorial", False):
            pending = stats.get("tutorial", {}).get("pending", 0)
            total_success += await migrate_table(
                ollama_service,
                session,
                KnowledgeChunk,
                "chunk_text",
                "qwen_embedding",
                "教程文档 (KnowledgeChunk)",
                batch_size,
                concurrency,
                total_pending=pending,
            )

        if choices.get("gk", False):
            pending = stats.get("gk", {}).get("pending", 0)
            total_success += await migrate_table(
                ollama_service,
                session,
                GeneralKnowledgeChunk,
                "chunk_text",
                "qwen_embedding",
                "通用知识 (GeneralKnowledgeChunk)",
                batch_size,
                concurrency,
                total_pending=pending,
            )

        if choices.get("community", False):
            pending = stats.get("community", {}).get("pending", 0)
            total_success += await migrate_table(
                ollama_service,
                session,
                CommunityMemberChunk,
                "chunk_text",
                "qwen_embedding",
                "社区成员 (CommunityMemberChunk)",
                batch_size,
                concurrency,
                total_pending=pending,
            )

        if choices.get("forum", False):
            pending = stats.get("forum", {}).get("pending", 0)
            total_success += await migrate_table(
                ollama_service,
                session,
                ForumThread,
                "content",
                "qwen_embedding",
                "论坛帖子 (ForumThread)",
                batch_size,
                concurrency,
                total_pending=pending,
            )

    total_elapsed = time.time() - total_start_time
    print_separator()
    print(f"\n🎉 迁移完成！共成功处理 {total_success} 条记录")
    print(f"   总耗时: {total_elapsed:.1f}秒")


async def main():
    """主函数"""
    print_banner()

    # 获取 Ollama URL
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    print(f"Ollama 服务地址: {ollama_url}")

    # 初始化 Qwen embedding 服务
    qwen_service = OllamaEmbeddingService(base_url=ollama_url, model_type="qwen")

    # 检查连接
    if not await check_ollama_connection(qwen_service):
        sys.exit(1)

    # 显示统计信息
    async with AsyncSessionLocal() as session:
        stats = await show_statistics(session)

    # 获取用户选择
    choices = get_user_choice()

    if choices.get("exit", False):
        print("\n👋 已退出")
        return

    # 确认执行
    if not confirm_proceed(stats, choices):
        print("\n👋 已取消")
        return

    # 执行迁移
    await run_migration(choices, qwen_service, stats)

    # 显示最终统计
    print("\n📊 最终统计:")
    async with AsyncSessionLocal() as session:
        await show_statistics(session)


if __name__ == "__main__":
    asyncio.run(main())
