# -*- coding: utf-8 -*-
import asyncio
import logging
import re
import time
from typing import List, Literal, Optional, Dict, Any

import discord
from discord.http import Route
from pydantic import BaseModel, Field

from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)
from src.chat.features.tutorial_search.services.tutorial_search_service import (
    tutorial_search_service,
)
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.chat.features.personal_memory.services.conversation_block_service import (
    conversation_block_service,
)
from src.chat.features.personal_memory.services.conversation_memory_search_service import (
    conversation_memory_search_service,
)
from src.chat.services.prompt_service import prompt_service
from src.chat.utils.database import chat_db_manager
from src.chat.utils.time_utils import BEIJING_TZ
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)

ALLOWED_CATEGORIES = [
    "世界书",
    "全性向",
    "其他区",
    "制卡工具区",
    "女性向",
    "工具区",
    "插件",
    "教程",
    "深渊区",
    "男性向",
    "纯净区",
    "美化",
    "预设",
    "️其它工具区",
]

CategoryName = Literal[
    "世界书",
    "全性向",
    "其他区",
    "制卡工具区",
    "女性向",
    "工具区",
    "插件",
    "教程",
    "深渊区",
    "男性向",
    "纯净区",
    "美化",
    "预设",
    "️其它工具区",
]

TUTORIAL_KEYWORDS = [
    "酒馆",
    "sillytavern",
    "教程",
    "设置",
    "安装",
    "报错",
    "类脑",
    "公益站",
    "配置",
    "怎么用",
    "如何使用",
]


class SearchParams(BaseModel):
    query: str = Field(
        ...,
        description="搜索关键词。",
    )
    scope: Literal["auto", "forum", "channel", "tutorial", "world_book", "memory"] = Field(
        default="auto",
        description=(
            "搜索范围："
            "forum=论坛帖子, channel=服务器消息历史, tutorial=教程知识库, "
            "world_book=社区成员名片和社区知识, memory=与当前用户的历史对话记忆。"
            "默认 auto 由系统自动判断最合适的数据源。"
        ),
    )
    category_name: Optional[CategoryName] = Field(
        None,
        description="论坛频道名称筛选（仅 scope 为 auto 或 forum 时生效）。",
    )
    author_id: Optional[str] = Field(
        None,
        description="作者的 Discord ID，纯数字（仅 scope 为 auto 或 forum 时生效）。",
    )
    start_date: Optional[str] = Field(
        None,
        description="开始日期，格式 YYYY-MM-DD（仅 scope 为 auto 或 forum 时生效）。",
    )
    end_date: Optional[str] = Field(
        None,
        description="结束日期，格式 YYYY-MM-DD（仅 scope 为 auto 或 forum 时生效）。",
    )
    limit: int = Field(
        default=5,
        description="每个数据源返回结果的数量限制，最多20。",
    )


def _auto_route(query: str) -> List[str]:
    return ["forum", "channel", "tutorial"]


def _format_channel_results(messages: List[Dict]) -> List[Dict[str, Any]]:
    from datetime import datetime

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


async def _execute_channel_search(
    bot, query: str, guild_id: int, channel_id: Optional[int] = None
) -> List[Dict[str, Any]]:
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
        return _format_channel_results(data.get("messages", []))
    except discord.Forbidden:
        scope = f"频道 {channel_id}" if channel_id else f"服务器 {guild_id}"
        log.error(f"没有在 {scope} 中搜索消息的权限。")
        return []
    except Exception as e:
        scope = f"频道 {channel_id}" if channel_id else f"服务器 {guild_id}"
        log.error(f"在 {scope} 中搜索时发生未知错误: {e}")
        return []


