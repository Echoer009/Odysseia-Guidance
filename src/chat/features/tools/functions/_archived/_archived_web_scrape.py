# -*- coding: utf-8 -*-
"""
网页抓取工具 - 抓取指定网页的正文内容
"""

import logging
import time
from typing import Optional

from pydantic import BaseModel, Field

from src.chat.features.web_search.services.scrape_service import (
    web_scrape_service,
)
from src.chat.features.tools.tool_metadata import tool_metadata
from src.chat.config.chat_config import WEB_SEARCH_CONFIG

log = logging.getLogger(__name__)

_user_scrape_timestamps: dict = {}


def _check_rate_limit(user_id: str) -> Optional[str]:
    window = WEB_SEARCH_CONFIG["RATE_LIMIT_WINDOW"]
    limit = WEB_SEARCH_CONFIG["RATE_LIMIT_SCRAPE"]
    now = time.monotonic()
    timestamps = _user_scrape_timestamps.get(user_id, [])
    timestamps = [t for t in timestamps if now - t < window]
    if len(timestamps) >= limit:
        return f"抓取频率过高，请在 {window} 秒后再试"
    timestamps.append(now)
    _user_scrape_timestamps[user_id] = timestamps
    return None


class WebScrapeParams(BaseModel):
    url: str = Field(
        ...,
        description="要抓取内容的网页 URL。必须以 http:// 或 https:// 开头。",
    )
    max_length: int = Field(
        default=WEB_SEARCH_CONFIG["SCRAPE_MAX_LENGTH"],
        description="返回内容的最大字符数。默认5000字符。",
    )


@tool_metadata(
    name="网页抓取",
    description="抓取指定网页的正文内容，用于深入了解某个链接的详细信息",
    emoji="📄",
    category="查询",
)
async def web_scrape(
    params: WebScrapeParams,
    **kwargs,
) -> str:
    """
    抓取指定网页的正文内容。

    适用于在 web_search 搜索结果中，发现需要深入了解的链接时使用。
    会自动提取网页核心文字内容，去除导航、广告等噪音。
    """
    url = params.url
    max_length = min(params.max_length, 8000)
    user_id = kwargs.get("user_id", "unknown")

    log.info(f"工具 'web_scrape' 被调用，URL: '{url}', user: {user_id}")

    rate_error = _check_rate_limit(str(user_id))
    if rate_error:
        log.warning(f"用户 {user_id} 抓取频率限制: {rate_error}")
        return f"错误：{rate_error}"

    result = await web_scrape_service.scrape(url=url, max_length=max_length)

    if not result.success:
        return f"抓取失败：{result.error}"

    parts = []
    if result.title:
        parts.append(f"标题: {result.title}")
    parts.append(f"URL: {result.url}")
    if result.content_length > max_length:
        parts.append(f"(原始内容 {result.content_length} 字符，已截断)")
    parts.append(f"\n{result.content}")

    return "\n".join(parts)
