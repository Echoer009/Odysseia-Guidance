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

    # 诊断日志：打印从向量数据库返回的原始结果
    log.info(f"原始搜索结果: {results}")

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

        thread_name = metadata.get("thread_name", "未知标题")
        guild_id = metadata.get("guild_id")

        # 确保我们拥有创建链接所需的所有信息
        if guild_id and thread_name:
            # 动态构建帖子链接
            thread_url = f"https://discord.com/channels/{guild_id}/{thread_id}"
            output_lines.append(f"- [{thread_name}]({thread_url})")

            # 成功添加后，再将 thread_id 计入“已处理”集合
            processed_thread_ids.add(thread_id)
        else:
            # 如果缺少信息，记录警告并继续处理下一个结果。
            # 这修复了一个 bug：之前，即使缺少 guild_id，thread_id 也会被添加到 processed_thread_ids，
            # 导致同一个帖子的其他有效区块（chunk）被跳过。
            log.warning(
                f"元数据不完整 (guild_id: {guild_id}, thread_name: {thread_name})，无法为帖子 {thread_id} 创建链接。"
            )

        # 限制最多返回5个结果，避免信息过载
        if len(processed_thread_ids) >= 5:
            break

    return "\n".join(output_lines)
