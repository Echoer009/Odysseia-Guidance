# -*- coding: utf-8 -*-
"""
网页抓取服务 - 抓取指定 URL 并提取正文内容
"""

import ipaddress
import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx

from src.chat.config.chat_config import WEB_SEARCH_CONFIG

log = logging.getLogger(__name__)

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]

_BLOCKED_HOSTNAMES = {
    "localhost",
    "host.docker.internal",
}

_NOISE_TAGS = re.compile(
    r"<(script|style|nav|header|footer|aside|iframe|noscript|form|button|input|select|textarea)"
    r"[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


@dataclass
class ScrapeResult:
    title: str
    url: str
    content: str
    content_length: int
    success: bool
    error: Optional[str] = None


class WebScrapeService:
    """抓取网页并提取正文内容"""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=WEB_SEARCH_CONFIG["SCRAPE_TIMEOUT"],
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "*",
                },
            )
        return self._client

    def _validate_url(self, url: str) -> Optional[str]:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return f"不支持的协议: {parsed.scheme}"
        hostname = parsed.hostname
        if not hostname:
            return "无效的 URL"
        if hostname.lower() in _BLOCKED_HOSTNAMES:
            return "不允许访问该地址"
        try:
            ip = ipaddress.ip_address(hostname)
            for network in _BLOCKED_NETWORKS:
                if ip in network:
                    return "不允许访问内网地址"
        except ValueError:
            pass
        return None

    def _extract_title(self, html: str) -> str:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
        if m:
            return _HTML_TAG.sub("", m.group(1)).strip()
        return ""

    def _extract_content(self, html: str) -> str:
        content = ""

        for tag in ("article", "main"):
            m = re.search(
                rf"<{tag}[^>]*>(.*?)</{tag}>", html, re.DOTALL | re.IGNORECASE
            )
            if m:
                content = m.group(1)
                break

        if not content:
            m = re.search(
                r'<div[^>]*role=["\']main["\'][^>]*>(.*?)</div>',
                html,
                re.DOTALL | re.IGNORECASE,
            )
            if m:
                content = m.group(1)

        if not content:
            content = html

        content = _NOISE_TAGS.sub("", content)
        text = _HTML_TAG.sub("", content)
        text = _WHITESPACE.sub(" ", text).strip()

        return text

    async def scrape(
        self,
        url: str,
        max_length: int = 5000,
    ) -> ScrapeResult:
        validation_error = self._validate_url(url)
        if validation_error:
            log.warning(f"URL 安全检查失败: {url} - {validation_error}")
            return ScrapeResult(
                title="",
                url=url,
                content="",
                content_length=0,
                success=False,
                error=validation_error,
            )

        try:
            client = self._get_client()
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
        except httpx.TimeoutException:
            return ScrapeResult(
                title="", url=url, content="", content_length=0,
                success=False, error="网页请求超时",
            )
        except httpx.HTTPStatusError as e:
            return ScrapeResult(
                title="", url=url, content="", content_length=0,
                success=False, error=f"HTTP 错误: {e.response.status_code}",
            )
        except Exception as e:
            log.error(f"抓取网页异常: {url} - {e}", exc_info=True)
            return ScrapeResult(
                title="", url=url, content="", content_length=0,
                success=False, error=f"无法访问: {e}",
            )

        title = self._extract_title(html)
        content = self._extract_content(html)
        original_length = len(content)

        if original_length > max_length:
            content = content[:max_length] + f"\n\n...(内容已截断，原始长度 {original_length} 字符)"

        return ScrapeResult(
            title=title,
            url=url,
            content=content,
            content_length=original_length,
            success=True,
        )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


web_scrape_service = WebScrapeService()
