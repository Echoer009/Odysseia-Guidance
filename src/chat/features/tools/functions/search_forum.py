# -*- coding: utf-8 -*-
"""
论坛搜索工具 - 在社区论坛中搜索帖子
"""

import logging
import re
import time
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)
from src.chat.config import chat_config as config
from src.chat.utils.database import chat_db_manager
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)

# 允许的频道名称列表
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


# 动态创建 Literal 类型
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


class ForumSearchParams(BaseModel):
    """论坛搜索参数"""

    query: Optional[str] = Field(
        None,
        description="搜索关键词。",
    )
    # 筛选条件（平铺到顶层）
    category_name: Optional[CategoryName] = Field(
        None,
        description="论坛频道名称。",
    )
    author_id: Optional[str] = Field(None, description="作者的 Discord ID (纯数字)")
    start_date: Optional[str] = Field(None, description="开始日期 (格式: YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="结束日期 (格式: YYYY-MM-DD)")
    limit: int = Field(
        default=config.FORUM_SEARCH_DEFAULT_LIMIT,
        description="返回结果数量限制。",
    )


@tool_metadata(
    name="论坛搜索",
    description="在社区论坛中搜索帖子，可按关键词、作者、频道或日期筛选",
    emoji="🔍",
    category="查询",
)
async def search_forum_threads(
    params: ForumSearchParams,
    **kwargs,
) -> List[str]:
    """
    在社区论坛中搜索帖子。

    返回格式：
    - 返回一个字符串列表，每个字符串的格式为：`'频道名称 > 帖子链接'`。
    - 你在最终回复时，必须原样输出这些链接，**不要**对链接进行任何形式的再加工、转换或添加Markdown格式。
    """
    # 从 Pydantic 模型中提取参数
    query = params.query
    limit = min(params.limit, 20)

    # 构建筛选条件字典
    filter_dict = {}
    if params.category_name:
        filter_dict["category_name"] = params.category_name
    if params.author_id:
        filter_dict["author_id"] = params.author_id
    if params.start_date:
        filter_dict["start_date"] = params.start_date
    if params.end_date:
        filter_dict["end_date"] = params.end_date

    # 过滤 category_name：只保留允许的频道名称
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

    # 处理 author_id
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
                return ["错误：提供的作者ID列表中包含无法处理的格式。"]

        filter_dict["author_id"] = processed_ids if is_single_item else processed_ids

    # 健壮性处理：应对 query 被错误地传入 filters 字典内的情况
    if query is None and "query" in filter_dict:
        query = filter_dict.pop("query", None)

    # 检查调用是否有效
    if not (query and query.strip()) and not filter_dict:
        log.error("工具调用缺少 'query' 和 'filters' 参数。")
        return ["错误：你需要提供一个关键词或者至少一个筛选条件。"]

    log.info(
        f"工具 'search_forum_threads' 被调用，查询: {query}, 过滤器: {filter_dict}"
    )

    if not forum_search_service.is_ready():
        return ["论坛搜索服务当前不可用，请稍后再试。"]

    await chat_db_manager.increment_forum_search_count()

    log.info(f"准备调用 forum_search_service.search。Limit: {limit}")

    start_time = time.monotonic()

    safe_query = query if query is not None else ""
    results = await forum_search_service.search(
        safe_query, n_results=limit, filters=filter_dict, use_hybrid=True
    )

    duration = time.monotonic() - start_time
    log.info(f"forum_search_service.search 调用完成, 耗时: {duration:.4f} 秒。")
    log.debug(f"原始搜索结果: {results}")

    if not results:
        return []

    # 处理并格式化返回结果
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

    return output_list
