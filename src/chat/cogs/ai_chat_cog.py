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
from src.chat.config.chat_config import CHAT_ENABLED
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

    # @app_commands.command(name="clear_context", description="清除指定用户的AI对话上下文")
    # @app_commands.describe(user="选择要清除上下文的用户")
    # @app_commands.default_permissions(administrator=True)
    # async def clear_context(self, interaction: discord.Interaction, user: discord.User):
    #     """斜杠命令，用于清除用户的AI对话历史"""
    #     try:
    #         guild_id = interaction.guild.id if interaction.guild else 0
    #         # 调用 context_service 清除用户上下文
    #         await context_service.clear_user_context(user.id, guild_id)
    #         await interaction.response.send_message(f"已成功清除用户 {user.mention} 的对话上下文。", ephemeral=True)
    #         log.info(f"管理员 {interaction.user} 清除了用户 {user.id} 的对话上下文")
    #     except Exception as e:
    #         log.error(f"清除用户上下文时出错: {e}")
    #         await interaction.response.send_message("清除上下文时发生错误，请检查日志。", ephemeral=True)

    # @app_commands.command(name="刷新记忆", description="(管理员) 将当前位置设为频道记忆的最新起点。")
    # @app_commands.default_permissions(administrator=True)
    # async def refresh_channel_memory(self, interaction: discord.Interaction):
    #     """
    #     斜杠命令，用于将当前命令的位置设置为频道记忆的新锚点。
    #     执行后，AI将只参考此命令之后发生的消息。
    #     """
    #     try:
    #         guild_id = interaction.guild.id if interaction.guild else 0
    #         channel_id = interaction.channel.id
    #         channel_name = interaction.channel.name

    #         # 获取此命令之前的最后一条消息
    #         last_message = [msg async for msg in interaction.channel.history(limit=1)]

    #         if not last_message:
    #             # 如果频道中没有消息，则不设置锚点，并告知用户
    #             await interaction.response.send_message(
    #                 f"频道 `#{channel_name}` 中还没有任何消息，无法设置记忆起点。",
    #                 ephemeral=True
    #             )
    #             log.warning(f"管理员 {interaction.user} 尝试在空频道 #{channel_name} 中刷新记忆，但失败了。")
    #             return

    #         anchor_message_id = last_message[0].id

    #         # 调用数据库管理器来设置或更新锚点
    #         await chat_db_manager.set_channel_memory_anchor(guild_id, channel_id, anchor_message_id)

    #         await interaction.response.send_message(
    #             f"好的，我已经刷新了对 `#{channel_name}` 频道的记忆。\n"
    #             f"从现在开始，我将只参考消息 ID `{anchor_message_id}` 之后的新对话作为上下文。",
    #             ephemeral=True
    #         )
    #         log.info(f"管理员 {interaction.user} 在频道 #{channel_name} 设置了新的记忆锚点: {anchor_message_id}。")
    #     except Exception as e:
    #         log.error(f"处理 refresh_channel_memory 命令时出错: {e}")
    #         if not interaction.response.is_done():
    #             await interaction.response.send_message("执行此命令时发生未知错误，请检查日志。", ephemeral=True)

    # @app_commands.command(name="清除频道记忆", description="(管理员) 清除当前频道的记忆锚点，解决上下文卡住的问题。")
    # @app_commands.default_permissions(administrator=True)
    # async def clear_channel_memory(self, interaction: discord.Interaction):
    #     """
    #     斜杠命令，用于删除当前频道的记忆锚点。
    #     """
    #     try:
    #         guild_id = interaction.guild.id if interaction.guild else 0
    #         channel_id = interaction.channel.id
    #         channel_name = interaction.channel.name

    #         deleted_rows = await chat_db_manager.delete_channel_memory_anchor(guild_id, channel_id)

    #         if deleted_rows > 0:
    #             await interaction.response.send_message(
    #                 f"已成功清除 `#{channel_name}` 频道的记忆锚点。\n"
    #                 "AI现在会参考此前的完整历史记录。",
    #                 ephemeral=True
    #             )
    #             log.info(f"管理员 {interaction.user} 清除了频道 #{channel_name} 的记忆锚点。")
    #         else:
    #             await interaction.response.send_message(
    #                 f"`#{channel_name}` 频道没有设置记忆锚点，无需清除。",
    #                 ephemeral=True
    #             )
    #     except Exception as e:
    #         log.error(f"处理 clear_channel_memory 命令时出错: {e}")
    #         if not interaction.response.is_done():
    #             await interaction.response.send_message("执行此命令时发生未知错误，请检查日志。", ephemeral=True)


async def setup(bot: commands.Bot):
    """将这个Cog添加到机器人中"""
    await bot.add_cog(AIChatCog(bot))
