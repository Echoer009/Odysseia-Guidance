# -*- coding: utf-8 -*-

import logging
import discord
from discord.ext import commands
import asyncio

from src.chat.features.thread_commentor.services.thread_commentor_service import (
    thread_commentor_service,
)
from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.config.chat_config import THREAD_COMMENTOR_CONFIG

log = logging.getLogger(__name__)


class ThreadCommentorCog(commands.Cog):
    """一个用于监听新帖子并进行评价的 Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_thread_create(self, thread: discord.Thread):
        """
        当有新帖子被创建时触发。
        """
        # 1. 检查暖贴功能是否全局开启
        if not await chat_settings_service.is_warm_up_enabled(thread.guild.id):
            return

        # 2. 检查该频道是否在暖贴频道列表中
        if not await chat_settings_service.is_warm_up_channel(
            thread.guild.id, thread.parent_id
        ):
            return

        # 3. 检查发帖人是否为机器人本身，避免自我循环
        if thread.owner_id == self.bot.user.id:
            log.info(f"帖子 '{thread.name}' 由机器人自己创建，跳过。")
            return

        log.info(
            f"检测到目标频道 '{thread.parent.name}' (ID: {thread.parent_id}) 的新帖子: '{thread.name}' (ID: {thread.id})"
        )

        # 获取发帖人信息
        user_id = thread.owner_id
        user_nickname = thread.owner.display_name
        log.info(f"帖子作者: {user_nickname} (ID: {user_id})")

        # 添加一个随机延迟，让回复看起来更自然
        delay = THREAD_COMMENTOR_CONFIG["INITIAL_DELAY_SECONDS"]
        log.info(f"等待 {delay} 秒后发送评价...")
        await asyncio.sleep(delay)

        try:
            # 4. 调用服务生成评价，并传递用户信息
            praise_text = await thread_commentor_service.praise_new_thread(
                thread, user_id, user_nickname
            )

            # 5. 如果成功生成，则发送到帖子
            if praise_text:
                await thread.send(praise_text)
                log.info(f"成功发送对帖子 '{thread.name}' 的评价。")
            else:
                log.warning(f"未能为帖子 '{thread.name}' 生成评价，或评价为空。")

        except Exception as e:
            log.error(f"处理帖子 '{thread.name}' 时发生未知错误: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ThreadCommentorCog(bot))
