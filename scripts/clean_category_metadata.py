# -*- coding: utf-8 -*-

import logging
import re
import sys
import argparse
import asyncio
import os
from pathlib import Path

import discord
from dotenv import load_dotenv
from tqdm.asyncio import tqdm_asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

# 将src目录添加到Python路径中，以便可以导入项目模块
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)
from src.chat.services.regex_service import regex_service

# 配置日志记录
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s",
    stream=sys.stdout,
)

log = logging.getLogger(__name__)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def backfill_timestamps():
    """
    遍历数据库中的所有记录，
    将 created_at 转换为北京时间，并填充 created_timestamp。
    """
    log.info("--- 开始执行时间戳回填和时区校准任务 ---")
    if not forum_vector_db_service.is_available():
        log.error("论坛向量数据库服务不可用。")
        return

    try:
        log.info("正在从数据库中拉取所有记录的元数据...")
        results = forum_vector_db_service.get(include=["metadatas"])
        ids, metadatas = results.get("ids"), results.get("metadatas")

        if not ids or not metadatas:
            log.warning("数据库为空，无需处理。")
            return

        log.info(f"成功拉取 {len(ids)} 条记录。开始检查和转换时间戳...")
        ids_to_update = []
        metadatas_to_update = []

        for doc_id, metadata in zip(ids, metadatas):
            created_at_str = metadata.get("created_at")
            if not created_at_str:
                log.warning(f"文档 {doc_id} 缺少 'created_at' 字段，跳过。")
                continue

            try:
                # fromisoformat 可以处理带时区信息的 ISO 字符串
                utc_dt = datetime.fromisoformat(created_at_str)
                beijing_dt = utc_dt.astimezone(BEIJING_TZ)

                new_timestamp = beijing_dt.timestamp()
                new_iso_str = beijing_dt.isoformat()

                # 检查是否需要更新
                # 1. created_timestamp 不存在
                # 2. created_timestamp 存在但值不正确
                # 3. created_at 字符串不是北京时区格式
                if (
                    metadata.get("created_timestamp") != new_timestamp
                    or metadata.get("created_at") != new_iso_str
                ):
                    updated_metadata = metadata.copy()
                    updated_metadata["created_at"] = new_iso_str
                    updated_metadata["created_timestamp"] = new_timestamp
                    ids_to_update.append(doc_id)
                    metadatas_to_update.append(updated_metadata)

            except (ValueError, TypeError) as e:
                log.error(f"处理文档 {doc_id} 的时间戳 '{created_at_str}' 时出错: {e}")

        if not ids_to_update:
            log.info("所有记录的时间戳都已是最新且正确的北京时间，无需更新。")
            return

        log.info(
            f"共发现 {len(ids_to_update)} 条记录需要更新时间戳。正在分批写回数据库..."
        )

        batch_size = 1000
        for i in range(0, len(ids_to_update), batch_size):
            batch_ids = ids_to_update[i : i + batch_size]
            batch_metadatas = metadatas_to_update[i : i + batch_size]
            log.info(
                f"正在处理批次 {i // batch_size + 1}，包含 {len(batch_ids)} 条记录..."
            )
            forum_vector_db_service.update(ids=batch_ids, metadatas=batch_metadatas)

        log.info("所有批次更新成功！时间戳回填和时区校准完成。")

    except Exception as e:
        log.error(f"在执行时间戳回填脚本时发生严重错误: {e}", exc_info=True)


def show_unique_category_names():
    """显示数据库中所有不重复的 category_name 元数据。"""
    log.info("--- 开始执行显示不重复频道名称任务 ---")
    if not forum_vector_db_service.is_available():
        log.error("论坛向量数据库服务不可用。")
        return

    try:
        results = forum_vector_db_service.get(include=["metadatas"])
        metadatas = results.get("metadatas")

        if not metadatas:
            log.warning("数据库中没有找到任何元数据。")
            return

        unique_names = set()
        for metadata in metadatas:
            category_name = metadata.get("category_name")
            if category_name:
                unique_names.add(category_name)

        if not unique_names:
            log.info("数据库中没有找到任何 'category_name' 元数据。")
            return

        log.info(f"发现 {len(unique_names)} 个不重复的频道名称:")
        # 为了更好的可读性，排序后输出
        for name in sorted(list(unique_names)):
            print(f"- {name}")

    except Exception as e:
        log.error(f"在执行显示频道名称脚本时发生严重错误: {e}", exc_info=True)

    log.info("--- 显示不重复频道名称任务完成 ---")