async def _search_forum(params: SearchParams, **kwargs) -> Dict[str, Any]:
    query = params.query
    limit = min(params.limit, 20)

    filter_dict = {}
    if params.category_name:
        filter_dict["category_name"] = params.category_name
    if params.author_id:
        filter_dict["author_id"] = params.author_id
    if params.start_date:
        filter_dict["start_date"] = params.start_date
    if params.end_date:
        filter_dict["end_date"] = params.end_date

    if "category_name" in filter_dict and filter_dict.get("category_name") is not None:
        category_input = filter_dict["category_name"]
        is_single_item = not isinstance(category_input, list)
        category_list = [category_input] if is_single_item else category_input

        filtered_categories = [
            cat for cat in category_list if cat in ALLOWED_CATEGORIES
        ]

        invalid_categories = [
            cat for cat in category_list if cat not in ALLOWED_CATEGORIES
        ]
        if invalid_categories:
            log.warning(
                f"自动过滤了无效的频道名称: {invalid_categories}。"
                f"允许的频道名称为: {ALLOWED_CATEGORIES}。"
            )

        if not filtered_categories:
            log.warning("所有提供的频道名称都无效，已移除 category_name 过滤器。")
            del filter_dict["category_name"]
        else:
            filter_dict["category_name"] = (
                filtered_categories[0] if is_single_item else filtered_categories
            )

    if "author_id" in filter_dict and filter_dict.get("author_id") is not None:
        author_id_input = filter_dict["author_id"]
        is_single_item = not isinstance(author_id_input, list)
        author_id_list = [author_id_input] if is_single_item else author_id_input

        processed_ids = []
        for author_id_val in author_id_list:
            if (
                isinstance(author_id_val, str)
                and author_id_val.startswith("<@")
                and author_id_val.endswith(">")
            ):
                match = re.search(r"\d+", author_id_val)
                if match:
                    author_id_val = match.group(0)
            try:
                processed_ids.append(int(author_id_val))
            except (ValueError, TypeError) as e:
                log.error(f"无法将 author_id '{author_id_val}' 转换为整数: {e}")
                return {
                    "results": [],
                    "error": "提供的作者ID列表中包含无法处理的格式。",
                }

        filter_dict["author_id"] = processed_ids if is_single_item else processed_ids

    if query is None and "query" in filter_dict:
        query = filter_dict.pop("query", None)

    if not (query and query.strip()) and not filter_dict:
        return {"results": [], "error": "需要提供一个关键词或者至少一个筛选条件。"}

    if not forum_search_service.is_ready():
        return {"results": [], "error": "论坛搜索服务当前不可用，请稍后再试。"}

    await chat_db_manager.increment_forum_search_count()

    start_time = time.monotonic()
    safe_query = query if query is not None else ""
    results = await forum_search_service.search(
        safe_query, n_results=limit, filters=filter_dict, use_hybrid=True
    )
    duration = time.monotonic() - start_time
    log.info(f"forum_search_service.search 调用完成, 耗时: {duration:.4f} 秒。")

    if not results:
        return {"results": []}

    processed_thread_ids = set()
    output_list = []
    for result in results:
        metadata = result.get("metadata", {})
        thread_id = metadata.get("thread_id")

        if not thread_id or thread_id in processed_thread_ids:
            continue

        category_name = metadata.get("category_name", "未知论坛")
        guild_id = metadata.get("guild_id")

        if guild_id:
            thread_url = f"https://discord.com/channels/{guild_id}/{thread_id}"
            output_string = f"{category_name} > {thread_url}"
            output_list.append(output_string)
            processed_thread_ids.add(thread_id)
            if len(processed_thread_ids) >= limit:
                break
        else:
            log.warning(f"元数据缺少 guild_id，无法为帖子 {thread_id} 创建链接。")

    return {"results": output_list}


async def _search_channel(params: SearchParams, **kwargs) -> Dict[str, Any]:
    query = params.query
    if not query or not query.strip():
        return {"results": [], "error": "频道搜索需要提供关键词。"}

    bot = kwargs.get("bot")
    guild_id = kwargs.get("guild_id")
    channel = kwargs.get("channel")
    channel_id = channel.id if channel else kwargs.get("channel_id")

    if not bot or not guild_id:
        log.error("机器人实例或服务器ID在上下文中不可用。")
        return {"results": []}

    int_guild_id = int(guild_id) if isinstance(guild_id, str) else guild_id
    int_channel_id = (
        int(channel_id) if channel_id and isinstance(channel_id, str) else channel_id
    )

    tasks = []
    task_names = []

    if int_channel_id:
        tasks.append(_execute_channel_search(bot, query, int_guild_id, int_channel_id))
        task_names.append("channel")
    tasks.append(_execute_channel_search(bot, query, int_guild_id))
    task_names.append("guild")

    results_list = await asyncio.gather(*tasks)

    channel_results = []
    guild_results = []

    for name, result in zip(task_names, results_list):
        if name == "channel":
            channel_results = result
        else:
            guild_results = result

    all_channel_ids = {msg["id"] for msg in channel_results}
    unique_guild_results = [
        msg for msg in guild_results if msg["id"] not in all_channel_ids
    ]

    combined = channel_results + unique_guild_results
    return {"results": combined}


async def _search_tutorial(params: SearchParams, **kwargs) -> Dict[str, Any]:
    query = params.query
    if not query or not query.strip():
        return {"results": [], "error": "教程搜索需要提供关键词。"}

    user_id = kwargs.get("user_id", "N/A")
    thread_id = kwargs.get("thread_id")

    docs = await tutorial_search_service.search(
        query, user_id=str(user_id), thread_id=thread_id
    )

    formatted_context = prompt_service.format_tutorial_context(docs, thread_id)

    return {"results": formatted_context}


