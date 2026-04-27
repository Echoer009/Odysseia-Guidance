# -*- coding: utf-8 -*-
"""
历史消息搜索工具 - 在频道或服务器中搜索历史消息
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

import discord
from discord.http import Route
from pydantic import BaseModel, Field

from src.chat.utils.time_utils import BEIJING_TZ
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


class ChannelHistoryQuery(BaseModel):
    """历史消息搜索参数"""

    query: str = Field(
        ...,
        description="要在消息内容中搜索的关键词或文本。",
    )


def _format_search_results(messages: List[Dict]) -> List[Dict[str, Any]]:
    """格式化搜索结果"""
    results = []
    for message_group in messages:
        for message_data in message_group:
            if message_data.get("hit"):
                author_data = message_data.get("author", {})

                timestamp_str = message_data.get("timestamp")
                utc_dt = datetime.fromisoformat(timestamp_str)
                beijing_dt = utc_dt.astimezone(BEIJING_TZ)

                results.append(
                    {
                        "id": message_data.get("id"),
                        "author": f"{author_data.get('username', 'N/A')}#{author_data.get('discriminator', '0000')}",
                        "content": message_data.get("content"),
                        "timestamp": beijing_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
    return results


@tool_metadata(
    name="历史消息",
    description="在当前频道或整个服务器中搜索历史消息",
    emoji="📜",
    category="查询",
)
async def search_channel_history(
    params: ChannelHistoryQuery,
    **kwargs,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    并行搜索当前频道和整个服务器的历史消息。
    """
    # 从 Pydantic 模型中提取参数
    query = params.query

    bot = kwargs.get("bot")
    guild_id = kwargs.get("guild_id")
    channel_id = kwargs.get("channel_id")

    if not bot or not guild_id:
        log.error("机器人实例或服务器ID在上下文中不可用。")
        return {"channel_results": [], "guild_results": []}

    if channel_id:
        channel_search_task = asyncio.create_task(
            _execute_search(bot, query, guild_id, channel_id)
        )
    else:
        channel_search_task = asyncio.create_task(asyncio.sleep(0, result=[]))

    guild_search_task = asyncio.create_task(_execute_search(bot, query, guild_id))

    channel_results, guild_results = await asyncio.gather(
        channel_search_task, guild_search_task
    )

    all_channel_ids = {msg["id"] for msg in channel_results}
    unique_guild_results = [
        msg for msg in guild_results if msg["id"] not in all_channel_ids
    ]

    return {
        "channel_results": channel_results,
        "guild_wide_results": unique_guild_results,
    }


async def _execute_search(
    bot, query: str, guild_id: int, channel_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """执行单个搜索请求"""
    try:
        if channel_id:
            route = Route(
                "GET", "/channels/{channel_id}/messages/search", channel_id=channel_id
            )
        else:
            route = Route(
                "GET", "/guilds/{guild_id}/messages/search", guild_id=guild_id
            )

        params = {"content": query}
        data = await bot.http.request(route, params=params)
        return _format_search_results(data.get("messages", []))

    except discord.Forbidden:
        scope = f"频道 {channel_id}" if channel_id else f"服务器 {guild_id}"
        log.error(f"没有在 {scope} 中搜索消息的权限。")
        return []
    except Exception as e:
        scope = f"频道 {channel_id}" if channel_id else f"服务器 {guild_id}"
        log.error(f"在 {scope} 中搜索时发生未知错误: {e}")
        return []
