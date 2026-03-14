# -*- coding: utf-8 -*-
"""
教程查询工具 - 查询酒馆、类脑和公益站的教程、指南和报错解决方案
"""

import logging

from pydantic import BaseModel, Field

from src.chat.features.tutorial_search.services.tutorial_search_service import (
    tutorial_search_service,
)
from src.chat.services.prompt_service import prompt_service
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


class TutorialQuery(BaseModel):
    """教程查询参数"""

    query: str = Field(
        ...,
        description="用户的原始问题。适用于酒馆(SillyTavern)、类脑、公益站相关的教程、指南、报错解决方案查询。",
    )


@tool_metadata(
    name="教程查询",
    description="查询酒馆、类脑和公益站的教程、指南和报错解决方案",
    emoji="📚",
    category="查询",
)
async def query_tutorial_knowledge_base(params: TutorialQuery, **kwargs) -> str:
    """
    查询教程知识库。适用于酒馆、类脑、公益站相关的技术问题。
    如无相关内容会返回"我不知道"。
    """
    # 从 Pydantic 模型中提取参数
    query = params.query

    log.info(f"工具 'query_tutorial_knowledge_base' 被调用，查询: '{query}'")

    user_id = kwargs.get("user_id", "N/A")
    thread_id = kwargs.get("thread_id")

    docs = await tutorial_search_service.search(
        query, user_id=str(user_id), thread_id=thread_id
    )

    formatted_context = prompt_service.format_tutorial_context(docs, thread_id)

    return formatted_context
