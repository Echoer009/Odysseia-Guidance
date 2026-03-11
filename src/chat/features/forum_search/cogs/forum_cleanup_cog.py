# -*- coding: utf-8 -*-

import logging
import discord
from discord.ext import commands, tasks
import datetime
from typing import Set, Dict, Any

from src.chat.config import chat_config
from src.chat.features.forum_search.services.forum_vector_db_service import (
    forum_vector_db_service,
)

log = logging.getLogger(__name__)


class ForumCleanupCog(commands.Cog):
    """
    后台任务：每日清理数据库中已删除的论坛帖子。

    执行频率：每天 UTC 20:00（北京时间凌晨 4:00）
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_task.start()

    async def cog_unload(self):
        """Cog 卸载时取消任务"""
        self.cleanup_task.cancel()

    @tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=datetime.timezone.utc))
    async def cleanup_task(self):
        """
        每日清理任务：删除数据库中已不存在于 Discord 的帖子。
        """
        log.info("[ForumCleanup] 开始每日失效帖子清理任务...")

        # 检查是否启用
        if not chat_config.FORUM_CLEANUP_ENABLED:
            log.info("[ForumCleanup] 清理任务已禁用，跳过。")
            return

        if not forum_vector_db_service.is_available():
            log.warning("[ForumCleanup] 论坛向量数据库服务不可用，跳过清理。")
            return

        channel_ids = chat_config.FORUM_SEARCH_CHANNEL_IDS
        if not channel_ids:
            log.info("[ForumCleanup] 没有配置论坛频道ID，任务结束。")
            return

        total_deleted = 0

        for channel_id in channel_ids:
            try:
                deleted_count = await self._cleanup_channel(channel_id)
                total_deleted += deleted_count
            except Exception as e:
                log.error(
                    f"[ForumCleanup] 清理频道 {channel_id} 时出错: {e}",
                    exc_info=True,
                )

        log.info(
            f"[ForumCleanup] 每日清理任务完成，共删除 {total_deleted} 个失效帖子。"
        )

    async def _cleanup_channel(self, channel_id: int) -> int:
        """
        清理单个频道的失效帖子。

        Args:
            channel_id: 论坛频道 ID

        Returns:
            删除的帖子数量
        """
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.ForumChannel):
            log.warning(f"[ForumCleanup] ID {channel_id} 不是有效的论坛频道，已跳过。")
            return 0

        log.info(f"[ForumCleanup] --- 开始清理频道: {channel.name} ({channel_id}) ---")

        # 1. 获取数据库中该频道的所有帖子 ID
        db_thread_ids = set(
            await forum_vector_db_service.get_thread_ids_by_channel(channel_id)
        )

        if not db_thread_ids:
            log.info(f"[ForumCleanup] 频道 {channel.name} 数据库中没有帖子记录。")
            return 0

        log.info(f"[ForumCleanup] 数据库中有 {len(db_thread_ids)} 个帖子记录。")

        # 2. 获取 Discord 中实际存在的帖子 ID
        discord_thread_ids = await self._get_existing_thread_ids(channel)
        log.info(f"[ForumCleanup] Discord 中有 {len(discord_thread_ids)} 个帖子。")

        # 3. 计算差集：数据库中有但 Discord 中没有的
        deleted_thread_ids = db_thread_ids - discord_thread_ids

        if not deleted_thread_ids:
            log.info(f"[ForumCleanup] 频道 {channel.name} 没有失效帖子需要清理。")
            return 0

        log.info(f"[ForumCleanup] 发现 {len(deleted_thread_ids)} 个失效帖子待清理。")

        # 4. 批量删除
        deleted_count = await forum_vector_db_service.delete_threads_by_ids(
            list(deleted_thread_ids)
        )
        log.info(
            f"[ForumCleanup] 频道 {channel.name} 已清理 {deleted_count} 个失效帖子。"
        )

        return deleted_count

    async def _get_existing_thread_ids(self, channel: discord.ForumChannel) -> Set[int]:
        """
        获取频道中所有实际存在的帖子 ID（活跃 + 归档）。

        Args:
            channel: 论坛频道

        Returns:
            帖子 ID 集合
        """
        thread_ids: Set[int] = set()

        # 获取活跃帖子
        for thread in channel.threads:
            thread_ids.add(thread.id)

        # 获取归档帖子
        async for thread in channel.archived_threads(limit=None):
            thread_ids.add(thread.id)

        return thread_ids

    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """在任务开始前等待机器人准备就绪"""
        await self.bot.wait_until_ready()

    async def cleanup_all_channels(self) -> Dict[str, Any]:
        """
        清理所有配置的论坛频道（供外部调用，如管理面板按钮）。

        Returns:
            {
                'total_indexed': int,      # 数据库中帖子总数
                'total_active': int,       # Discord 中帖子总数
                'total_deleted': int,      # 被清理的帖子数
                'channels': [              # 每个频道的详情
                    {
                        'channel_id': int,
                        'channel_name': str,
                        'indexed': int,
                        'active': int,
                        'deleted': int
                    }
                ]
            }
        """
        result: Dict[str, Any] = {
            "total_indexed": 0,
            "total_active": 0,
            "total_deleted": 0,
            "channels": [],
        }

        if not forum_vector_db_service.is_available():
            log.warning("[ForumCleanup] 论坛向量数据库服务不可用。")
            return result

        channel_ids = chat_config.FORUM_SEARCH_CHANNEL_IDS
        if not channel_ids:
            return result

        for channel_id in channel_ids:
            channel = self.bot.get_channel(channel_id)
            if not isinstance(channel, discord.ForumChannel):
                continue

            # 获取数据库中的帖子
            db_thread_ids = set(
                await forum_vector_db_service.get_thread_ids_by_channel(channel_id)
            )

            # 获取 Discord 中的帖子
            discord_thread_ids = await self._get_existing_thread_ids(channel)

            # 计算差集并删除
            deleted_thread_ids = db_thread_ids - discord_thread_ids
            deleted_count = 0
            if deleted_thread_ids:
                deleted_count = await forum_vector_db_service.delete_threads_by_ids(
                    list(deleted_thread_ids)
                )

            channel_info = {
                "channel_id": channel_id,
                "channel_name": channel.name,
                "indexed": len(db_thread_ids),
                "active": len(discord_thread_ids),
                "deleted": deleted_count,
            }
            result["channels"].append(channel_info)
            result["total_indexed"] += len(db_thread_ids)
            result["total_active"] += len(discord_thread_ids)
            result["total_deleted"] += deleted_count

        return result

    async def get_deleted_threads_preview(self, channel_id: int) -> Dict[str, Any]:
        """
        获取指定频道中失效帖子的预览信息（不执行删除）。

        Args:
            channel_id: 频道 ID

        Returns:
            {
                'channel_id': int,
                'channel_name': str,
                'deleted_thread_ids': List[int],  # 失效帖子 ID 列表
                'deleted_threads_info': List[Dict],  # 失效帖子详情列表
            }
            如果频道无效或没有失效帖子，返回空字典。
        """
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.ForumChannel):
            return {}

        db_thread_ids = set(
            await forum_vector_db_service.get_thread_ids_by_channel(channel_id)
        )

        discord_thread_ids = await self._get_existing_thread_ids(channel)

        deleted_thread_ids = db_thread_ids - discord_thread_ids

        if not deleted_thread_ids:
            return {}

        # 获取失效帖子的详细信息
        deleted_threads_info = await forum_vector_db_service.get_deleted_threads_info(
            list(deleted_thread_ids)
        )

        return {
            "channel_id": channel_id,
            "channel_name": channel.name,
            "deleted_thread_ids": list(deleted_thread_ids),
            "deleted_threads_info": deleted_threads_info,
        }


# 全局实例，供外部调用
forum_cleanup_cog: ForumCleanupCog | None = None


async def setup(bot: commands.Bot):
    """将此 Cog 添加到机器人中。"""
    global forum_cleanup_cog
    forum_cleanup_cog = ForumCleanupCog(bot)
    await bot.add_cog(forum_cleanup_cog)
    log.info("[ForumCleanup] ForumCleanupCog 已加载。")
