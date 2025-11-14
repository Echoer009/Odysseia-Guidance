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
    根据用户提问在论坛中进行语义搜索或按条件浏览。
    - 如果提供了 `query`，则执行语义搜索。
    - 如果 `query` 未提供但提供了 `filters`，则按条件列出最新的帖子。
    此工具返回一个字符串列表，每个字符串都结合了帖子的分类和其URL。你应该将列表中的每个字符串作为新的一行直接展示给用户。

    Args:
        query (str, optional): 用于语义搜索的核心查询内容。如果省略或为空字符串，则变为按 `filters` 浏览模式。
        filters (Dict[str, Any], optional): 一个包含元数据过滤条件的字典。
            - `category_name` (str): 按指定的论坛频道名称进行过滤。
            - `author_id` (int): 按作者的Discord ID进行过滤。
            - `author_name` (str): 按作者的显示名称进行过滤。
            - `start_date` (str): 筛选发布日期在此日期之后的帖子 (格式: YYYY-MM-DD)。
            - `end_date` (str): 筛选发布日期在此日期之前的帖子 (格式: YYYY-MM-DD)。
            示例:
            {
                "category_name": "男性向",
                "author_name": "张三"
            }

    Returns:
        List[str]: 一个字符串列表，每个字符串格式为 '分类名 > https://discord.com/channels/...'。
    """
    if filters is None:
        filters = {}

    # 修复：确保 author_id 是整数，以防止科学计数法问题
    if "author_id" in filters and filters["author_id"] is not None:
        try:
            filters["author_id"] = int(filters["author_id"])
        except (ValueError, TypeError) as e:
            log.error(f"无法将 author_id '{filters['author_id']}' 转换为整数: {e}")
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
