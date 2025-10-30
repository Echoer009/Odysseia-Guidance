# -*- coding: utf-8 -*-

import discord
import logging
from typing import List, Dict, Any, Optional, Tuple
import re
import asyncio
import aiohttp

from src.chat.services.regex_service import regex_service
from src import config
from src.chat.config import chat_config

log = logging.getLogger(__name__)

# 定义一个正则表达式来匹配自定义表情
# <a:emoji_name:emoji_id> (动态) 或 <:emoji_name:emoji_id> (静态)
EMOJI_REGEX = re.compile(r"<a?:(\w+):(\d+)>")


class MessageProcessor:
    """
    负责处理和解析 discord.Message 对象，提取用于 AI 对话所需的信息。
    """

    async def _fetch_image_aio(
        self, session: aiohttp.ClientSession, url: str, proxy: Optional[str] = None
    ) -> Optional[bytes]:
        """下载图片"""
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5), proxy=proxy
            ) as response:
                response.raise_for_status()
                return await response.read()
        except asyncio.TimeoutError:
            log.warning(f"下载表情图片超时: {url}")
            return None
        except aiohttp.ClientError as e:
            log.warning(f"下载表情图片失败: {url}, 错误: {e}")
            return None

    async def _extract_emojis_as_images(
        self, content: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """从文本中提取自定义表情，下载图片，并用占位符替换文本"""
        emoji_images = []
        tasks = []
        matches = list(EMOJI_REGEX.finditer(content))

        if not matches:
            return content, []

        proxy_url = config.PROXY_URL
        async with aiohttp.ClientSession() as session:
            for match in matches:
                emoji_name, emoji_id = match.groups()
                extension = "gif" if match.group(0).startswith("<a:") else "png"
                url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}"
                tasks.append(
                    asyncio.create_task(
                        self._fetch_image_aio(session, url, proxy=proxy_url)
                    )
                )

            results = await asyncio.gather(*tasks)

        modified_content = content
        for match, image_bytes in zip(matches, results):
            if image_bytes:
                emoji_name = match.group(1)
                mime_type = (
                    "image/gif" if match.group(0).startswith("<a:") else "image/png"
                )
                emoji_images.append(
                    {
                        "mime_type": mime_type,
                        "data": image_bytes,
                        "source": "emoji",
                        "name": emoji_name,
                    }
                )
                modified_content = modified_content.replace(
                    match.group(0), f"__EMOJI_{emoji_name}__", 1
                )

        return modified_content, emoji_images

    async def process_message(
        self, message: discord.Message, bot: discord.Client
    ) -> Optional[Dict[str, Any]]:
        """
        处理传入的 discord 消息对象。
        如果消息来自一个不应被触发的频道（如永久面板或置顶帖子），则返回 None。
        """
        # --- 置顶帖诊断日志 ---
        channel = message.channel
        is_thread = isinstance(channel, discord.Thread)
        is_pinned = False
        if is_thread:
            is_pinned = channel.flags.pinned

        log.info("--- 置顶帖检查 (message_processor) ---")
        log.info(f"频道名称: {channel.name} (ID: {channel.id})")
        log.info(f"频道类型是否为 Thread: {is_thread}")
        if is_thread:
            log.info(f"Thread Flags: {channel.flags}")
            log.info(f"是否检测到 Pinned Flag: {is_pinned}")
        log.info("------------------------------------")

        # 检查消息是否来自置顶帖子
        if is_thread and is_pinned:
            log.info(f"判定为置顶帖消息，已忽略。")
            return None

        # 检查消息是否来自配置中禁用的频道
        if message.channel.id in chat_config.DISABLED_INTERACTION_CHANNEL_IDS:
            log.debug(f"消息来自禁用的频道 {message.channel.name}，已忽略。")
            return None

        image_data_list = []
        bot_user = message.guild.me

        if message.attachments:
            image_data_list.extend(
                await self._extract_images_from_attachments(message.attachments)
            )

        replied_message_content = ""
        if message.reference and message.reference.message_id:
            try:
                ref_msg = await message.channel.fetch_message(
                    message.reference.message_id
                )
                if ref_msg:
                    # 核心修复：使用 'in' 和 '[]' 来访问 MessageSnapshot 的数据
                    if (
                        hasattr(ref_msg, "message_snapshots")
                        and ref_msg.message_snapshots
                    ):
                        log.debug(f"检测到消息快照，处理转发消息: {ref_msg.id}")
                        snapshot_content_parts = []

                        forwarder_name = ref_msg.author.display_name
                        original_author_name = "未知作者"

                        for snapshot in ref_msg.message_snapshots:
                            # 根据 discord.py 文档，MessageSnapshot 是一个对象，必须使用属性访问。
                            # 我们使用 hasattr() 来安全地检查属性是否存在。
                            if hasattr(snapshot, "author") and snapshot.author:
                                # snapshot.author 是一个 User/Member 对象，它有 display_name 属性
                                original_author_name = snapshot.author.display_name

                            if hasattr(snapshot, "content") and snapshot.content:
                                snapshot_content_parts.append(snapshot.content)

                            if hasattr(snapshot, "embeds") and snapshot.embeds:
                                for embed in snapshot.embeds:
                                    # embed 是一个 Embed 对象
                                    if embed.title:
                                        snapshot_content_parts.append(
                                            f"标题: {embed.title}"
                                        )
                                    if embed.description:
                                        snapshot_content_parts.append(
                                            f"描述: {embed.description}"
                                        )
                                    for field in embed.fields:
                                        snapshot_content_parts.append(
                                            f"{field.name}: {field.value}"
                                        )

                            if (
                                hasattr(snapshot, "attachments")
                                and snapshot.attachments
                            ):
                                # snapshot.attachments 是 Attachment 对象的列表
                                image_data_list.extend(
                                    await self._extract_images_from_attachments(
                                        snapshot.attachments
                                    )
                                )

                        snapshot_full_text = "\n".join(
                            filter(None, snapshot_content_parts)
                        ).strip()
                        if snapshot_full_text:
                            lines = snapshot_full_text.split("\n")
                            formatted_quote = "\n> ".join(lines)
                            reply_header = f"> [{forwarder_name} 转发的来自 {original_author_name} 的消息]:"
                            replied_message_content = (
                                f"{reply_header}\n> {formatted_quote}\n\n"
                            )

                    else:
                        # 对非转发消息（包括embed命令）的常规处理
                        command_name = None
                        if ref_msg.embeds:
                            for embed in ref_msg.embeds:
                                if embed.footer and embed.footer.text:
                                    footer_text = embed.footer.text
                                    if "投喂" in footer_text:
                                        command_name = "/投喂"
                                    elif "忏悔" in footer_text:
                                        command_name = "/忏悔"
                                    break  # 找到一个就够了

                        embed_texts = []
                        if ref_msg.embeds:
                            for embed in ref_msg.embeds:
                                if embed.author and embed.author.name:
                                    author_label = (
                                        "投喂者"
                                        if command_name == "/投喂"
                                        else "忏悔者"
                                        if command_name == "/忏悔"
                                        else "作者"
                                    )
                                    embed_texts.append(
                                        f"{author_label}: {embed.author.name}"
                                    )
                                if embed.title:
                                    embed_texts.append(f"标题: {embed.title}")
                                if embed.description:
                                    embed_texts.append(f"描述: {embed.description}")
                                # 根据要求，不再将 embed 中的图片链接作为文本添加到上下文中
                                # if embed.image and embed.image.url: embed_texts.append(f"[图片]: {embed.image.url}")
                                for field in embed.fields:
                                    embed_texts.append(f"{field.name}: {field.value}")
                                if embed.footer and embed.footer.text:
                                    embed_texts.append(f"页脚: {embed.footer.text}")

                        embed_content = "\n".join(embed_texts)
                        ref_content_cleaned = self._clean_message_content(
                            ref_msg.content, ref_msg.mentions, bot_user
                        )

                        full_ref_content = [
                            ref for ref in [ref_content_cleaned, embed_content] if ref
                        ]
                        combined_content = "\n".join(full_ref_content).strip()

                        if combined_content:
                            lines = combined_content.split("\n")
                            formatted_quote = "\n> ".join(lines)

                            reply_header = ""
                            # 修复: ref_msg.embeds 是一个列表，我们应该从列表的第一个元素获取 author
                            embed_author_name = (
                                ref_msg.embeds[0].author.name
                                if ref_msg.embeds and ref_msg.embeds[0].author
                                else None
                            )

                            if ref_msg.author.id == bot_user.id and embed_author_name:
                                command_context = (
                                    f"的 {command_name} 回应"
                                    if command_name
                                    else "的回应"
                                )
                                reply_header = f"> [类脑娘对 {embed_author_name} {command_context}]:"
                            else:
                                reply_header = f"> [{ref_msg.author.display_name}]:"

                            replied_message_content = (
                                f"{reply_header}\n> {formatted_quote}\n\n"
                            )

                        if ref_msg.attachments:
                            image_data_list.extend(
                                await self._extract_images_from_attachments(
                                    ref_msg.attachments
                                )
                            )

            except (discord.NotFound, discord.Forbidden):
                log.warning(
                    f"无法找到或无权访问被回复的消息 ID: {message.reference.message_id}"
                )
            except Exception as e:
                log.error(f"处理被回复消息时出错: {e}", exc_info=True)

        content_with_placeholders, emoji_images = await self._extract_emojis_as_images(
            message.content
        )
        image_data_list.extend(emoji_images)

        clean_content = self._clean_message_content(
            content_with_placeholders, message.mentions, bot_user
        )

        return {
            "user_content": clean_content,
            "replied_content": replied_message_content,
            "image_data_list": image_data_list,
        }

    async def _extract_images_from_attachments(
        self, attachments: List[discord.Attachment]
    ) -> List[Dict[str, Any]]:
        """从附件列表中提取图片数据。"""
        image_data_list = []
        for attachment in attachments:
            if attachment.content_type and attachment.content_type.startswith("image/"):
                try:
                    image_bytes = await attachment.read()
                    if image_bytes:
                        image_data_list.append(
                            {
                                "mime_type": attachment.content_type,
                                "data": image_bytes,
                                "source": "attachment",
                            }
                        )
                        log.debug(
                            f"成功读取图片附件: {attachment.filename}, 大小: {len(image_bytes)} 字节"
                        )
                except Exception as e:
                    log.error(f"读取图片附件 {attachment.filename} 时出错: {e}")
        return image_data_list

    def _clean_message_content(
        self, content: str, mentions: list, bot_user: discord.ClientUser
    ) -> str:
        """
        清理消息内容，将对自身的@mention替换为名字，并移除其他@mention。
        """
        content = content.replace("\\_", "_")

        for user in mentions:
            mention_str_1 = f"<@{user.id}>"
            mention_str_2 = f"<@!{user.id}>"
            if user.id == bot_user.id:
                replacement = f"@{bot_user.display_name}"
                content = content.replace(mention_str_1, replacement).replace(
                    mention_str_2, replacement
                )
            else:
                content = content.replace(mention_str_1, "").replace(mention_str_2, "")

        content = regex_service.clean_user_input(content)
        content = content.strip()

        return content


# 创建一个单例
message_processor = MessageProcessor()