async def fix_author_names(client):
    """修复数据库中作者姓名为'未知作者'的记录。"""
    log.info("--- 开始执行作者元数据修复任务 ---")

    if not forum_vector_db_service.is_available():
        log.error("论坛向量数据库服务不可用。")
        return

    # 1. 从数据库中找出所有 author_id 为 0 的记录
    log.info("正在从数据库中查找 author_id 为 0 的记录...")
    try:
        results = forum_vector_db_service.get(
            where={"author_id": 0}, include=["metadatas"]
        )
        ids_to_fix = results.get("ids", [])
        metadatas_to_fix = results.get("metadatas", [])
    except Exception as e:
        log.error(f"从数据库获取待修复作者信息时出错: {e}", exc_info=True)
        return

    if not ids_to_fix:
        log.info("数据库中没有找到 author_id 为 0 的记录，无需修复。")
        return

    log.info(f"发现 {len(ids_to_fix)} 条记录需要修复作者信息。")

    # 2. 遍历记录并尝试修复
    ids_to_update = []
    metadatas_to_update = []
    fixed_count = 0
    guild_cache = {}

    for doc_id, metadata in tqdm_asyncio(
        zip(ids_to_fix, metadatas_to_fix),
        total=len(ids_to_fix),
        desc="修复作者昵称",
    ):
        guild_id = metadata.get("guild_id")
        thread_id = metadata.get("thread_id")

        if not guild_id or not thread_id:
            log.warning(f"文档 {doc_id} 缺少 guild_id 或 thread_id，跳过。")
            continue

        try:
            # 缓存Guild对象以减少API调用
            guild = guild_cache.get(guild_id)
            if not guild:
                guild = client.get_guild(guild_id) or await client.fetch_guild(guild_id)
                if guild:
                    guild_cache[guild_id] = guild
                else:
                    log.warning(f"无法找到 Guild ID: {guild_id}，跳过相关记录。")
                    continue

            # 通过 thread_id 直接获取 thread 对象
            # 线程本身也是一种频道，所以可以用 fetch_channel
            thread = await client.fetch_channel(thread_id)
            if not thread or not hasattr(thread, "owner_id"):
                log.warning(
                    f"无法通过 ID {thread_id} 找到对应的帖子，或该对象不是帖子。"
                )
                continue

            correct_author_id = thread.owner_id
            if not correct_author_id:
                log.warning(f"帖子 {thread_id} 没有 owner_id，跳过。")
                continue

            member = guild.get_member(correct_author_id) or await guild.fetch_member(
                correct_author_id
            )

            if member:
                correct_author_name = member.display_name
                # 检查是否需要更新
                if (
                    metadata.get("author_name") != correct_author_name
                    or metadata.get("author_id") != correct_author_id
                ):
                    log.info(
                        f"修复帖子 '{metadata.get('thread_name')}' (ID: {thread_id}): "
                        f"作者 '{metadata.get('author_name')}' (ID: {metadata.get('author_id')}) -> "
                        f"'{correct_author_name}' (ID: {correct_author_id})"
                    )
                    updated_metadata = metadata.copy()
                    updated_metadata["author_name"] = correct_author_name
                    updated_metadata["author_id"] = correct_author_id
                    ids_to_update.append(doc_id)
                    metadatas_to_update.append(updated_metadata)
                    fixed_count += 1
            else:
                log.warning(
                    f"无法在服务器 {guild_id} 中找到成员 ID: {correct_author_id}。"
                )

        except discord.NotFound:
            log.warning(
                f"无法找到帖子 ID: {thread_id} 或成员。可能帖子已被删除或成员已离开服务器。"
            )
        except discord.Forbidden:
            log.error(
                f"机器人权限不足，无法获取帖子 {thread_id} 或其作者信息。请检查频道权限。"
            )
        except Exception as e:
            log.error(
                f"处理文档 {doc_id} (Thread: {thread_id}) 时发生未知错误: {e}",
                exc_info=True,
            )

    # 3. 批量更新数据库
    if ids_to_update:
        log.info(f"准备将 {fixed_count} 条已更正的作者信息写回数据库...")
        forum_vector_db_service.update(ids=ids_to_update, metadatas=metadatas_to_update)
        log.info("作者信息批量更新成功！")
    else:
        log.info("没有发现可以成功修复的作者信息。")

    log.info("--- 作者元数据修复任务完成 ---")


