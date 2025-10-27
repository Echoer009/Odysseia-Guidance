# -*- coding: utf-8 -*-

import discord
from typing import Optional, Dict

import re

from src import config
from typing import List, Tuple, Union


def create_embed_from_template_data(
    data: Dict, channel: Optional[discord.abc.GuildChannel] = None, **format_args
) -> discord.Embed:
    """根据单个消息字典创建 Embed。"""
    # 替换所有文本字段中的占位符
    title_template = data.get("title", "")

    # 如果提供了频道，优先替换频道名称占位符
    if channel:
        title_template = title_template.replace(
            "CHANNEL_NAME_PLACEHOLDER", channel.name
        )

    title = title_template.format(**format_args)
    description_template = data.get("description", "")

    # [BUGFIX] 手动处理换行符，因为 .format() 不会解析字符串内的转义字符
    description = description_template.format(**format_args).replace("\\n", "\n")
    footer_text = (
        (data.get("footer") or data.get("footer_text", ""))
        .format(**format_args)
        .replace("\\n", "\n")
    )
    image_url = (data.get("image_url") or "").format(**format_args)
    thumbnail_url = (data.get("thumbnail_url") or "").format(**format_args)

    embed = discord.Embed(
        title=title, description=description, color=config.EMBED_COLOR_PRIMARY
    )

    if footer_text.strip():
        embed.set_footer(text=footer_text.strip())

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    elif format_args.get("server_icon"):
        embed.set_thumbnail(url=format_args["server_icon"])

    if image_url:
        embed.set_image(url=image_url)

    return embed


def create_embed_from_template(
    template_data: Optional[Union[Dict, List[Dict]]],
    guild: discord.Guild,
    user: Optional[discord.User] = None,
    channel: Optional[discord.abc.GuildChannel] = None,
    template_name: Optional[str] = None,
    **kwargs,
) -> Tuple[discord.Embed, Optional[discord.ui.View]]:
    """
    一个辅助函数，用于从数据库模板创建 Embed 和可选的 View。
    返回 (embed, view) 元组。
    """
    if not template_data:
        embed = discord.Embed(
            title="配置缺失",
            description="管理员尚未配置此消息模板。",
            color=config.EMBED_COLOR_PRIMARY,
        )
        return embed, None

    format_args = {
        "server_name": guild.name,
        "server_icon": str(guild.icon.url) if guild.icon else "",
        "user_name": user.display_name if user else "",
        "user_mention": user.mention if user else "",
        "user_avatar": str(user.display_avatar.url) if user else "",
        "template_name": template_name,
        **kwargs,
    }
    # 确保所有值都是字符串
    format_args = {k: str(v) if v is not None else "" for k, v in format_args.items()}

    if isinstance(template_data, list):
        # 多消息模板
        from src.guidance.ui.views.message_cycler import MessageCycleView

        if not template_data:  # 如果列表为空
            embed = discord.Embed(
                title="配置为空",
                description="此多消息模板为空。",
                color=config.EMBED_COLOR_PRIMARY,
            )
            return embed, None

        initial_embed = create_embed_from_template_data(
            template_data[0], channel=channel, **format_args
        )
        view = MessageCycleView(
            messages=template_data, format_args=format_args, channel=channel
        )
        return initial_embed, view
    else:
        # 单消息模板
        embed = create_embed_from_template_data(
            template_data, channel=channel, **format_args
        )
        return embed, None
