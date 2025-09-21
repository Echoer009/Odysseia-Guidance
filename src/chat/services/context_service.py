# -*- coding: utf-8 -*-

import logging
from typing import Optional, Dict, List
import discord # 导入discord模块
import re # 导入正则表达式模块
from src import config
from src.chat.config import chat_config # 导入 chat_config
from src.chat.utils.database import chat_db_manager
from src.chat.services.regex_service import regex_service
from src.chat.features.affection.service.affection_service import affection_service
from src.chat.features.world_book.services.world_book_service import world_book_service

log = logging.getLogger(__name__)

class ContextService:
    """上下文管理服务，处理用户个人上下文和频道全局上下文"""
    
    def __init__(self):
        self.bot = None # 初始化时bot实例为空
    
    def set_bot_instance(self, bot: 'discord.ext.commands.Bot'):
        """设置bot实例，以便访问Discord API"""
        self.bot = bot
        log.info("ContextService 已设置 bot 实例。")
    
    async def get_user_conversation_history(self, user_id: int, guild_id: int) -> List[Dict]:
        """从数据库获取用户的对话历史（5轮）"""
        context = await chat_db_manager.get_ai_conversation_context(user_id, guild_id)
        if context and context.get('conversation_history'):
            return context['conversation_history']
        return []
    
    async def update_user_conversation_history(self, user_id: int, guild_id: int,
                                             user_message: str, ai_response: str):
        """更新用户的对话历史到数据库（5轮）"""
        current_history = await self.get_user_conversation_history(user_id, guild_id)
        
        # 添加上一轮对话
        current_history.append({"role": "user", "parts": [user_message]})
        current_history.append({"role": "model", "parts": [ai_response]})
        
        # 限制上下文长度，保留最近5轮对话
        if len(current_history) > 10:  # 5轮对话 (每轮2条消息)
            current_history = current_history[-10:]
        
        await chat_db_manager.update_ai_conversation_context(user_id, guild_id, current_history)
    
    async def get_channel_conversation_history(self, channel_id: int, limit: int = chat_config.CHANNEL_MEMORY_CONFIG["raw_history_limit"]) -> List[Dict]:
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
                is_irrelevant_type = msg.type not in (discord.MessageType.default, discord.MessageType.reply)
                if is_irrelevant_type:
                    continue

                # 提取消息内容
                if msg.content:
                    # 净化消息内容，替换用户提及
                    # 净化消息内容，移除提及、URL和自定义表情
                    clean_content = self.clean_message_content(msg.content, msg.guild)
                    history.append({
                        "role": "user",
                        "parts": [f"{msg.author.display_name}: {clean_content}"]
                    })

            # history.flatten() 返回的是从新到旧的消息，我们需要反转列表以保持时间顺序
            return history[::-1]
        except discord.Forbidden:
            log.error(f"机器人没有权限读取频道 {channel_id} 的消息历史。")
            return []
        except Exception as e:
            log.error(f"获取频道 {channel_id} 消息历史时出错: {e}")
            return []
    
    async def get_formatted_channel_history(self, channel_id: int, user_id: int, guild_id: int, limit: int = chat_config.CHANNEL_MEMORY_CONFIG["formatted_history_limit"], exclude_message_id: Optional[int] = None) -> List[Dict[str, any]]:
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
            anchor_message_id = await chat_db_manager.get_channel_memory_anchor(guild_id, channel_id)
            
            after_message = None
            fetch_limit = limit
            if anchor_message_id:
                try:
                    after_message = discord.Object(id=anchor_message_id)
                    # 增加 limit 以确保在锚点之后的第一条消息也能被捕获
                    fetch_limit = limit + 1
                    log.info(f"找到频道 {channel_id} 的记忆锚点: {anchor_message_id}，将从此消息之后开始获取历史。")
                except Exception as e:
                    log.error(f"创建 discord.Object 失败，锚点ID {anchor_message_id} 可能无效: {e}")

            # 使用 after 参数获取历史记录，返回的是从旧到新
            history_messages = [msg async for msg in channel.history(limit=fetch_limit, after=after_message)]

            # 只有在没有使用 'after' (即从最新消息开始获取) 时，返回的列表才是从新到旧的，才需要反转。
            # 使用 'after' 时，列表已经是从旧到新了。
            if not after_message:
                history_messages.reverse()

            for msg in history_messages:
                # 根据用户要求，不再过滤任何机器人消息
                # 只过滤掉非我们关心的消息类型（保留 default 和 reply），并排除指定消息
                is_irrelevant_type = msg.type not in (discord.MessageType.default, discord.MessageType.reply)
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
                            ref_content_cleaned = self.clean_message_content(ref_msg.content, ref_msg.guild)
                            # 创建更丰富的回复信息，包括被回复的内容摘要
                            # 使用更不容易被模型模仿的括号和格式来构造回复信息
                            cleaned_reply_author_name = regex_service.clean_user_input(ref_msg.author.display_name)
                            reply_info = f'[回复 {cleaned_reply_author_name}] '
                    except (discord.NotFound, discord.Forbidden):
                        log.warning(f"无法找到或无权访问被回复的消息 ID: {msg.reference.message_id}")
                        pass # 获取失败则静默忽略

                cleaned_author_name = regex_service.clean_user_input(msg.author.display_name)

                if msg.author.id == self.bot.user.id or \
                   (config.BRAIN_GIRL_APP_ID and msg.author.id == config.BRAIN_GIRL_APP_ID):
                    # Bot的消息 (model) - 冲洗用户缓冲区，然后将消息添加到模型缓冲区
                    if user_messages_buffer:
                        history_list.append({
                            "role": "user",
                            "parts": ["\n\n".join(user_messages_buffer)]
                        })
                        user_messages_buffer = []
                    
                    bot_message_content = f'{reply_info}{cleaned_author_name}: {clean_content}'
                    model_messages_buffer.append(bot_message_content)
                else:
                    # 用户的消息 (user) - 冲洗模型缓冲区，然后将消息添加到用户缓冲区
                    if model_messages_buffer:
                        history_list.append({
                            "role": "model",
                            "parts": ["\n\n".join(model_messages_buffer)]
                        })
                        model_messages_buffer = []

                    formatted_message = f'[user]: {reply_info}{cleaned_author_name}: {clean_content}'
                    user_messages_buffer.append(formatted_message)

            # 循环结束后，如果缓冲区还有用户消息，全部作为最后一个'user'回合提交
            if user_messages_buffer:
                history_list.append({
                    "role": "user",
                    "parts": ["\n\n".join(user_messages_buffer)]
                })
            
            # 同样，如果模型缓冲区还有消息，也全部提交
            if model_messages_buffer:
                history_list.append({
                    "role": "model",
                    "parts": ["\n\n".join(model_messages_buffer)]
                })
            
            # 新增：在历史记录的末尾，注入好感度和用户档案作为对下一条用户消息的上下文提示
            affection_status = await affection_service.get_affection_status(user_id, guild_id)
            affection_level_prompt = affection_status.get("prompt", "")

            # --- 新增：获取并注入用户个人档案 ---
            user_profile_prompt = ""
            log.info(f"--- 个人档案注入诊断: 正在为用户 {user_id} 查找档案 ---")
            user_profile = world_book_service.get_profile_by_discord_id(str(user_id))
            log.info(f"--- 个人档案注入诊断: world_book_service 返回的档案: {user_profile} ---")
            if user_profile:
                # 找到档案，进行格式化
                profile_content = user_profile.get('content', {})
                if isinstance(profile_content, dict):
                    # 只有当值不为空时，才添加到列表中
                    profile_details = [f"{key}: {value}" for key, value in profile_content.items() if value and value != '未提供']
                    log.info(f"--- 个人档案注入诊断: 过滤后的档案详情: {profile_details} ---")
                    if profile_details: # 只有当列表不为空时才生成提示
                        # 使用 \n\n 来增加与好感度提示之间的间距
                        user_profile_prompt = "\n\n这是与你对话的用户的已知信息：\n" + "\n".join(profile_details)
            
            log.info(f"--- 个人档案注入诊断: 最终生成的档案提示长度: {len(user_profile_prompt)} ---")
            # 使用 \n\n 来增加与档案或好感度提示之间的间距
            model_reply = f"好的,上面是已知的历史消息,我会针对用户的最新消息进行回复。{affection_level_prompt}{user_profile_prompt}"
            
            history_list.append({
                "role": "model",
                "parts": [model_reply]
            })

            return history_list
        except discord.Forbidden:
            log.error(f"机器人没有权限读取频道 {channel_id} 的消息历史。")
            return []
        except Exception as e:
            log.error(f"获取并格式化频道 {channel_id} 消息历史时出错: {e}")
            return []
    
    def clean_message_content(self, content: str, guild: Optional[discord.Guild]) -> str:
        """
        净化消息内容，移除或替换不适合模型处理的元素。
        - 移除 Discord CDN 链接。
        - 移除自定义表情符号代码 <a:name:id> 或 <:name:id>。
        - 替换用户提及 <@USER_ID> 为 @USERNAME。
        - 清理用户输入中的所有指定括号。
        """
        # 1. 移除 Discord CDN 链接 (例如 https://cdn.discordapp.com/...)
        content = re.sub(r'https?://cdn\.discordapp\.com\S+', '', content)

        # 3. 将用户提及 <@USER_ID> 替换为 @USERNAME
        if guild:
            def replace_mention(match):
                user_id = int(match.group(1))
                member = guild.get_member(user_id)
                return f"@{member.display_name}" if member else "@未知用户"
            content = re.sub(r'<@!?(\d+)>', replace_mention, content)

        # 4. 移除自定义表情符号 (例如 <:name:id> 或 <a:name:id>)
        content = re.sub(r'<a?:\w+:\d+>', '', content)

        # 5. 使用新的清理函数，清理用户输入中的所有指定括号
        content = regex_service.clean_user_input(content)

        return content.strip()

    async def clear_user_context(self, user_id: int, guild_id: int):
        """清除指定用户的对话上下文"""
        await chat_db_manager.clear_ai_conversation_context(user_id, guild_id)
        log.info(f"已清除用户 {user_id} 在服务器 {guild_id} 的对话上下文")

# 全局实例
context_service = ContextService()