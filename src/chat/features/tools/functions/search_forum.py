# -*- coding: utf-8 -*-

import logging
from typing import List, Optional, Union
from pydantic import BaseModel, Field

from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)
from src.chat.config import chat_config as config
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)


# 1. 使用 Pydantic 定义 Filter 的精确结构，替代模糊的 Dict[str, Any]
# 这能让 Google SDK 自动生成精确的 JSON Schema，引导模型正确调用
class ForumSearchFilters(BaseModel):
    category_name: Optional[Union[str, List[str]]] = Field(
        None,
        description="论坛频道的名称，例如: '世界书', '教程', '男性向'等。",
    )
    author_id: Optional[Union[str, List[str]]] = Field(
        None, description="作者的 Discord ID (纯数字) "
    )
    start_date: Optional[str] = Field(None, description="开始日期 (格式: YYYY-MM-DD)。")
    end_date: Optional[str] = Field(None, description="结束日期 (格式: YYYY-MM-DD)。")


# 2. 在函数签名中使用 Pydantic 模型
async def search_forum_threads(
    query: Optional[str] = None,
    filters: Optional[ForumSearchFilters] = None,
    limit: int = config.FORUM_SEARCH_DEFAULT_LIMIT,
    **kwargs,
) -> List[str]:
    """
    在社区论坛中搜索帖子，可根据关键词、作者、频道或日期进行精确查找。

    [使用示例]
    - "帮我找找关于'女仆'的帖子" -> `query="女仆"`
    - "看看<@12345>最近发了什么" -> `filters={"author_id": "12345"}`
    - "我想看'男性向'频道里最新的内容" -> `filters={"category_name": "男性向"}`
    - "有没有Gemini预设推荐？" -> `query="Gemini预设"`, `filters={"category_name": ["预设"]}`

    [返回格式与要求]
    - 函数返回一个字符串列表，每个字符串的格式为：`'频道名称 > 帖子链接'`。
    - 你在最终回复时，必须原样输出这些字符串，**不要**对链接进行任何形式的再加工、转换或添加Markdown格式。
    """
    # 为保护系统性能，设置一个硬性上限
    limit = min(limit, 20)

    # 3. 将 Pydantic 模型转换为字典，以便在函数内部安全地操作
    filter_dict = {}
    if filters:
        # 健壮性处理：如果传入的是字典，先用它创建 Pydantic 模型实例
        if not isinstance(filters, ForumSearchFilters):
            try:
                filters = ForumSearchFilters(**filters)
            except Exception as e:
                log.error(f"从字典 {filters} 创建 ForumSearchFilters 时出错: {e}")
                return [f"错误：提供的筛选条件格式不正确。详情: {e}"]

        # 现在 filters 肯定是一个 Pydantic 对象，可以安全地调用 model_dump
        filter_dict = filters.model_dump(exclude_none=True)

    # 4. 在字典上执行所有的数据清洗和验证逻辑
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
                import re

                match = re.search(r"\d+", author_id_val)
                if match:
                    author_id_val = match.group(0)
            try:
                processed_ids.append(int(author_id_val))
            except (ValueError, TypeError) as e:
                log.error(f"无法将 author_id '{author_id_val}' 转换为整数: {e}")
                return ["错误：提供的作者ID列表中包含无法处理的格式。"]

        # 更新字典中的值
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
    # 5. 执行搜索
    log.info(f"准备调用 forum_search_service.search。Limit: {limit}")
    import time

    start_time = time.monotonic()

    safe_query = query if query is not None else ""
    results = await forum_search_service.search(
        safe_query, n_results=limit, filters=filter_dict
    )

    duration = time.monotonic() - start_time
    log.info(f"forum_search_service.search 调用完成, 耗时: {duration:.4f} 秒。")
    log.debug(f"原始搜索结果: {results}")

    if not results:
        return []

    # 6. 处理并格式化返回结果
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
