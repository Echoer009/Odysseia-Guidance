# -*- coding: utf-8 -*-

import logging
from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)

log = logging.getLogger(__name__)


async def search_forum_threads(query: str, **kwargs) -> str:
    """
    在指定的论坛频道中，根据用户提问进行语义搜索，以查找相关的帖子。
    当用户的问题是查询角色卡、教程、预设、公益站或美化等内容有关时，应使用此工具。
    返回一个包含帖子标题和链接的列表。
    重要：你必须使用Markdown的项目符号列表（bulleted list）来清晰地展示返回的每一个帖子链接，而不是将它们混在一段话里。
    """
    log.info(f"工具 'search_forum_threads' 被调用，查询: {query}")

    if not forum_search_service.is_ready():
        return "论坛搜索服务当前不可用，请稍后再试。"

    results = await forum_search_service.search(query)

    if not results:
        return "在论坛中没有找到相关的帖子。"

    # 使用集合来防止返回重复的帖子链接
    processed_thread_ids = set()
    output_lines = ["找到了以下相关的论坛帖子:"]

    for result in results:
        metadata = result.get("metadata", {})
        thread_id = metadata.get("thread_id")

        if not thread_id or thread_id in processed_thread_ids:
            continue

        processed_thread_ids.add(thread_id)

        thread_name = metadata.get("thread_name", "未知标题")
        guild_id = metadata.get("guild_id")

        if not guild_id:
            log.warning(f"元数据中缺少 guild_id，无法为帖子 {thread_id} 创建链接。")
            continue

        # 动态构建帖子链接
        thread_url = f"https://discord.com/channels/{guild_id}/{thread_id}"
        # 动态构建帖子链接
        output_lines.append(f"- [{thread_name}]({thread_url})")

        # 限制最多返回5个结果，避免信息过载
        if len(processed_thread_ids) >= 5:
            break

    return "\n".join(output_lines)
