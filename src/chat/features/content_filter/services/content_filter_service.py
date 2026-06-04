# -*- coding: utf-8 -*-

import json
import logging
from typing import List, Tuple

import discord

from src.config import DEVELOPER_USER_IDS, EMBED_COLOR_ERROR
from src.chat.config.chat_config import CONTENT_FILTER_BASE_KEYWORDS
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)

_CUSTOM_KEYWORDS_CACHE: List[str] = []
_CUSTOM_KEYWORDS_LOADED = False


async def _load_custom_keywords() -> List[str]:
    global _CUSTOM_KEYWORDS_CACHE, _CUSTOM_KEYWORDS_LOADED
    if not _CUSTOM_KEYWORDS_LOADED:
        raw = await chat_db_manager.get_global_setting("content_filter_keywords")
        if raw:
            try:
                _CUSTOM_KEYWORDS_CACHE = json.loads(raw)
            except json.JSONDecodeError:
                _CUSTOM_KEYWORDS_CACHE = []
                log.warning("自定义关键词 JSON 解析失败，已重置为空列表")
        else:
            _CUSTOM_KEYWORDS_CACHE = []
        _CUSTOM_KEYWORDS_LOADED = True
    return _CUSTOM_KEYWORDS_CACHE


def _invalidate_cache():
    global _CUSTOM_KEYWORDS_LOADED
    _CUSTOM_KEYWORDS_LOADED = False


async def get_all_keywords() -> List[str]:
    custom = await _load_custom_keywords()
    merged = list(CONTENT_FILTER_BASE_KEYWORDS) + custom
    seen = set()
    result = []
    for kw in merged:
        key = kw.lower()
        if key not in seen:
            seen.add(key)
            result.append(kw)
    return result


def check_content(text: str, keywords: List[str]) -> Tuple[bool, List[str]]:
    if not text:
        return False, []
    text_lower = text.lower()
    matched = []
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    return bool(matched), matched


async def send_developer_alert(
    bot: discord.Client,
    message: discord.Message,
    flagged_text: str,
    matched_keywords: List[str],
    source: str,
):
    try:
        before_messages = []
        try:
            async for msg in message.channel.history(
                before=message, limit=10
            ):
                before_messages.append(msg)
            before_messages.reverse()
        except discord.Forbidden:
            pass

        embed = _build_alert_embed(
            message, flagged_text, matched_keywords, source, before_messages
        )

        user_id_for_view = message.author.id
        guild_id_for_view = message.guild.id if message.guild else 0
        from src.chat.features.content_filter.ui.filter_alert_view import (
            FilterAlertView,
        )

        for dev_id in DEVELOPER_USER_IDS:
            try:
                dev = await bot.fetch_user(dev_id)
                if dev:
                    view = FilterAlertView(
                        user_id=user_id_for_view,
                        guild_id=guild_id_for_view,
                        bot=bot,
                    )
                    await dev.send(embed=embed, view=view)
            except discord.Forbidden:
                log.warning(f"无法向开发者 {dev_id} 发送私信报警")
            except discord.NotFound:
                log.warning(f"开发者用户 {dev_id} 未找到")
            except Exception as e:
                log.error(f"向开发者 {dev_id} 发送报警时出错: {e}")

        log.info(
            f"文爱检测报警已发送: 用户={message.author.id}, "
            f"来源={source}, 关键词={matched_keywords}"
        )
    except Exception as e:
        log.error(f"发送开发者报警时发生错误: {e}", exc_info=True)


def _build_alert_embed(
    message: discord.Message,
    flagged_text: str,
    matched_keywords: List[str],
    source: str,
    before_messages: List[discord.Message],
) -> discord.Embed:
    user = message.author
    guild = message.guild
    channel = message.channel

    embed = discord.Embed(
        title="🚨 文爱检测警报",
        description=f"检测到对话内容可能超出限制。来源：**{source}**",
        color=EMBED_COLOR_ERROR,
        timestamp=message.created_at,
    )

    user_info_lines = [
        f"**用户ID:** {user.id}",
        f"**用户名:** {user.name}",
        f"**显示名称:** {user.display_name}",
    ]
    if guild:
        user_info_lines.append(f"**服务器:** {guild.name} ({guild.id})")
    if isinstance(channel, discord.abc.GuildChannel):
        user_info_lines.append(f"**频道:** {channel.name} ({channel.id})")
    embed.add_field(name="👤 用户信息", value="\n".join(user_info_lines), inline=False)

    embed.add_field(
        name="🔑 命中关键词",
        value=", ".join(f"`{kw}`" for kw in matched_keywords)
        if matched_keywords
        else "无",
        inline=False,
    )

    embed.add_field(
        name="📝 标记内容",
        value=flagged_text[:1024] if len(flagged_text) <= 1024 else flagged_text[:1020] + "...",
        inline=False,
    )

    context_lines = []
    for m in before_messages:
        prefix = "🤖" if m.author.bot else "👤"
        context_lines.append(
            f"{prefix} **{m.author.display_name}**: {m.content[:150]}"
        )
    context_lines.append(
        f"🟡 **{user.display_name}** (本条): {flagged_text[:150]}"
    )
    if context_lines:
        embed.add_field(
            name=f"📋 上下文 (前{len(before_messages)}条 + 当前)",
            value="\n".join(context_lines),
            inline=False,
        )

    channel_ref = channel.mention if isinstance(channel, discord.abc.GuildChannel) else "未知频道"
    embed.add_field(
        name="🔗 跳转",
        value=f"[点击跳转到消息]({message.jump_url})  |  {channel_ref}",
        inline=False,
    )

    embed.set_footer(text="防文爱系统 · 请及时处理")
    if user.avatar:
        embed.set_thumbnail(url=user.avatar.url)

    return embed
