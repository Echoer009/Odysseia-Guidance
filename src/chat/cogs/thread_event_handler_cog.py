# -*- coding: utf-8 -*-

import logging
import discord
from discord.ext import commands
import asyncio

from src.chat.config import chat_config
from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)

log = logging.getLogger(__name__)


class ThreadEventHandlerCog(commands.Cog):
    """
    一个中央处理器，用于监听所有与帖子（Thread）相关的事件。
    它会为每个需要响应的模块，启动一个带有独立延迟的异步任务，
    从而实现统一管理和灵活控制。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _dispatch_to_forum_sync(self, thread: discord.Thread):
        """检查条件并延迟后，分发给 ForumSyncCog 进行RAG索引。"""
        if thread.parent_id not in chat_config.FORUM_SEARCH_CHANNEL_IDS:
            return

        delay = chat_config.FORUM_SYNC_DELAY_SECONDS
        log.info(
            f"[ForumSync Dispatch] 帖子 {thread.id} 符合RAG索引条件。等待 {delay} 秒后开始处理..."
        )
        await asyncio.sleep(delay)
        forum_sync_cog = self.bot.get_cog("ForumSyncCog")
        if forum_sync_cog:
            # 类型断言：我们知道这个Cog有handle_new_thread方法
            assert isinstance(forum_sync_cog, commands.Cog)
            # 使用getattr来避免类型检查错误
            if hasattr(forum_sync_cog, "handle_new_thread"):
                await getattr(forum_sync_cog, "handle_new_thread")(thread)
            else:
                log.warning(
                    "[ForumSync Dispatch] ForumSyncCog 没有handle_new_thread方法。"
                )
        else:
            log.warning("[ForumSync Dispatch] 找不到 ForumSyncCog 实例，任务取消。")

    async def _dispatch_to_coin_cog(self, thread: discord.Thread):
        """检查条件并延迟后，获取消息并分发给 CoinCog 发放奖励。"""
        if thread.guild.id not in chat_config.COIN_REWARD_GUILD_IDS:
            return

        delay = chat_config.COIN_REWARD_DELAY_SECONDS
        log.info(
            f"[CoinCog Dispatch] 帖子 {thread.id} 符合发币奖励条件。等待 {delay} 秒后开始处理..."
        )
        await asyncio.sleep(delay)
        try:
            first_message = await anext(thread.history(limit=1, oldest_first=True))
            coin_cog = self.bot.get_cog("CoinCog")
            if coin_cog:
                # 类型断言：我们知道这个Cog有handle_new_thread_reward方法
                assert isinstance(coin_cog, commands.Cog)
                # 使用getattr来避免类型检查错误
                if hasattr(coin_cog, "handle_new_thread_reward"):
                    await getattr(coin_cog, "handle_new_thread_reward")(
                        thread, first_message
                    )
                else:
                    log.warning(
                        "[CoinCog Dispatch] CoinCog 没有handle_new_thread_reward方法。"
                    )
            else:
                log.warning("[CoinCog Dispatch] 找不到 CoinCog 实例，任务取消。")
        except (discord.NotFound, StopAsyncIteration):
            log.warning(
                f"[CoinCog Dispatch] 等待后仍然无法为帖子 {thread.id} 找到起始消息。"
            )
        except Exception as e:
            log.error(
                f"[CoinCog Dispatch] 处理帖子 {thread.id} 奖励时发生未知错误: {e}",
                exc_info=True,
            )

    async def _dispatch_to_thread_commentor(self, thread: discord.Thread):
        """检查条件后，分发给 ThreadCommentorCog 进行暖贴。"""
        try:
            log.info(f"[Commentor Dispatch] 开始检查帖子 {thread.id} 的暖贴条件...")

            is_enabled = await chat_settings_service.is_warm_up_enabled(thread.guild.id)
            log.info(f"[Commentor Dispatch] 全局暖贴开关: {is_enabled}")

            is_channel = await chat_settings_service.is_warm_up_channel(
                thread.guild.id, thread.parent_id
            )
            log.info(
                f"[Commentor Dispatch] 频道 {thread.parent_id} 是否为暖贴频道: {is_channel}"
            )

            should_warm_up = is_enabled and is_channel
            log.info(f"[Commentor Dispatch] 最终是否暖贴: {should_warm_up}")

            if not should_warm_up:
                log.info(
                    f"[Commentor Dispatch] 帖子 {thread.id} 不符合暖贴条件，跳过。"
                )
                return

            log.info(f"[Commentor Dispatch] 帖子 {thread.id} 符合暖贴条件，开始处理...")
            thread_commentor_cog = self.bot.get_cog("ThreadCommentorCog")
            if thread_commentor_cog:
                # 类型断言：我们知道这个Cog有handle_new_thread_comment方法
                assert isinstance(thread_commentor_cog, commands.Cog)
                # 使用getattr来避免类型检查错误
                if hasattr(thread_commentor_cog, "handle_new_thread_comment"):
                    await getattr(thread_commentor_cog, "handle_new_thread_comment")(
                        thread
                    )
                else:
                    log.warning(
                        "[Commentor Dispatch] ThreadCommentorCog 没有handle_new_thread_comment方法。"
                    )
            else:
                log.warning(
                    "[Commentor Dispatch] 找不到 ThreadCommentorCog 实例，任务取消。"
                )
        except Exception as e:
            log.error(
                f"[Commentor Dispatch] 处理帖子 {thread.id} 暖贴时发生未知错误: {e}",
                exc_info=True,
            )

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """
        统一监听新帖子的创建事件，并为每个目标模块启动一个带独立延迟的异步任务。
        """
        log.info(
            f"[Central Dispatcher] 检测到新帖子 '{thread.name}' ({thread.id})，开始分发任务..."
        )

        # --- 任务分发逻辑 ---
        # 为每个潜在的目标模块启动一个独立的、非阻塞的异步任务。
        # 每个任务自己负责检查是否需要执行。

        asyncio.create_task(self._dispatch_to_forum_sync(thread))
        asyncio.create_task(self._dispatch_to_coin_cog(thread))
        asyncio.create_task(self._dispatch_to_thread_commentor(thread))


async def setup(bot: commands.Bot):
    """将此Cog添加到机器人中。"""
    await bot.add_cog(ThreadEventHandlerCog(bot))
    log.info("中央帖子事件处理器 (ThreadEventHandlerCog) 已加载。")
