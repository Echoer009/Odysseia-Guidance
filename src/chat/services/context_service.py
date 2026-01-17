# -*- coding: utf-8 -*-

import logging
from typing import Optional, Dict, List, Any
import discord  # 导入discord模块
from discord.ext import commands
import re  # 导入正则表达式模块
from src import config
from src.chat.config import chat_config  # 导入 chat_config
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)


class ContextService:
    """上下文管理服务，处理用户个人上下文和频道全局上下文"""

    def __init__(self):
        self.bot = None  # 初始化时bot实例为空

    def set_bot_instance(self, bot: commands.Bot):
        """设置bot实例，以便访问Discord API"""
        self.bot = bot
        log.info("ContextService 已设置 bot 实例。")

    async def get_user_conversation_history(
        self, user_id: int, guild_id: int
    ) -> List[Dict]:
        """从数据库获取用户的对话历史"""
        context = await chat_db_manager.get_ai_conversation_context(user_id, guild_id)
        if context and context.get("conversation_history"):
            return context["conversation_history"]
        return []

    async def update_user_conversation_history(
        self, user_id: int, guild_id: int, user_message: str, ai_response: str
    ):
        """更新用户的对话历史到数据库"""
        current_history = await self.get_user_conversation_history(user_id, guild_id)

        # 添加上一轮对话
        current_history.append({"role": "user", "parts": [user_message]})
        current_history.append({"role": "model", "parts": [ai_response]})

        await chat_db_manager.update_ai_conversation_context(
            user_id, guild_id, current_history
        )

    async def get_channel_conversation_history(
        self,
        channel_id: int,
        limit: int = chat_config.CHANNEL_MEMORY_CONFIG["raw_history_limit"],
    ) -> List[Dict]:
        """
        从Discord API获取频道的全局对话历史（最近N条消息）
        """
        if not self.bot:
            log.error("ContextService 的 bot 实例未设置，无法获取频道消息历史。")
            return []

        channel = self.bot.get_channel(channel_id)
        if not channel:
            log.warning(f"未找到频道 ID: {channel_id}，无法获取频道消息历史。")
            return []

        history = []
        try:
            if not isinstance(channel, (discord.TextChannel, discord.Thread)):
                log.warning(f"频道 {channel_id} 类型不支持 history 方法，已跳过。")
                return []
            # 使用 async for 循环来正确处理异步迭代器
            async for msg in channel.history(limit=limit):
                # 忽略其他机器人和系统消息
                # 只过滤掉非我们关心的消息类型（保留 default 和 reply）
                is_irrelevant_type = msg.type not in (
                    discord.MessageType.default,
                    discord.MessageType.reply,
                )
                if is_irrelevant_type:
                    continue

                # 提取消息内容
                if msg.content:
                    # 净化消息内容，替换用户提及
                    # 净化消息内容，移除提及、URL和自定义表情
                    clean_content = self.clean_message_content(msg.content, msg.guild)
                    history.append(
                        {
                            "role": "user",
                            "parts": [f"{msg.author.display_name}: {clean_content}"],
                        }
                    )

            # history.flatten() 返回的是从新到旧的消息，我们需要反转列表以保持时间顺序
            return history[::-1]
        except discord.Forbidden:
            log.error(f"机器人没有权限读取频道 {channel_id} 的消息历史。")
            return []
        except Exception as e:
            log.error(f"获取频道 {channel_id} 消息历史时出错: {e}")
            return []

    async def get_formatted_channel_history(
        self,
        channel_id: int,
        user_id: int,
        guild_id: int,
        limit: int = chat_config.CHANNEL_MEMORY_CONFIG["formatted_history_limit"],
        exclude_message_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取结构化的频道对话历史，用于构建多轮对话请求。
        此方法会合并连续的用户消息，以符合 user/model 交替的API格式。
        如果数据库中存在记忆锚点，则只获取该锚点之后的消息。

        Args:
            channel_id (int): 频道ID。
            limit (int): 获取的消息数量上限。
            exclude_message_id (Optional[int]): 需要从历史记录中排除的特定消息ID。
        """
        log.info(f"--- 开始获取频道 {channel_id} 的历史记录 ---")
        if not self.bot:
            log.error("ContextService 的 bot 实例未设置，无法获取频道消息历史。")
            return []

        channel = self.bot.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            log.warning(f"未找到或无效的文本频道 ID: {channel_id}")
            return []

        history_list = []
        user_messages_buffer = []
        model_messages_buffer = []

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
                    f"[上下文服务] 缓存命中。从缓存中获取 {len(history_messages)} 条消息。API 调用: 0。"
                )
            else:
                # 缓存不足或为空，需要 API 补充
                remaining_limit = limit - len(cached_msgs)
                before_message = None
                if cached_msgs:
                    # 如果缓存中有消息，就从最老的一条消息之前开始获取
                    before_message = discord.Object(id=cached_msgs[0].id)

                log.info(
                    f"[上下文服务] 缓存找到 {len(cached_msgs)} 条，需要从 API 获取 {remaining_limit} 条。"
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
                    f"[上下文服务] 本次获取: 缓存 {len(cached_msgs)} 条, API {len(api_messages)} 条。总计 {len(history_messages)} 条。"
                )

            for msg in history_messages:
                # 根据用户要求，不再过滤任何机器人消息
                # 只过滤掉非我们关心的消息类型（保留 default 和 reply），并排除指定消息
                is_irrelevant_type = msg.type not in (
                    discord.MessageType.default,
                    discord.MessageType.reply,
                )
                if is_irrelevant_type or msg.id == exclude_message_id:
                    continue

                clean_content = self.clean_message_content(msg.content, msg.guild)
                if not clean_content and not msg.attachments:
                    continue

                # --- 新增：处理回复关系 ---
                reply_info = ""
                if msg.reference and msg.reference.message_id:
                    try:
                        # 尝试从缓存或API获取被回复的消息
                        ref_msg = await channel.fetch_message(msg.reference.message_id)
                        if ref_msg and ref_msg.author:
                            # 清理被回复消息的内容
                            # 创建更丰富的回复信息，包括被回复的内容摘要
                            # 使用更不容易被模型模仿的括号和格式来构造回复信息
                            reply_info = f"[{ref_msg.author.display_name}] "
                    except (discord.NotFound, discord.Forbidden):
                        log.warning(
                            f"无法找到或无权访问被回复的消息 ID: {msg.reference.message_id}"
                        )
                        pass  # 获取失败则静默忽略

                if (self.bot.user and msg.author.id == self.bot.user.id) or (
                    config.BRAIN_GIRL_APP_ID
                    and msg.author.id == config.BRAIN_GIRL_APP_ID
                ):
                    # Bot的消息 (model) - 冲洗用户缓冲区，然后将消息添加到模型缓冲区
                    if user_messages_buffer:
                        history_list.append(
                            {
                                "role": "user",
                                "parts": ["\n\n".join(user_messages_buffer)],
                            }
                        )
                        user_messages_buffer = []

                    # 统一历史消息中机器人和用户的回复格式，解决主语混淆问题
                    bot_message_content = (
                        f"[{msg.author.display_name}]: {reply_info}{clean_content}"
                    )
                    model_messages_buffer.append(bot_message_content)
                else:
                    # 用户的消息 (user) - 冲洗模型缓冲区，然后将消息添加到用户缓冲区
                    if model_messages_buffer:
                        history_list.append(
                            {
                                "role": "model",
                                "parts": ["\n\n".join(model_messages_buffer)],
                            }
                        )
                        model_messages_buffer = []

                    # 格式化用户消息，符合用户期望的 [用户名]:xxxx 或 [用户名][回复xxx]:xxxx
                    # 恢复旧版格式，冒号始终在用户名后
                    formatted_message = (
                        f"[{msg.author.display_name}]: {reply_info}{clean_content}"
                    )
                    user_messages_buffer.append(formatted_message)

            # 循环结束后，如果缓冲区还有用户消息，全部作为最后一个'user'回合提交
            if user_messages_buffer:
                history_list.append(
                    {"role": "user", "parts": ["\n\n".join(user_messages_buffer)]}
                )

            # 同样，如果模型缓冲区还有消息，也全部提交
            if model_messages_buffer:
                history_list.append(
                    {"role": "model", "parts": ["\n\n".join(model_messages_buffer)]}
                )

            # 频道历史只返回纯粹的对话历史，好感度和用户档案的注入由 prompt_service 统一处理
            history_list.append(
                {
                    "role": "model",
                    "parts": [
                        "好的，上面是已知的历史消息，我会针对用户的最新消息进行回复。"
                    ],
                }
            )
            return history_list
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
        - 移除 Discord CDN 链接。
        - 移除自定义表情符号代码 <a:name:id> 或 <:name:id>。
        - 替换用户提及 <@USER_ID> 为 @USERNAME。
        - 清理用户输入中的所有指定括号。
        """
        # 1. 移除 Discord CDN 链接 (例如 https://cdn.discordapp.com/...)
        content = re.sub(r"https?://cdn\.discordapp\.com\S+", "", content)

        # 3. 将用户提及 <@USER_ID> 替换为 @USERNAME
        log.info("[Mention Clean] ----- Start Mention Cleaning -----")
        log.info(f"[Mention Clean] Initial content: '{content}'")
        log.info(f"[Mention Clean] Guild available: {bool(guild)}")

        if guild:

            def replace_mention(match):
                user_id_str = match.group(1)
                log.info(f"[Mention Clean] Matched user ID string: '{user_id_str}'")
                try:
                    user_id = int(user_id_str)
                    member = guild.get_member(user_id)
                    log.info(
                        f"[Mention Clean] guild.get_member({user_id}) result: {member}"
                    )

                    if member:
                        replacement = f"{member.display_name}<{user_id}>"
                        log.info(
                            f"[Mention Clean] Found member '{member.display_name}'. Replacing with: '{replacement}'"
                        )
                        return replacement
                    else:
                        log.warning(
                            f"[Mention Clean] Could not find member with ID {user_id} in guild '{guild.name}'."
                        )
                        replacement = f"未知用户<{user_id}>"
                        log.info(f"[Mention Clean] Replacing with: '{replacement}'")
                        return replacement
                except ValueError:
                    log.error(
                        f"[Mention Clean] Could not convert matched group '{user_id_str}' to an integer. Original match: {match.group(0)}"
                    )
                    return match.group(
                        0
                    )  # Return the original mention if conversion fails

            content = re.sub(r"<@!?(\d+)>", replace_mention, content)
            log.info(f"[Mention Clean] Content after replacement: '{content}'")
        else:
            log.warning(
                "[Mention Clean] No guild object provided, skipping mention replacement."
            )

        log.info("[Mention Clean] ----- End Mention Cleaning -----")

        # 4. 移除自定义表情符号 (例如 <:name:id> 或 <a:name:id>)
        content = re.sub(r"<a?:\w+:\d+>", "", content)

        # 5. 使用新的清理函数，清理用户输入中的所有指定括号
        # content = regex_service.clean_user_input(content)

        return content.strip()

    async def clear_user_context(self, user_id: int, guild_id: int):
        """清除指定用户的对话上下文"""
        await chat_db_manager.clear_ai_conversation_context(user_id, guild_id)
        log.info(f"已清除用户 {user_id} 在服务器 {guild_id} 的对话上下文")


# 全局实例
context_service = ContextService()
