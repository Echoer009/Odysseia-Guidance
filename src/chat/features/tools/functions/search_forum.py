# -*- coding: utf-8 -*-

import logging
from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)
from src.chat.config import chat_config as config

log = logging.getLogger(__name__)


from typing import Dict, Any, List, Union


async def search_forum_threads(
    query: str = None,
    filters: Dict[str, Any] = None,
    limit: int = config.FORUM_SEARCH_DEFAULT_LIMIT,
    **kwargs,
) -> List[str]:
    """
    在社区论坛中搜索帖子。仅当用户明确想寻找、查询或浏览论坛内容时，使用此工具。

    此工具有两种主要使用模式:
    1. **语义搜索**: 当用户提供具体的关键词时，使用 `query` 参数进行内容搜索。此时可选择性地附加 `filters` 来缩小范围。
    2. **条件浏览**: 当用户只想按特定条件筛选帖子时，如时间条件，作者条件;使用 `filters` 参数。**在这种模式下，`query` 参数可以、也应该为空。**

    Args:
        query (str, optional): 用于语义搜索的核心查询内容。如果用户只想按条件浏览，请将此项留空。
        limit (int, optional): 返回结果的最大数量。默认为 5。
        filters (Dict[str, Any], optional): 一个或多个过滤条件。可以单独使用，也可以与 `query` 组合使用。
            - `category_name` (Union[str, List[str]]): 按一个或多个论坛频道名称进行过滤。
            - `author_id` (Union[str, List[str]]): 按一个或多个作者的Discord ID过滤。要获取此ID，你必须引导用户使用@mention功能。ID应为纯数字字符串。
            - `start_date` (str): 筛选发布日期在此日期或之后的帖子 (格式: YYYY-MM-DD)。
            - `end_date` (str): 筛选发布日期在此日期或之前的帖子 (格式: YYYY-MM-DD)。

    Returns:
        List[str]: 一个字符串列表，每个字符串格式为 '分类名 > https://discord.com/channels/...'。
    """
    if filters is None:
        filters = {}

    # 修复：确保 author_id 是整数或整数列表，并能处理 @mention 格式
    if "author_id" in filters and filters["author_id"] is not None:
        author_id_input = filters["author_id"]
        is_single_item = not isinstance(author_id_input, list)
        author_id_list = [author_id_input] if is_single_item else author_id_input

        processed_ids = []
        for author_id_val in author_id_list:
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
                processed_ids.append(int(author_id_val))
            except (ValueError, TypeError) as e:
                log.error(f"无法将 author_id '{author_id_val}' 转换为整数: {e}")
                return ["错误：提供的作者ID列表中包含无法处理的格式。"]

        # 如果原来是单个条目，就还用单个整数；如果原来是列表，就用列表
        filters["author_id"] = processed_ids[0] if is_single_item else processed_ids

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

    results = await forum_search_service.search(query, n_results=limit, filters=filters)
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

    return output_list
