# -*- coding: utf-8 -*-
"""
联网搜索服务 - 通过 SearXNG JSON API 搜索互联网
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from src.chat.config.chat_config import WEB_SEARCH_CONFIG

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    engine: str
    score: float = 0.0
    category: str = "general"


@dataclass
class SearchResponse:
    results: List[SearchResult] = field(default_factory=list)
    total_results: int = 0
    query: str = ""
    error: Optional[str] = None


class WebSearchService:
    """通过 SearXNG JSON API 执行互联网搜索"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=WEB_SEARCH_CONFIG["TIMEOUT"])
        return self._client

    async def search(
        self,
        query: str,
        max_results: int = 5,
        categories: Optional[List[str]] = None,
        engines: Optional[List[str]] = None,
    ) -> SearchResponse:
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }
        if categories:
            params["categories"] = ",".join(categories)
        if engines:
            params["engines"] = ",".join(engines)

        try:
            client = self._get_client()
            resp = await client.get(f"{self.base_url}/search", params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException:
            log.warning(f"SearXNG 搜索超时: query='{query}'")
            return SearchResponse(query=query, error="搜索超时，请稍后再试")
        except httpx.HTTPStatusError as e:
            log.error(f"SearXNG HTTP 错误: {e.response.status_code}")
            return SearchResponse(query=query, error=f"搜索服务返回错误 ({e.response.status_code})")
        except Exception as e:
            log.error(f"SearXNG 搜索异常: {e}", exc_info=True)
            return SearchResponse(query=query, error=f"搜索服务不可用: {e}")

        results = []
        seen_urls = set()
        for item in data.get("results", []):
            url = item.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=url,
                    snippet=item.get("content", ""),
                    engine=item.get("engine", "unknown"),
                    score=item.get("score", 0.0),
                    category=item.get("category", "general"),
                )
            )
            if len(results) >= max_results:
                break

        return SearchResponse(
            results=results,
            total_results=len(results),
            query=query,
        )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


web_search_service = WebSearchService(
    base_url=WEB_SEARCH_CONFIG["SEARXNG_URL"],
)