def clean_category_names():
    """执行频道名称元数据的原地清洗。"""
    log.info("--- 开始执行频道名称元数据清洗任务 ---")

    if not forum_vector_db_service.is_available():
        log.error("论坛向量数据库服务不可用。")
        return

    try:
        results = forum_vector_db_service.get(include=["metadatas"])
        ids, metadatas = results.get("ids"), results.get("metadatas")

        if not ids or not metadatas or len(ids) != len(metadatas):
            log.warning("获取到的数据不一致或为空，脚本终止。")
            return

        log.info(f"成功拉取 {len(ids)} 条记录。开始遍历和清洗...")
        ids_to_update, metadatas_to_update = [], []

        for doc_id, metadata in zip(ids, metadatas):
            original_name = metadata.get("category_name")
            if original_name:
                # 使用集中的 regex_service 进行清洗
                cleaned_name = regex_service.clean_channel_name(original_name)
                if original_name != cleaned_name:
                    log.info(
                        f"清洗频道名称: '{original_name}' -> '{cleaned_name}' (ID: {doc_id})"
                    )
                    updated_metadata = metadata.copy()
                    updated_metadata["category_name"] = cleaned_name
                    ids_to_update.append(doc_id)
                    metadatas_to_update.append(updated_metadata)

        if not ids_to_update:
            log.info("所有频道名称元数据都已经是干净的，无需更新。")
            return

        log.info(f"共发现 {len(ids_to_update)} 条记录需要更新。正在分批写回数据库...")

        batch_size = 1000  # 设置一个安全的批处理大小
        for i in range(0, len(ids_to_update), batch_size):
            batch_ids = ids_to_update[i : i + batch_size]
            batch_metadatas = metadatas_to_update[i : i + batch_size]

            log.info(
                f"正在处理批次 {i // batch_size + 1}，包含 {len(batch_ids)} 条记录..."
            )
            forum_vector_db_service.update(ids=batch_ids, metadatas=batch_metadatas)

        log.info("所有批次更新成功！元数据清洗完成。")

    except Exception as e:
        log.error(f"在执行清洗脚本时发生严重错误: {e}", exc_info=True)


async def main():
    parser = argparse.ArgumentParser(description="论坛元数据维护工具。")
    parser.add_argument(
        "--show-names", action="store_true", help="显示数据库中所有不重复的频道名称。"
    )
    parser.add_argument(
        "--clean-names", action="store_true", help="清洗频道名称中的无效字符。"
    )
    parser.add_argument(
        "--fix-authors", action="store_true", help="修复作者姓名为'未知作者'的记录。"
    )
    parser.add_argument(
        "--backfill-timestamps",
        action="store_true",
        help="将所有记录的UTC时间戳转换为北京时间并填充新字段。",
    )
    args = parser.parse_args()

    if not any(
        [args.show_names, args.clean_names, args.fix_authors, args.backfill_timestamps]
    ):
        log.info(
            "请至少选择一个操作: --show-names, --clean-names, --fix-authors, 或 --backfill-timestamps"
        )
        return

    if args.show_names:
        show_unique_category_names()

    if args.clean_names:
        clean_category_names()

    if args.backfill_timestamps:
        backfill_timestamps()

    if args.fix_authors:
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            log.info(f"机器人已作为 {client.user} 登录，准备修复作者信息。")
            await fix_author_names(client)
            await client.close()

        token = os.getenv("DISCORD_TOKEN")
        if not token:
            log.critical("错误: DISCORD_TOKEN 未在 .env 文件中设置！")
            return
        await client.start(token)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
