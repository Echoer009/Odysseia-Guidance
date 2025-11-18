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
        # 用于在内存中缓存回溯进度，避免重复DB查询
        self.backfill_bookmarks = {}
        self.poll_threads.start()

    async def cog_load(self):
        """Cog加载时执行初始化，并从数据库恢复回溯书签。"""
        await self.initialize_db()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")  # 开启 WAL 模式增强稳定性
            cursor = await db.execute(
                "SELECT channel_id, oldest_known_timestamp, is_complete FROM backfill_status"
            )
            rows = await cursor.fetchall()
            for row in rows:
                self.backfill_bookmarks[row[0]] = {
                    "timestamp": row[1],
                    "is_complete": bool(row[2]),
                }
            if self.backfill_bookmarks:
                log.info(
                    f"已从数据库恢复 {len(self.backfill_bookmarks)} 个频道的回溯书签。"
                )

    async def initialize_db(self):
        """初始化数据库，创建所需的数据表。"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            # 表1: 存储已处理的帖子ID，用于避免重复处理
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_threads (
                    thread_id INTEGER PRIMARY KEY
                )
                """
            )
            # 表2: 存储每个频道的回溯进度书签
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS backfill_status (
                    channel_id INTEGER PRIMARY KEY,
                    oldest_known_timestamp TEXT,
                    is_complete INTEGER DEFAULT 0
                )
                """
            )
            await db.commit()

    async def _process_thread_concurrently(
        self, thread: discord.Thread, semaphore: asyncio.Semaphore
    ):
        """并发处理单个帖子的辅助函数"""
        async with semaphore:
            try:
                # 使用 aiosqlite 连接池来处理并发写入
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("PRAGMA journal_mode=WAL")
                    cursor = await db.execute(
                        "SELECT 1 FROM processed_threads WHERE thread_id = ?",
                        (thread.id,),
                    )
                    if await cursor.fetchone():
                        return  # 如果已被实时监听处理过，则跳过

                    log.info(f"正在回溯处理帖子: {thread.name} ({thread.id})")
                    await forum_search_service.process_thread(thread)

                    await db.execute(
                        "INSERT OR IGNORE INTO processed_threads (thread_id) VALUES (?)",
                        (thread.id,),
                    )
                    await db.commit()
            except Exception as e:
                log.error(
                    f"并发处理帖子 {thread.name} ({thread.id}) 时出错: {e}",
                    exc_info=True,
                )

    # 每天在 UTC 时间 20:00（即北京时间凌晨 4:00）执行轮询任务
    @tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=datetime.timezone.utc))
    async def poll_threads(self):
        """
        历史回溯任务：每天运行一次，从每个频道已索引的最旧帖子开始，向更早的帖子回溯处理一批。
        """
        log.info("开始每日论坛历史回溯任务...")
        if not forum_search_service.is_ready():
            log.warning("论坛搜索服务未就绪，跳过此次回溯。")
            return

        channel_ids = chat_config.FORUM_SEARCH_CHANNEL_IDS
        if not channel_ids:
            log.info("没有配置要回溯的论坛频道ID，任务结束。")
            return

        semaphore = asyncio.Semaphore(chat_config.FORUM_POLL_CONCURRENCY)

        for channel_id in channel_ids:
            bookmark = self.backfill_bookmarks.get(channel_id, {})
            if bookmark.get("is_complete"):
                log.info(f"频道 {channel_id} 已完成历史回溯，本次跳过。")
                continue

            channel = self.bot.get_channel(channel_id)
            if not isinstance(channel, discord.ForumChannel):
                log.warning(f"ID {channel_id} 不是有效的论坛频道，已跳过。")
                continue

            log.info(f"--- 开始回溯频道: {channel.name} ({channel_id}) ---")
            try:
                # 1. 确定回溯的起点
                before_timestamp = None
                # 优先使用内存/DB中的书签
                if bookmark.get("timestamp"):
                    before_timestamp = datetime.datetime.fromisoformat(
                        bookmark["timestamp"]
                    )
                else:
                    # 如果没有书签，则实时查询一次向量库作为冷启动的起点
                    log.info(
                        f"频道 {channel_id} 没有找到回溯书签，将从向量库查询初始起点。"
                    )
                    oldest_ts_str = (
                        await forum_search_service.get_oldest_indexed_thread_timestamp(
                            channel_id
                        )
                    )
                    if oldest_ts_str:
                        before_timestamp = datetime.datetime.fromisoformat(
                            oldest_ts_str
                        )

                log.info(
                    f"将从时间点 {before_timestamp or '最新'} 开始向前回溯历史帖子。"
                )

                # 2. 获取一批更旧的帖子
                threads_iterator = channel.archived_threads(
                    limit=chat_config.FORUM_POLL_THREAD_LIMIT, before=before_timestamp
                )
                threads_to_process = [t async for t in threads_iterator]

                if not threads_to_process:
                    log.info(
                        f"频道 {channel.name} 没有找到更早的帖子，标记为回溯完成。"
                    )
                    self.backfill_bookmarks[channel_id] = {
                        "timestamp": bookmark.get("timestamp"),
                        "is_complete": True,
                    }
                    async with aiosqlite.connect(self.db_path) as db:
                        await db.execute("PRAGMA journal_mode=WAL")
                        await db.execute(
                            "INSERT OR REPLACE INTO backfill_status (channel_id, oldest_known_timestamp, is_complete) VALUES (?, ?, 1)",
                            (channel_id, bookmark.get("timestamp")),
                        )
                        await db.commit()
                    continue

                # 3. 并发处理这批帖子
                log.info(f"找到 {len(threads_to_process)} 个历史帖子，准备并发处理...")
                tasks = [
                    self._process_thread_concurrently(thread, semaphore)
                    for thread in threads_to_process
                ]
                await asyncio.gather(*tasks)

                # 4. 更新书签
                new_oldest_thread = min(threads_to_process, key=lambda t: t.created_at)
                new_bookmark_ts = new_oldest_thread.created_at.isoformat()
                self.backfill_bookmarks[channel_id] = {
                    "timestamp": new_bookmark_ts,
                    "is_complete": False,
                }
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("PRAGMA journal_mode=WAL")
                    await db.execute(
                        "INSERT OR REPLACE INTO backfill_status (channel_id, oldest_known_timestamp, is_complete) VALUES (?, ?, 0)",
                        (channel_id, new_bookmark_ts),
                    )
                    await db.commit()
                log.info(f"频道 {channel.name} 的回溯书签已更新为: {new_bookmark_ts}")

            except Exception as e:
                log.error(f"回溯频道 {channel.name} 时出错: {e}", exc_info=True)

        completed_count = sum(
            1 for b in self.backfill_bookmarks.values() if b.get("is_complete")
        )
        if completed_count == len(channel_ids):
            log.info("所有频道的历史回溯任务均已完成，未来的轮询将只进行检查。")
        else:
            log.info("每日论坛历史回溯任务完成。")

    @poll_threads.before_loop
    async def before_poll_threads(self):
        """在任务开始前等待机器人准备就绪。"""
        await self.bot.wait_until_ready()

    async def handle_new_thread(self, thread: discord.Thread):
        """
        由中央事件处理器调用的公共方法，用于处理新的帖子。
        """
        try:
            log.info(
                f"[ForumSyncCog] 接收到新帖子进行处理: {thread.name} ({thread.id})"
            )
            await forum_search_service.process_thread(thread)
            # 将新帖子ID添加到数据库，以防轮询任务重复处理
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute(
                    "INSERT OR IGNORE INTO processed_threads (thread_id) VALUES (?)",
                    (thread.id,),
                )
                await db.commit()
            log.info(f"[ForumSyncCog] 帖子 {thread.id} 已成功处理并记录。")
        except Exception as e:
            log.error(
                f"[ForumSyncCog] 处理帖子 {thread.name} ({thread.id}) 时出错: {e}",
                exc_info=True,
            )


async def setup(bot: commands.Bot):
    """将此Cog添加到机器人中。"""
    await bot.add_cog(ForumSyncCog(bot))
