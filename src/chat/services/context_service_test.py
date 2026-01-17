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

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if bot:
            log.info("ContextServiceTest 已通过构造函数设置 bot 实例。")
        else:
            log.warning("ContextServiceTest 初始化时未收到有效的 bot 实例。")

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

        channel = self.bot.get_channel(channel_id)
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
            history_messages = []

            # --- 混合读取逻辑 ---
            cached_msgs = []
            api_messages = []

            # 1. 从缓存中获取所有可用的当前频道消息
            if self.bot and self.bot.cached_messages:
                cached_msgs = [
                    m for m in self.bot.cached_messages if m.channel.id == channel_id
                ]
                # 确保缓存消息按时间从旧到新排序
                cached_msgs.sort(key=lambda m: m.created_at)

            # 2. 判断是否需要调用 API
            if len(cached_msgs) >= limit:
                # 缓存完全满足需求
                history_messages = cached_msgs[-limit:]
                log.info(
                    f"[上下文服务-Test] 缓存命中。从缓存中获取 {len(history_messages)} 条消息。API 调用: 0。"
                )
            else:
                # 缓存不足或为空，需要 API 补充
                remaining_limit = limit - len(cached_msgs)
                before_message = None
                if cached_msgs:
                    # 如果缓存中有消息，就从最老的一条消息之前开始获取
                    before_message = discord.Object(id=cached_msgs[0].id)

                log.info(
                    f"[上下文服务-Test] 缓存找到 {len(cached_msgs)} 条，需要从 API 获取 {remaining_limit} 条。"
                )

                # 从 API 获取缺失的消息
                api_messages = [
                    msg
                    async for msg in channel.history(
                        limit=remaining_limit, before=before_message
                    )
                ]
                # API 返回的是从新到旧，需要反转以匹配时间顺序
                api_messages.reverse()

                # 合并两部分消息
                history_messages = api_messages + cached_msgs
                log.info(
                    f"[上下文服务-Test] 本次获取: 缓存 {len(cached_msgs)} 条, API {len(api_messages)} 条。总计 {len(history_messages)} 条。"
                )

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
# 修改：不再立即创建实例，而是等待 bot 对象被创建后再初始化
_context_service_test_instance: Optional["ContextServiceTest"] = None


def initialize_context_service_test(bot: commands.Bot):
    """
    全局初始化函数。必须在应用程序启动时调用一次。
    """
    global _context_service_test_instance
    if _context_service_test_instance is None:
        _context_service_test_instance = ContextServiceTest(bot)
        log.info("全局 ContextServiceTest 实例已成功初始化。")
    else:
        log.warning("尝试重复初始化 ContextServiceTest 实例，已跳过。")


def get_context_service() -> "ContextServiceTest":
    """
    获取 ContextServiceTest 的单例实例。
    如果实例尚未初始化，将引发 RuntimeError。
    """
    if _context_service_test_instance is None:
        raise RuntimeError(
            "ContextServiceTest 尚未初始化。请确保在应用启动时调用 initialize_context_service_test。"
        )
    return _context_service_test_instance
