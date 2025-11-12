# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import sys
import shutil
import discord

# 将项目根目录添加到系统路径中，以便导入 src 中的模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import config as main_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)

# 定义数据库路径
DB_DIR = os.path.join(main_config.DATA_DIR, "forum_chroma_db")
DB_STATUS_FILE = os.path.join(main_config.DATA_DIR, "forum_sync_status.db")


def clear_existing_database():
    """清空现有的向量数据库和同步状态文件。"""
    log.info("开始清空旧的论坛索引数据库...")
    try:
        if os.path.exists(DB_DIR):
            shutil.rmtree(DB_DIR)
            log.info(f"成功删除目录: {DB_DIR}")
        else:
            log.info("向量数据库目录不存在，无需删除。")

        if os.path.exists(DB_STATUS_FILE):
            os.remove(DB_STATUS_FILE)
            log.info(f"成功删除文件: {DB_STATUS_FILE}")
        else:
            log.info("同步状态数据库文件不存在，无需删除。")
        log.info("数据库清理完成。")
        return True
    except Exception as e:
        log.error(f"清理数据库时发生错误: {e}", exc_info=True)
        return False


async def reindex_forums():
    """连接到Discord并执行重新索引任务。"""
    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True  # 需要此权限来读取帖子内容
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        log.info(f"机器人已作为 {client.user} 登录，准备开始索引。")

        # 在这里导入服务和配置，确保它们在数据库清理和 .env 加载之后才被初始化
        from src.chat.config import chat_config
        from src.chat.features.forum_search.services.forum_search_service import (
            forum_search_service,
        )

        channel_ids = chat_config.FORUM_SEARCH_CHANNEL_IDS
        if not channel_ids:
            log.warning("没有在配置中找到任何论坛频道ID。")
            await client.close()
            return

        log.info(f"将要处理的频道ID: {channel_ids}")

        for channel_id in channel_ids:
            channel = client.get_channel(channel_id)
            if not isinstance(channel, discord.ForumChannel):
                log.warning(f"ID {channel_id} 不是一个有效的论坛频道，已跳过。")
                continue

            log.info(f"--- 开始处理频道: {channel.name} ({channel.id}) ---")
            try:
                # 获取最新的50个帖子（包括活跃和已归档的）
                active_threads = channel.threads
                archived_threads_iterator = channel.archived_threads(
                    limit=chat_config.FORUM_POLL_THREAD_LIMIT
                )
                archived_threads = [t async for t in archived_threads_iterator]

                all_threads_dict = {t.id: t for t in active_threads}
                all_threads_dict.update({t.id: t for t in archived_threads})

                sorted_threads = sorted(
                    all_threads_dict.values(),
                    key=lambda t: t.created_at,
                    reverse=True,
                )
                threads_to_process = sorted_threads[
                    : chat_config.FORUM_POLL_THREAD_LIMIT
                ]
                log.info(f"找到 {len(threads_to_process)} 个帖子准备处理。")

                # --- 并发处理 ---
                semaphore = asyncio.Semaphore(chat_config.FORUM_POLL_CONCURRENCY)
                tasks = []

                async def process_with_semaphore(thread):
                    async with semaphore:
                        log.info(f"正在处理帖子: '{thread.name}' ({thread.id})")
                        await forum_search_service.process_thread(thread)

                for thread in threads_to_process:
                    tasks.append(process_with_semaphore(thread))

                await asyncio.gather(*tasks)

            except Exception as e:
                log.error(f"处理频道 {channel.name} 时发生错误: {e}", exc_info=True)

        log.info("所有频道的索引任务已完成。机器人将自动关闭。")
        await client.close()

    try:
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            log.critical("错误: DISCORD_TOKEN 未在 .env 文件中设置！")
            return
        await client.start(token)
    except discord.LoginFailure:
        log.error("机器人令牌无效，请检查您的 .env 文件配置。")
    except Exception as e:
        log.error(f"启动机器人时发生未知错误: {e}", exc_info=True)


async def main():
    if not clear_existing_database():
        log.error("数据库清理失败，索引任务已中止。")
        return

    await reindex_forums()


if __name__ == "__main__":
    from dotenv import load_dotenv

    # 确保 .env 文件已加载
    load_dotenv()
    asyncio.run(main())
