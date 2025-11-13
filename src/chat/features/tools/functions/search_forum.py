# -*- coding: utf-8 -*-

import logging
from src.chat.features.forum_search.services.forum_search_service import (
    forum_search_service,
)

log = logging.getLogger(__name__)


from typing import Dict, Any, List


async def search_forum_threads(
    query: str, filters: Dict[str, Any] = None, **kwargs
) -> str:
    """
    根据用户提问进行语义搜索，并支持通过元数据进行精确过滤。

    Args:
        query (str): 用于语义搜索的核心查询内容。
        filters (Dict[str, Any], optional): 一个包含元数据过滤条件的字典。
            - `category_name` (str): 按指定的论坛频道名称进行过滤。
            - `author_id` (int): 按作者的Discord ID进行过滤。
            - `author_name` (str): 按作者的显示名称进行过滤。
            - `tags` (List[str]): 按标签进行过滤，帖子必须包含列表中的所有指定标签。
            示例:
            {
                "category_name": "男性向",
                "author_name": "张三",
                "tags": ["角色卡", "原创"]
            }

    Returns:
        str: 一个Markdown格式的、包含帖子标题和链接的列表。
    """
    log.info(f"工具 'search_forum_threads' 被调用，查询: {query}, 过滤器: {filters}")

    if not forum_search_service.is_ready():
        return "论坛搜索服务当前不可用，请稍后再试。"

    results = await forum_search_service.search(query, filters=filters)

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
        category_name = metadata.get("category_name", "未知论坛")
        guild_id = metadata.get("guild_id")

        # 确保我们拥有创建链接所需的所有信息
        if guild_id and thread_name and category_name:
            # 清理标题中的换行符
            cleaned_thread_name = thread_name.replace("\n", " ").replace("\r", " ")

            # 动态构建帖子链接 (服务器ID/帖子ID)
            thread_url = f"https://discord.com/channels/{guild_id}/{thread_id}"

            # 按照 “标题 面包屑导航格式” 进行渲染
            output_lines.append(
                f"- {category_name} > {cleaned_thread_name} {thread_url}"
            )

            # 成功添加后，再将 thread_id 计入“已处理”集合
            processed_thread_ids.add(thread_id)
        else:
            # 如果缺少信息，记录警告并继续处理下一个结果。
            log.warning(
                f"元数据不完整 (guild_id: {guild_id}, thread_name: {thread_name}, category_name: {category_name})，无法为帖子 {thread_id} 创建链接。"
            )

        # 限制最多返回5个结果，避免信息过载
        if len(processed_thread_ids) >= 5:
            break

    return "\n".join(output_lines)
