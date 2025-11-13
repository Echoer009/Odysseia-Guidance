# -*- coding: utf-8 -*-

import logging
import discord
from discord.ext import commands, tasks
import aiosqlite
import os
import datetime
import asyncio

from src.chat.config import chat_config
from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)
from src import config as main_config

log = logging.getLogger(__name__)

DB_PATH = os.path.join(main_config.DATA_DIR, "forum_sync_status.db")


class ForumSyncCog(commands.Cog):
    """
    包含后台任务，用于轮询和监听论坛频道，以进行语义索引。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = DB_PATH
        self.poll_threads.start()

    async def cog_load(self):
        await self.initialize_db()

    async def initialize_db(self):
        """初始化数据库，创建用于存储已处理帖子ID的表。"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_threads (
                    thread_id INTEGER PRIMARY KEY
                )
                """
            )
            await db.commit()

    async def _process_thread_concurrently(
        self, thread: discord.Thread, semaphore: asyncio.Semaphore, db_conn
    ):
        """并发处理单个帖子的辅助函数"""
        async with semaphore:
            try:
                # 检查帖子是否已被处理
                cursor = await db_conn.execute(
                    "SELECT 1 FROM processed_threads WHERE thread_id = ?", (thread.id,)
                )
                if await cursor.fetchone():
                    return  # 跳过

                log.info(f"正在处理帖子: {thread.name} ({thread.id})")
                await forum_search_service.process_thread(thread)

                # 标记为已处理
                await db_conn.execute(
                    "INSERT INTO processed_threads (thread_id) VALUES (?)", (thread.id,)
                )
                await db_conn.commit()
            except Exception as e:
                log.error(
                    f"并发处理帖子 {thread.name} ({thread.id}) 时出错: {e}",
                    exc_info=True,
                )

    # 每天在 UTC 时间 20:00（即北京时间凌晨 4:00）执行轮询任务
    @tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=datetime.timezone.utc))
    async def poll_threads(self):
        """
        每天运行一次，轮询指定论坛频道的最新帖子，并以10个并发进行处理。
        """
        log.info("开始每日论坛帖子轮询任务...")
        if not forum_search_service.is_ready():
            log.warning("论坛搜索服务未就绪，跳过此次轮询。")
            return

        channel_ids = chat_config.FORUM_SEARCH_CHANNEL_IDS
        if not channel_ids:
            log.info("没有配置要轮询的论坛频道ID，任务结束。")
            return

        semaphore = asyncio.Semaphore(chat_config.FORUM_POLL_CONCURRENCY)  # 设置并发数

        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if not isinstance(channel, discord.ForumChannel):
                continue

            log.info(f"正在轮询论坛频道: {channel.name} ({channel_id})")
            try:
                # 1. 获取所有已处理的帖子ID
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute("SELECT thread_id FROM processed_threads")
                    processed_ids = {row[0] for row in await cursor.fetchall()}

                # 2. 获取频道中所有帖子，并筛选出未处理的
                log.info(f"正在从频道 {channel.name} 获取帖子列表...")
                all_threads_in_channel = []
                all_threads_in_channel.extend(channel.threads)
                # 限制一个较大的数量以防无限加载和API滥用
                async for t in channel.archived_threads(limit=5000):
                    all_threads_in_channel.append(t)

                unprocessed_threads = [
                    t for t in all_threads_in_channel if t.id not in processed_ids
                ]

                # 3. 按时间倒序排列，并获取本轮要处理的批次
                sorted_unprocessed = sorted(
                    unprocessed_threads, key=lambda t: t.created_at, reverse=True
                )
                threads_to_process = sorted_unprocessed[
                    : chat_config.FORUM_POLL_THREAD_LIMIT
                ]

                if not threads_to_process:
                    log.info(f"频道 {channel.name} 中没有找到新的未处理帖子。")
                    continue

                # 4. 并发处理这一批次的帖子
                log.info(
                    f"找到 {len(threads_to_process)} 个未处理帖子，准备并发处理..."
                )
                async with aiosqlite.connect(self.db_path) as db:
                    tasks = [
                        self._process_thread_concurrently(thread, semaphore, db)
                        for thread in threads_to_process
                    ]
                    await asyncio.gather(*tasks)

            except Exception as e:
                log.error(f"轮询论坛频道 {channel_id} 时出错: {e}", exc_info=True)

        log.info("每日论坛帖子轮询任务完成。")

    @poll_threads.before_loop
    async def before_poll_threads(self):
        """在任务开始前等待机器人准备就绪。"""
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """
        监听新帖子的创建事件。
        """
        if thread.parent_id not in chat_config.FORUM_SEARCH_CHANNEL_IDS:
            return

        log.info(f"检测到新帖子，准备处理: {thread.name} ({thread.id})")
        await forum_search_service.process_thread(thread)
        # 将新帖子ID添加到数据库，以防轮询任务重复处理
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO processed_threads (thread_id) VALUES (?)",
                (thread.id,),
            )
            await db.commit()


async def setup(bot: commands.Bot):
    """将此Cog添加到机器人中。"""
    await bot.add_cog(ForumSyncCog(bot))
