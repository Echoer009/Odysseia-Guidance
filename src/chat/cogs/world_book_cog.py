# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
import logging
from src.chat.config import chat_config
from src.chat.services.review_service import review_service

log = logging.getLogger(__name__)

# --- 审核配置 ---
REVIEW_SETTINGS = chat_config.WORLD_BOOK_CONFIG["review_settings"]
VOTE_EMOJI = REVIEW_SETTINGS["vote_emoji"]
REJECT_EMOJI = REVIEW_SETTINGS["reject_emoji"]


class WorldBookCog(commands.Cog):
    """
    处理世界之书相关功能的Cog（已重构）。
    该Cog现在只作为事件监听器，将所有复杂的审核逻辑转发给 ReviewService。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 定时任务已移至 ReviewService
        # self.check_expired_entries.start()

    def cog_unload(self):
        # 定时任务已移至 ReviewService
        # self.check_expired_entries.cancel()
        pass

    @commands.Cog.listener("on_raw_reaction_add")
    async def on_review_reaction(self, payload: discord.RawReactionActionEvent):
        """
        监听对审核消息的反应，并将其转发给 ReviewService。
        """
        # 步骤 1: 忽略机器人自己的反应
        if payload.user_id == self.bot.user.id:
            return

        # 步骤 2: 检查是否是有效的投票表情
        if str(payload.emoji) not in [VOTE_EMOJI, REJECT_EMOJI]:
            return

        # 步骤 3: 确保 ReviewService 已初始化
        if not review_service:
            log.warning("ReviewService 尚未初始化，无法处理投票事件。")
            return

        # 步骤 4: 将事件转发给 ReviewService
        # ReviewService 将负责获取消息、解析ID和处理所有后续逻辑
        await review_service.handle_vote(payload)


async def setup(bot: commands.Bot):
    """将这个Cog添加到机器人中"""
    await bot.add_cog(WorldBookCog(bot))
