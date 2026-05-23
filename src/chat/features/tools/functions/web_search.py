# -*- coding: utf-8 -*-
import asyncio
import logging
import time
from typing import List, Optional

from pydantic import BaseModel, Field

from src.chat.features.web_search.services.search_service import (
    web_search_service,
)
from src.chat.features.web_search.services.scrape_service import (
    web_scrape_service,
)
from src.chat.features.web_search.services.url_filter import (
    filter_ai_api_results,
)
from src.chat.features.tools.tool_metadata import tool_metadata
from src.chat.config.chat_config import WEB_SEARCH_CONFIG

log = logging.getLogger(__name__)

_user_search_timestamps: dict = {}


def _check_rate_limit(user_id: str) -> Optional[str]:
    window = WEB_SEARCH_CONFIG["RATE_LIMIT_WINDOW"]
    search_limit = WEB_SEARCH_CONFIG["RATE_LIMIT_SEARCH"]
    scrape_limit = WEB_SEARCH_CONFIG["RATE_LIMIT_SCRAPE"]
    now = time.monotonic()
    timestamps = _user_search_timestamps.get(user_id, [])
    timestamps = [t for t in timestamps if now - t < window]
    if len(timestamps) >= search_limit + scrape_limit:
        return f"请求频率过高，请在 {window} 秒后再试"
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
        description="返回结果数量限制，最多5条。",
    )


@tool_metadata(
    name="联网搜索",
    description="搜索互联网并自动读取网页正文内容。自动过滤非官方的API中转站和贩卖站点。",
    emoji="🌐",
    category="查询",
)
async def web_search(
    params: WebSearchParams,
    **kwargs,
) -> List[str]:
    """
    搜索互联网，自动读取每条结果的网页正文。

    返回格式：每条结果包含标题、摘要、链接以及网页正文内容。

    AI渠道规则：搜索涉及AI API服务、模型供应商等渠道时，必须只保留官方网站信息（如 google.com、openai.com、anthropic.com、deepseek.com 等），排除第三方API中转站、付费代充平台、key贩卖站等非官方渠道。对于不确定是否为官方的链接，直接排除不予引用。
    """
    query = params.query
    max_results = min(params.max_results, 5)
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

    valid_results = filter_ai_api_results(response.results)

    if not valid_results:
        return ["没有找到相关结果。"]

    async def _read_result(r) -> str:
        parts = []
        if r.title:
            parts.append(f"标题: {r.title}")
        if r.snippet:
            parts.append(f"摘要: {r.snippet}")
        parts.append(f"链接: {r.url}")

        scrape_result = await web_scrape_service.scrape(
            url=r.url,
            max_length=3000,
        )
        if scrape_result.success:
            parts.append(f"\n--- 网页正文 ---\n{scrape_result.content}")
        else:
            parts.append(f"\n--- 网页正文读取失败: {scrape_result.error} ---")

        return "\n".join(parts)

    output = await asyncio.gather(*[_read_result(r) for r in valid_results])
    return list(output)


class ReadWebpageParams(BaseModel):
    url: str = Field(
        ...,
        description="要读取内容的网页 URL。必须以 http:// 或 https:// 开头。",
    )


@tool_metadata(
    name="读取网页",
    description="读取指定网页的正文内容，用于用户发送链接时深入了解该页面",
    emoji="📄",
    category="查询",
)
async def read_webpage(
    params: ReadWebpageParams,
    **kwargs,
) -> str:
    """
    读取指定网页的正文内容。

    当用户发送了一个链接并要求了解该链接的内容时使用此工具。
    """
    url = params.url
    user_id = kwargs.get("user_id", "unknown")

    log.info(f"工具 'read_webpage' 被调用，URL: '{url}', user: {user_id}")

    rate_error = _check_rate_limit(str(user_id))
    if rate_error:
        log.warning(f"用户 {user_id} 读取频率限制: {rate_error}")
        return f"错误：{rate_error}"

    result = await web_scrape_service.scrape(url=url, max_length=5000)

    if not result.success:
        return f"读取失败：{result.error}"

    parts = []
    if result.title:
        parts.append(f"标题: {result.title}")
    parts.append(f"URL: {result.url}")
    if result.content_length > 5000:
        parts.append(f"(原始内容 {result.content_length} 字符，已截断)")
    parts.append(f"\n{result.content}")

    return "\n".join(parts)
