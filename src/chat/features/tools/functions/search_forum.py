# -*- coding: utf-8 -*-

import logging
from typing import Dict, Any, List, Optional

from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)
from src.chat.config import chat_config as config

log = logging.getLogger(__name__)


async def search_forum_threads(
    query: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
    limit: int = config.FORUM_SEARCH_DEFAULT_LIMIT,
    **kwargs,
) -> List[str]:
    """
    [功能描述] 在社区论坛中搜索帖子，可以根据关键词、作者、频道或日期进行精确查找或模糊浏览。

    [使用时机]
    - 当用户明确表示想找帖子、搜内容时使用。
    - 当用户询问特定用户（例如 @user）发过什么内容时使用。
    - 当用户想看某个频道的近期帖子时使用。

    [参数说明]
    - query (str, optional): 搜索的关键词。如果用户只是按条件浏览，此项可留空。
    - limit (int, optional): 返回结果的最大数量，默认为 5。
    - filters (Dict[str, Any], optional): 过滤条件。
      - `category_name` (Union[str, List[str]]): 论坛频道的名称。有效名称包括: ['世界书', '全性向', '其他区', '制卡工具区', '女性向', '工具区', '插件', '教程', '深渊区', '男性向', '纯净区', '美化', '预设', '️其它工具区']。
      - `author_id` (Union[str, List[str]]): 作者的Discord ID。引导用户使用@mention来获取。
      - `start_date` (str): 开始日期 (格式: YYYY-MM-DD)。
      - `end_date` (str): 结束日期 (格式: YYYY-MM-DD)。

    [使用示例]
    - 用户说: "帮我找找关于'猫猫'的帖子" -> 调用时: `query="猫猫"`
    - 用户说: "看看<@12345>最近发了什么" -> 调用时: `filters={"author_id": "12345"}`
    - 用户说: "我想看'男性向'频道里最新的内容" -> 调用时: `filters={"category_name": "男性向"}`

    [返回格式与要求]
    - 函数返回一个字符串列表，每个字符串的格式为：`'频道名称 > 帖子链接'`。
    - 你在最终回复时，必须原样输出这些字符串，**不要**对链接进行任何形式的再加工、转换或添加Markdown格式。
    """
    # 为保护系统性能，设置一个硬性上限，最多获取 20 个文本块。
    limit = min(limit, 20)

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

    log.info(
        f"[SEARCH_FORUM_TOOL] 准备调用 forum_search_service.search。Limit: {limit}"
    )
    import time

    start_time = time.monotonic()

    # 确保 query 和 filters 不为 None，以满足 search 函数的类型要求
    safe_query = query if query is not None else ""
    safe_filters = filters if filters is not None else {}
    results = await forum_search_service.search(
        safe_query, n_results=limit, filters=safe_filters
    )

    duration = time.monotonic() - start_time
    log.info(
        f"[SEARCH_FORUM_TOOL] forum_search_service.search 调用完成, 耗时: {duration:.4f} 秒。"
    )
    log.debug(f"原始搜索结果: {results}")

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
            if len(processed_thread_ids) >= limit:
                break
        else:
            log.warning(f"元数据缺少 guild_id，无法为帖子 {thread_id} 创建链接。")

    return output_list
