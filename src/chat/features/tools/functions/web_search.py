# -*- coding: utf-8 -*-
"""
联网搜索工具 - 搜索互联网获取信息
"""

import logging
import time
from typing import List, Optional

from pydantic import BaseModel, Field

from src.chat.features.web_search.services.search_service import (
    web_search_service,
)
from src.chat.features.tools.tool_metadata import tool_metadata
from src.chat.config.chat_config import WEB_SEARCH_CONFIG

log = logging.getLogger(__name__)

_user_search_timestamps: dict = {}


def _check_rate_limit(user_id: str) -> Optional[str]:
    window = WEB_SEARCH_CONFIG["RATE_LIMIT_WINDOW"]
    limit = WEB_SEARCH_CONFIG["RATE_LIMIT_SEARCH"]
    now = time.monotonic()
    timestamps = _user_search_timestamps.get(user_id, [])
    timestamps = [t for t in timestamps if now - t < window]
    if len(timestamps) >= limit:
        return f"搜索频率过高，请在 {window} 秒后再试"
    timestamps.append(now)
    _user_search_timestamps[user_id] = timestamps
    return None


class WebSearchParams(BaseModel):
    query: str = Field(
        ...,
        description="搜索关键词。用于查询互联网上的信息。",
    )
    max_results: int = Field(
        default=WEB_SEARCH_CONFIG["MAX_RESULTS"],
        description="返回结果数量限制，最多10条。",
    )


@tool_metadata(
    name="联网搜索",
    description="搜索互联网获取信息，返回相关网页列表（标题、摘要、链接）",
    emoji="🌐",
    category="查询",
)
async def web_search(
    params: WebSearchParams,
    **kwargs,
) -> List[str]:
    """
    搜索互联网获取信息。

    返回格式：
    - 返回一个字符串列表，每条格式为：`标题 | 摘要 | 链接`。
    - 你可以从中选择有价值的链接，使用 web_scrape 工具进一步获取详细内容。
    """
    query = params.query
    max_results = min(params.max_results, 10)
    user_id = kwargs.get("user_id", "unknown")

    log.info(f"工具 'web_search' 被调用，查询: '{query}', user: {user_id}")

    rate_error = _check_rate_limit(str(user_id))
    if rate_error:
        log.warning(f"用户 {user_id} 搜索频率限制: {rate_error}")
        return [f"错误：{rate_error}"]

    response = await web_search_service.search(
        query=query,
        max_results=max_results,
    )

    if response.error:
        return [f"搜索失败：{response.error}"]

    if not response.results:
        return ["没有找到相关结果。"]

    output = []
    for r in response.results:
        parts = []
        if r.title:
            parts.append(f"标题: {r.title}")
        if r.snippet:
            parts.append(f"摘要: {r.snippet}")
        parts.append(f"链接: {r.url}")
        output.append("\n".join(parts))

    return output
