# -*- coding: utf-8 -*-

import logging
from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)

log = logging.getLogger(__name__)


from typing import Dict, Any, List


async def search_forum_threads(
    query: str = None, filters: Dict[str, Any] = None, **kwargs
) -> List[str]:
    """
    在社区论坛中搜索帖子。这个工具有两种模式：
    1. **语义搜索**: 当用户提供具体的关键词时，使用 `query` 参数进行搜索。
    2. **条件浏览**: 当用户想按特定条件筛选帖子时，使用 `filters` 参数。

    Args:
        query (str, optional): 用于语义搜索的核心查询内容。如果省略或为空字符串，则变为按 `filters` 浏览模式。
        filters (Dict[str, Any], optional): 一个包含元数据过滤条件的字典。
            - `category_name` (str): 按指定的论坛频道名称进行过滤。
            - `author_id` (str): 按作者的Discord ID过滤。要获取此ID，你必须引导用户使用@mention功能。ID应为纯数字字符串。

    Returns:
        List[str]: 一个字符串列表，每个字符串格式为 '分类名 > https://discord.com/channels/...'。
    """
    if filters is None:
        filters = {}

    # 修复：确保 author_id 是整数，并能处理 @mention 格式
    if "author_id" in filters and filters["author_id"] is not None:
        author_id_val = filters["author_id"]

        # 检查并从 <@...> mention 格式中提取数字 ID
        if (
            isinstance(author_id_val, str)
            and author_id_val.startswith("<@")
            and author_id_val.endswith(">")
        ):
            import re

            match = re.search(r"\d+", author_id_val)
            if match:
                author_id_val = match.group(0)

        try:
            # 将最终处理过的值转换为整数
            filters["author_id"] = int(author_id_val)
        except (ValueError, TypeError) as e:
            log.error(f"无法将 author_id '{author_id_val}' 转换为整数: {e}")
            return ["错误：提供的作者ID格式不正确，无法处理。"]

    # 健壮性处理：应对 query 被错误地传入 filters 字典内的情况
    if query is None and "query" in filters:
        query = filters.pop("query")

    # 如果 query (去除首尾空格后) 为空且 filters 也为空，则返回错误
    if not (query and query.strip()) and not filters:
        log.error(
            "工具 'search_forum_threads' 被调用，但缺少 'query' 和 'filters' 参数。"
        )
        return ["错误：你需要提供一个关键词或者至少一个筛选条件（比如频道名称）。"]

    log.info(f"工具 'search_forum_threads' 被调用，查询: {query}, 过滤器: {filters}")

    if not forum_search_service.is_ready():
        return ["论坛搜索服务当前不可用，请稍后再试。"]

    results = await forum_search_service.search(query, filters=filters)
    log.info(f"原始搜索结果: {results}")

    if not results:
        return []

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
            # 构建 "分类 > 链接" 格式的字符串
            output_string = f"{category_name} > {thread_url}"
            output_list.append(output_string)
            processed_thread_ids.add(thread_id)
        else:
            log.warning(f"元数据缺少 guild_id，无法为帖子 {thread_id} 创建链接。")

        if len(processed_thread_ids) >= 5:
            break

    return output_list
