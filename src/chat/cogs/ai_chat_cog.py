# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
import logging
from typing import Optional

# 导入新的 Service
from src.chat.services.chat_service import chat_service
from src.chat.services.message_processor import message_processor

# 导入上下文服务以设置 bot 实例
from src.chat.services.context_service import context_service
from src.chat.services.context_service_test import context_service_test  # 导入测试服务

# 导入数据库管理器以进行黑名单检查和斜杠命令
from src.chat.utils.database import chat_db_manager
from src.chat.config.chat_config import CHAT_ENABLED, MESSAGE_SETTINGS
from src.chat.features.odysseia_coin.service.coin_service import coin_service

log = logging.getLogger(__name__)


class AIChatCog(commands.Cog):
    """处理AI聊天功能的Cog，包括@mention回复和斜杠命令"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 将bot实例传递给需要它的服务
        context_service.set_bot_instance(bot)
        context_service_test.set_bot_instance(bot)  # 为测试服务也设置bot实例

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        监听所有消息，当bot被@mention时进行回复
        """
        if not CHAT_ENABLED:
            return

        # 忽略机器人自己的消息
        if message.author.bot:
            return

        # --- 核心前置检查 ---
        # 在处理任何逻辑之前，首先检查消息是否应该被 message_processor 忽略
        # 这会处理置顶帖和禁用频道的情况
        processed_data = await message_processor.process_message(message, self.bot)
        if processed_data is None:
            # 如果返回 None，说明消息来自一个应被忽略的源（如置顶帖），直接退出
            return

        # 检查消息是否符合处理条件：私聊 或 在服务器中被@
        is_dm = message.guild is None
        is_mentioned = self.bot.user in message.mentions

        if not is_dm and not is_mentioned:
            return

        # 新增：检查是否在帖子中，以及帖子创建者是否禁用了回复
        if isinstance(message.channel, discord.Thread):
            # 检查帖子的创建者
            thread_owner = message.channel.owner
            if thread_owner and await coin_service.blocks_thread_replies(
                thread_owner.id
            ):
                log.info(
                    f"帖子 '{message.channel.name}' 的创建者 {thread_owner.id} 已禁用回复，跳过消息处理。"
                )
                return

        # 黑名单检查
        if await chat_db_manager.is_user_globally_blacklisted(message.author.id):
            log.info(f"用户 {message.author.id} 在全局黑名单中，已跳过。")
            return

        # 在显示“输入中”之前执行所有前置检查
        if not await chat_service.should_process_message(message):
            return

        # 显示"正在输入"状态，直到AI响应生成完毕
        response_text = None
        async with message.channel.typing():
            # 注意：这里我们将已经处理过的数据传递下去
            response_text = await self.handle_chat_message(message, processed_data)

        # 在退出 typing 状态后发送回复
        if response_text:
            try:
                if len(response_text) > MESSAGE_SETTINGS["DM_THRESHOLD"]:
                    try:
                        await message.author.send(
                            f"刚刚在 {message.channel.mention} 频道里，你想听我说的话有点多，在这里悄悄告诉你哦：\n\n{response_text}"
                        )
                        log.info(
                            f"回复因过长已通过私信发送给 {message.author.display_name}"
                        )
                    except discord.Forbidden:
                        log.warning(
                            f"无法通过私信发送给 {message.author.display_name}，将在原频道回复提示信息。"
                        )
                        await message.reply(
                            "字太多啦，我不要刷屏。你的私信又关了，我就不给你讲啦！",
                            mention_author=True,
                        )
                else:
                    await message.reply(response_text, mention_author=True)
            except discord.errors.HTTPException as e:
                log.warning(f"发送回复失败: {e}")
                pass  # 如果发送回复失败，则忽略

    async def handle_chat_message(
        self, message: discord.Message, processed_data: dict
    ) -> Optional[str]:
        """
        处理聊天消息（包括私聊和@mention），协调各个服务生成AI回复并返回其内容
        """
        try:
            # 1. MessageProcessor 的处理已前移到 on_message 中

            # 2. 使用 ChatService 获取AI回复
            # --- 新增：获取并传递位置信息 ---
            guild_name = message.guild.name if message.guild else "私信"
            location_name = ""
            if isinstance(message.channel, discord.Thread):
                # 如果是帖子（子区），显示“父频道 -> 帖子名”
                parent_channel_name = (
                    message.channel.parent.name
                    if message.channel.parent
                    else "未知频道"
                )
                location_name = f"{parent_channel_name} -> {message.channel.name}"
            else:
                # 否则，直接显示频道名
                location_name = message.channel.name

            final_response = await chat_service.handle_chat_message(
                message, processed_data, guild_name, location_name
            )

            # 3. 返回回复内容
            return final_response

        except Exception as e:
            log.error(f"[AIChatCog] 处理@mention消息时发生顶层错误: {e}", exc_info=True)
            # 确保即使发生意外错误也有反馈
            return "抱歉，处理你的请求时遇到了一个未知错误。"


async def setup(bot: commands.Bot):
    """将这个Cog添加到机器人中"""
    await bot.add_cog(AIChatCog(bot))