async def _search_world_book(params: SearchParams, **kwargs) -> Dict[str, Any]:
    query = params.query
    if not query or not query.strip():
        return {"results": [], "error": "社区知识搜索需要提供关键词。"}

    user_id = kwargs.get("user_id")
    guild_id = kwargs.get("guild_id")
    if not user_id or not guild_id:
        return {"results": [], "error": "缺少用户或服务器信息。"}

    user_name = kwargs.get("user_name", "用户")
    channel_context = kwargs.get("channel_context")

    if not world_book_service.is_ready():
        return {"results": [], "error": "社区知识搜索服务当前不可用，请稍后再试。"}

    entries = await world_book_service.find_entries(
        latest_query=query,
        user_id=int(user_id),
        guild_id=int(guild_id),
        user_name=user_name,
        conversation_history=channel_context,
    )

    if entries:
        formatted = prompt_service._format_world_book_entries(entries, user_name)
        return {"results": formatted}
    return {"results": []}


async def _search_memory(params: SearchParams, **kwargs) -> Dict[str, Any]:
    query = params.query
    if not query or not query.strip():
        return {"results": [], "error": "历史记忆搜索需要提供关键词。"}

    user_id = kwargs.get("user_id")
    if not user_id:
        return {"results": [], "error": "缺少用户信息。"}

    user_id = str(user_id)

    latest_block_id = await conversation_block_service.get_latest_block_id(user_id)
    exclude_block_ids = [latest_block_id] if latest_block_id else None

    blocks = await conversation_memory_search_service.search(
        discord_id=user_id,
        query=query,
        exclude_block_ids=exclude_block_ids,
    )

    if blocks:
        formatted = conversation_memory_search_service.format_blocks_for_context(blocks)
        log.info(f"[search/memory] 检索到 {len(blocks)} 个相关对话记忆块")
        return {"results": formatted}
    return {"results": []}


@tool_metadata(
    name="搜索",
    description="搜索社区论坛帖子、服务器消息历史、教程知识库、社区成员名片与知识、历史对话记忆",
    emoji="🔍",
    category="查询",
)
async def search(
    params: SearchParams,
    **kwargs,
) -> Dict[str, Any]:
    """
    搜索社区内部资源和用户相关信息。

    scope 参数说明：
    - "auto": 系统自动选择数据源（默认搜索论坛+频道，若关键词含教程相关词汇则额外搜索教程库）
    - "forum": 仅搜索论坛帖子
    - "channel": 仅搜索服务器消息历史
    - "tutorial": 仅搜索教程知识库
    - "world_book": 搜索社区成员名片、其他用户资料和社区知识
    - "memory": 搜索与当前用户的历史对话记忆

    返回格式：字典，每个数据源一个键，值为该源的搜索结果。

    各数据源的结果格式：
    - forum: {"results": ["分类名 > 帖子链接", ...]}，每条结果为 "分类名 > URL" 格式的字符串。
      你在最终回复时，必须原样输出帖子链接和分类名，不要对链接进行任何再加工、转换或添加Markdown格式。
    - channel: {"results": [{"id": "...", "author": "...", "content": "...", "timestamp": "..."}]}
    - tutorial: {"results": "格式化后的教程文本"}
    - world_book: {"results": "格式化后的社区知识内容"}
    - memory: {"results": "格式化后的历史对话记忆"}
    """
    query = params.query

    if not (query and query.strip()):
        return {"error": "需要提供搜索关键词。"}

    if params.scope == "auto":
        sources = _auto_route(query or "")
    else:
        sources = [params.scope]

    log.info(
        f"工具 'search' 被调用，查询: {query}, scope: {params.scope}, 实际数据源: {sources}"
    )

    tasks = {}
    if "forum" in sources:
        tasks["forum"] = _search_forum(params, **kwargs)
    if "channel" in sources:
        tasks["channel"] = _search_channel(params, **kwargs)
    if "tutorial" in sources:
        tasks["tutorial"] = _search_tutorial(params, **kwargs)
    if "world_book" in sources:
        tasks["world_book"] = _search_world_book(params, **kwargs)
    if "memory" in sources:
        tasks["memory"] = _search_memory(params, **kwargs)

    if not tasks:
        return {"error": "没有可用的数据源。"}

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    output = {}
    for name, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            log.error(f"搜索数据源 '{name}' 失败: {result}", exc_info=result)
            output[name] = {"results": [], "error": str(result)}
        else:
            output[name] = result

    return output
