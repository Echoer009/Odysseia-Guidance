# -*- coding: utf-8 -*-

import logging
from typing import List, Tuple

import discord
from sqlalchemy import select, update as sa_update, delete as sa_delete

from src.config import DEVELOPER_USER_IDS, EMBED_COLOR_ERROR
from src.database.database import AsyncSessionLocal
from src.database.models import ContentFilterKeyword

log = logging.getLogger(__name__)

_KEYWORDS_CACHE: List[str] = []
_KEYWORDS_LOADED = False


async def _load_active_keywords() -> List[str]:
    global _KEYWORDS_CACHE, _KEYWORDS_LOADED
    if not _KEYWORDS_LOADED:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ContentFilterKeyword.keyword).where(
                    ContentFilterKeyword.is_ignored == 0
                )
            )
            _KEYWORDS_CACHE = [row[0] for row in result.all()]
        _KEYWORDS_LOADED = True
    return _KEYWORDS_CACHE


def _invalidate_cache():
    global _KEYWORDS_LOADED
    _KEYWORDS_LOADED = False


async def get_all_keywords() -> List[str]:
    return await _load_active_keywords()


def check_content(text: str, keywords: List[str]) -> Tuple[bool, List[str]]:
    if not text:
        return False, []
    text_lower = text.lower()
    matched = []
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    return bool(matched), matched


async def add_keyword(keyword: str) -> bool:
    kw = keyword.strip().lower()
    if not kw:
        return False
    async with AsyncSessionLocal() as session:
        exists = await session.execute(
            select(ContentFilterKeyword).where(
                ContentFilterKeyword.keyword == kw
            )
        )
        if exists.scalar_one_or_none():
            return False
        session.add(ContentFilterKeyword(keyword=kw, is_ignored=0))
        await session.commit()
    _invalidate_cache()
    log.info(f"已添加关键词: {kw}")
    return True


async def remove_keyword(keyword: str) -> bool:
    kw = keyword.strip().lower()
    async with AsyncSessionLocal() as session:
        exists = await session.execute(
            select(ContentFilterKeyword.keyword).where(
                ContentFilterKeyword.keyword == kw
            )
        )
        if not exists.scalar_one_or_none():
            return False
        await session.execute(
            sa_delete(ContentFilterKeyword).where(
                ContentFilterKeyword.keyword == kw
            )
        )
        await session.commit()
    _invalidate_cache()
    log.info(f"已删除关键词: {kw}")
    return True


async def ignore_keywords(keywords: List[str]):
    normalized = [kw.strip().lower() for kw in keywords]
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa_update(ContentFilterKeyword)
            .where(ContentFilterKeyword.keyword.in_(normalized))
            .values(is_ignored=1)
        )
        await session.commit()
    _invalidate_cache()
    log.info(f"已忽略关键词: {keywords}")


async def unignore_keyword(keyword: str):
    kw = keyword.strip().lower()
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa_update(ContentFilterKeyword)
            .where(ContentFilterKeyword.keyword == kw)
            .values(is_ignored=0)
        )
        await session.commit()
    _invalidate_cache()
    log.info(f"已恢复关键词: {kw}")


async def get_all_keywords_with_status() -> List[Tuple[str, bool]]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(
                ContentFilterKeyword.keyword,
                ContentFilterKeyword.is_ignored,
            ).order_by(ContentFilterKeyword.keyword)
        )
        return [(row[0], bool(row[1])) for row in result.all()]


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
                        matched_keywords=matched_keywords,
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
