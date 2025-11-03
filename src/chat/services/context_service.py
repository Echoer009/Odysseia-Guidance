# -*- coding: utf-8 -*-

import logging
from typing import Optional, Dict, List
import discord  # 导入discord模块
import re  # 导入正则表达式模块
from src import config
from src.chat.config import chat_config  # 导入 chat_config
from src.chat.utils.database import chat_db_manager
from src.chat.services.regex_service import regex_service

log = logging.getLogger(__name__)


class ContextService:
    """上下文管理服务，处理用户个人上下文和频道全局上下文"""

    def __init__(self):
        self.bot = None  # 初始化时bot实例为空

    def set_bot_instance(self, bot: "discord.ext.commands.Bot"):
        """设置bot实例，以便访问Discord API"""
        self.bot = bot
        log.info("ContextService 已设置 bot 实例。")

    async def get_user_conversation_history(
        self, user_id: int, guild_id: int
    ) -> List[Dict]:
        """从数据库获取用户的对话历史（5轮）"""
        context = await chat_db_manager.get_ai_conversation_context(user_id, guild_id)
        if context and context.get("conversation_history"):
            return context["conversation_history"]
        return []

    async def update_user_conversation_history(
        self, user_id: int, guild_id: int, user_message: str, ai_response: str
    ):
        """更新用户的对话历史到数据库（5轮）"""
        current_history = await self.get_user_conversation_history(user_id, guild_id)

        # 添加上一轮对话
        current_history.append({"role": "user", "parts": [user_message]})
        current_history.append({"role": "model", "parts": [ai_response]})

        # 限制上下文长度，保留最近5轮对话
        if len(current_history) > 10:  # 5轮对话 (每轮2条消息)
            current_history = current_history[-10:]

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
    ) -> List[Dict[str, any]]:
        """
        获取结构化的频道对话历史，用于构建多轮对话请求。
        此方法会合并连续的用户消息，以符合 user/model 交替的API格式。
        如果数据库中存在记忆锚点，则只获取该锚点之后的消息。

        Args:
            channel_id (int): 频道ID。
            limit (int): 获取的消息数量上限。
            exclude_message_id (Optional[int]): 需要从历史记录中排除的特定消息ID。
        """
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
            # 检查是否存在记忆锚点
            guild_id = channel.guild.id if channel.guild else 0
            anchor_message_id = await chat_db_manager.get_channel_memory_anchor(
                guild_id, channel_id
            )

            after_message = None
            fetch_limit = limit
            if anchor_message_id:
                try:
                    after_message = discord.Object(id=anchor_message_id)
                    # 增加 limit 以确保在锚点之后的第一条消息也能被捕获
                    fetch_limit = limit + 1
                    log.info(
                        f"找到频道 {channel_id} 的记忆锚点: {anchor_message_id}，将从此消息之后开始获取历史。"
                    )
                except Exception as e:
                    log.error(
                        f"创建 discord.Object 失败，锚点ID {anchor_message_id} 可能无效: {e}"
                    )

            # 使用 after 参数获取历史记录，返回的是从旧到新
            history_messages = [
                msg
                async for msg in channel.history(limit=fetch_limit, after=after_message)
            ]

            # 只有在没有使用 'after' (即从最新消息开始获取) 时，返回的列表才是从新到旧的，才需要反转。
            # 使用 'after' 时，列表已经是从旧到新了。
            if not after_message:
                history_messages.reverse()

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

                if msg.author.id == self.bot.user.id or (
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
        if guild:

            def replace_mention(match):
                user_id = int(match.group(1))
                member = guild.get_member(user_id)
                return f"@{member.display_name}" if member else "@未知用户"

            content = re.sub(r"<@!?(\d+)>", replace_mention, content)

        # 4. 移除自定义表情符号 (例如 <:name:id> 或 <a:name:id>)
        content = re.sub(r"<a?:\w+:\d+>", "", content)

        # 5. 使用新的清理函数，清理用户输入中的所有指定括号
        content = regex_service.clean_user_input(content)

        return content.strip()

    async def clear_user_context(self, user_id: int, guild_id: int):
        """清除指定用户的对话上下文"""
        await chat_db_manager.clear_ai_conversation_context(user_id, guild_id)
        log.info(f"已清除用户 {user_id} 在服务器 {guild_id} 的对话上下文")


# 全局实例
context_service = ContextService()
