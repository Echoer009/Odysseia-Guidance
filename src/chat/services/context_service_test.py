# -*- coding: utf-8 -*-

import logging
from typing import Optional, Dict, List, Any
import discord
from discord.ext import commands
import re
from src.chat.config import chat_config
from src.chat.utils.database import chat_db_manager
from src.chat.services.regex_service import regex_service

log = logging.getLogger(__name__)


class ContextServiceTest:
    """上下文管理服务测试版本，用于对比新的上下文处理逻辑"""

    def __init__(self):
        self.bot: Optional[commands.Bot] = None

    def set_bot_instance(self, bot: commands.Bot):
        self.bot = bot
        log.info("ContextServiceTest 已设置 bot 实例。")

    async def get_formatted_channel_history_new(
        self,
        channel_id: int,
        user_id: int,
        guild_id: int,
        limit: int = chat_config.CHANNEL_MEMORY_CONFIG["formatted_history_limit"],
        exclude_message_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取结构化的频道对话历史。
        此方法将历史消息与用户的最新消息分离，以引导模型只回复最新内容。
        """
        if not self.bot:
            log.error("ContextServiceTest 的 bot 实例未设置，无法获取频道消息历史。")
            return []

        channel = self.bot.get_channel(channel_id) or self.bot.get_thread(channel_id)
        if not channel:
            try:
                # 作为备用方案，尝试通过API获取，这可以找到公开帖子
                channel = await self.bot.fetch_channel(channel_id)
                if isinstance(channel, (discord.abc.GuildChannel, discord.Thread)):
                    log.info(
                        f"通过 fetch_channel 成功获取到频道/帖子: {channel.name} (ID: {channel_id})"
                    )
                else:
                    log.info(f"通过 fetch_channel 成功获取到频道 (ID: {channel_id})")
            except (discord.NotFound, discord.Forbidden):
                log.warning(
                    f"无法通过 get_channel 或 fetch_channel 找到 ID 为 {channel_id} 的频道或帖子。"
                )
                return []

        # 检查是否是支持消息历史的类型
        if not isinstance(channel, (discord.TextChannel, discord.Thread)):
            log.warning(
                f"频道 ID {channel_id} 的类型为 {type(channel)}，不支持读取消息历史。"
            )
            return []

        history_parts = []
        try:
            guild_id = channel.guild.id if channel.guild else 0
            anchor_message_id = await chat_db_manager.get_channel_memory_anchor(
                guild_id, channel_id
            )

            after_message = None
            fetch_limit = limit
            if anchor_message_id:
                try:
                    after_message = discord.Object(id=anchor_message_id)
                    log.info(
                        f"找到频道 {channel_id} 的记忆锚点: {anchor_message_id}，将从此消息之后开始获取历史。"
                    )
                except Exception as e:
                    log.error(
                        f"创建 discord.Object 失败，锚点ID {anchor_message_id} 可能无效: {e}"
                    )

            history_messages = [
                msg
                async for msg in channel.history(limit=fetch_limit, after=after_message)
            ]

            if not after_message:
                history_messages.reverse()

            # 处理历史消息
            for msg in history_messages:
                is_irrelevant_type = msg.type not in (
                    discord.MessageType.default,
                    discord.MessageType.reply,
                )
                if is_irrelevant_type or msg.id == exclude_message_id:
                    continue

                clean_content = self.clean_message_content(msg.content, msg.guild)
                if not clean_content and not msg.attachments:
                    continue

                reply_info = ""
                if msg.reference and msg.reference.message_id:
                    try:
                        ref_msg = await channel.fetch_message(msg.reference.message_id)
                        if ref_msg and ref_msg.author:
                            reply_info = f"[回复 {ref_msg.author.display_name}]"
                    except (discord.NotFound, discord.Forbidden):
                        pass

                # 强制在元信息（用户名和回复）后添加冒号，清晰地分割内容
                user_meta = f"[{msg.author.display_name}]{reply_info}"
                final_part = f"{user_meta}: {clean_content}"
                history_parts.append(final_part)

            # 构建最终的上下文列表
            final_context = []

            # 1. 将所有历史记录打包成一个 user 消息作为背景
            if history_parts:
                background_prompt = "这是本频道最近的对话记录:\n\n" + "\n\n".join(
                    history_parts
                )
                final_context.append({"role": "user", "parts": [background_prompt]})

            # 2. 添加一个确认收到历史背景的 model 回复，以维持对话轮次
            final_context.append({"role": "model", "parts": ["我已了解频道的历史对话"]})

            return final_context
        except discord.Forbidden:
            log.error(f"机器人没有权限读取频道 {channel_id} 的消息历史。")
            return []
        except Exception as e:
            log.error(f"获取并格式化频道 {channel_id} 消息历史时出错: {e}")
            return []

    def clean_message_content(
        self, content: str, guild: Optional[discord.Guild]
    ) -> str:
        """
        净化消息内容，移除或替换不适合模型处理的元素。
        """
        # 还原 Discord 为了 Markdown 显示而自动添加的转义
        content = content.replace("\\_", "_")

        content = re.sub(r"https?://cdn\.discordapp\.com\S+", "", content)
        if guild:

            def replace_mention(match):
                user_id = int(match.group(1))
                member = guild.get_member(user_id)
                return f"@{member.display_name}" if member else "@未知用户"

            content = re.sub(r"<@!?(\d+)>", replace_mention, content)
        content = re.sub(r"<a?:\w+:\d+>", "", content)
        content = regex_service.clean_user_input(content)
        return content.strip()


# 全局实例
context_service_test = ContextServiceTest()
