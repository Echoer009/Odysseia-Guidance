import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import discord
from discord.http import Route
from src.chat.utils.time_utils import BEIJING_TZ
from src.chat.features.tools.tool_metadata import tool_metadata


def _format_search_results(messages: List[Dict]) -> List[Dict[str, Any]]:
    """Helper to format messages from the search API."""
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
    description="翻翻之前的聊天记录～可以在当前频道或者整个服务器里搜关键词！",
    emoji="📜",
    category="查询",
)
async def search_channel_history(
    query: str,
    **kwargs,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    并行地在当前频道和整个服务器中搜索历史消息，并合并返回结果。

    [调用指南]
    - **自主决策**: 当需要全面查找信息时调用，它会同时搜索精确频道和整个服务器。
    - **定义查询**: 使用 `query` 参数指定搜索的关键词。

    Args:
        query (str): 要在消息内容中搜索的文本。

    Returns:
        一个字典，包含来自频道和服务器的合并、去重后的搜索结果。
    """
    bot = kwargs.get("bot")
    guild_id = kwargs.get("guild_id")
    channel_id = kwargs.get("channel_id")

    if not bot or not guild_id:
        logging.error("机器人实例或服务器ID在上下文中不可用。")
        return {"channel_results": [], "guild_results": []}

    # --- 并行执行频道和服务器搜索 ---
    # 仅当 channel_id 可用时，才执行频道搜索
    if channel_id:
        channel_search_task = asyncio.create_task(
            _execute_search(bot, query, guild_id, channel_id)
        )
    else:
        channel_search_task = asyncio.create_task(
            asyncio.sleep(0, result=[])
        )  # 返回空结果

    guild_search_task = asyncio.create_task(_execute_search(bot, query, guild_id))

    channel_results, guild_results = await asyncio.gather(
        channel_search_task, guild_search_task
    )

    # --- 合并与去重 ---
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
    """Executes a single search request against the Discord API."""
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
        logging.error(f"没有在 {scope} 中搜索消息的权限。")
        return []
    except Exception as e:
        scope = f"频道 {channel_id}" if channel_id else f"服务器 {guild_id}"
        logging.error(f"在 {scope} 中搜索时发生未知错误: {e}")
        return []


# Metadata for the tool
SEARCH_CHANNEL_HISTORY_TOOL = {
    "type": "function",
    "function": {
        "name": "search_channel_history",
        "description": "在当前频道和整个服务器中并行搜索消息历史，并返回合并后的结果。自然的用得到结果回复",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要在消息内容中搜索的文本。"}
            },
            "required": ["query"],
        },
    },
}
