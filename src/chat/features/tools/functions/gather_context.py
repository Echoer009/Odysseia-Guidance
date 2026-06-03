# -*- coding: utf-8 -*-
"""
上下文收集工具 - 按需获取用户的印象、对话记录、知识库搜索结果、历史对话记忆
"""

import logging
from typing import Dict, Any, List, Literal, Optional

from pydantic import BaseModel, Field

from src.chat.features.tools.tool_metadata import tool_metadata
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.chat.features.personal_memory.services.conversation_block_service import (
    conversation_block_service,
)
from src.chat.features.personal_memory.services.conversation_memory_search_service import (
    conversation_memory_search_service,
)
from src.chat.services.prompt_service import prompt_service

log = logging.getLogger(__name__)


class GatherContextParams(BaseModel):
    scope: Literal[
        "impression", "conversation", "knowledge_base", "conversation_memory", "all"
    ] = Field(
        default="all",
        description=(
            "查询范围："
            "impression=你对当前用户的个人印象和了解；"
            "conversation=你和当前用户最近的对话记录；"
            "knowledge_base=搜索其他社区成员的资料、社区知识等，需要提供query作为搜索词；"
            "conversation_memory=搜索与当前用户的历史对话记忆，需要提供query作为搜索词；"
            "all=以上全部，一次性获取。"
            "如果不确定需要什么，使用 all。"
        ),
    )
    query: Optional[str] = Field(
        None,
        description="搜索关键词。scope为knowledge_base时用于搜索社区成员资料和社区知识，scope为conversation_memory时用于搜索历史对话，scope为all时可作为搜索依据",
    )


async def _gather_impression(**kwargs) -> Optional[str]:
    user_id = kwargs.get("user_id")
    if not user_id:
        return None
    user_profile_data = await world_book_service.get_profile_by_discord_id(int(user_id))
    if user_profile_data:
        return user_profile_data.get("personal_summary")
    return None


async def _gather_conversation(**kwargs) -> Optional[str]:
    user_id = kwargs.get("user_id")
    if not user_id:
        return None
    latest_block = await conversation_block_service.get_latest_block_content(user_id)
    if latest_block:
        time_desc = latest_block.get("time_description", "最近")
        conversation_text = latest_block.get("conversation_text", "")
        return f"以下是你与用户在 {time_desc} 的对话记录：\n{conversation_text}"
    return None


async def _gather_knowledge_base(**kwargs) -> Optional[str]:
    user_id = kwargs.get("user_id")
    if not user_id:
        return None
    query = kwargs.get("fallback_query", "")
    user_query = kwargs.get("query") or query
    if not user_query:
        return None

    guild_id = kwargs.get("guild_id")
    if not guild_id:
        return None

    user_name = kwargs.get("user_name", "用户")
    channel_context = kwargs.get("channel_context")

    entries = await world_book_service.find_entries(
        latest_query=user_query,
        user_id=int(user_id),
        guild_id=int(guild_id),
        user_name=user_name,
        conversation_history=channel_context,
    )

    if entries:
        return prompt_service._format_world_book_entries(entries, user_name)
    return None


async def _gather_conversation_memory(**kwargs) -> Optional[str]:
    user_id = kwargs.get("user_id")
    if not user_id:
        return None
    query = kwargs.get("fallback_query", "")
    user_query = kwargs.get("query") or query
    if not user_query:
        return None

    latest_block_id = await conversation_block_service.get_latest_block_id(user_id)
    exclude_block_ids = [latest_block_id] if latest_block_id else None

    blocks = await conversation_memory_search_service.search(
        discord_id=user_id,
        query=user_query,
        exclude_block_ids=exclude_block_ids,
    )

    if blocks:
        formatted = conversation_memory_search_service.format_blocks_for_context(blocks)
        log.info(f"[gather_context] 检索到 {len(blocks)} 个相关对话记忆块")
        return formatted
    return None


@tool_metadata(
    name="获取上下文",
    description="每次回复前，根据当前对话调用此工具获取相关信息。可获取：个人印象、最近对话、世界书资料、历史记忆等。",
    emoji="🧠",
    category="查询",
)
async def gather_context(
    params: GatherContextParams,
    **kwargs,
) -> Dict[str, Any]:
    """
    当你对当前用户的偏好、历史互动、社区知识等信息不确定时，
    应主动调用此工具获取相关上下文，而非凭猜测回复。
    遇到记不清的细节、被问到之前的对话内容、或需要了解用户背景时都必须调用。
    不确定需要什么范围时用 scope=all。
    """
    user_id = kwargs.get("user_id")
    if not user_id:
        return {"error": "无法获取当前用户ID"}

    user_id = str(user_id)
    scope = params.scope
    query = params.query

    if query:
        kwargs["query"] = query

    kwargs["user_id"] = user_id

    log.info(f"[gather_context] scope={scope}, query={query}, user_id={user_id}")

    results = {}

    try:
        if scope in ("impression", "all"):
            impression = await _gather_impression(**kwargs)
            if impression:
                results["impression"] = impression

        if scope in ("conversation", "all"):
            conversation = await _gather_conversation(**kwargs)
            if conversation:
                results["conversation"] = conversation

        if scope in ("knowledge_base", "all"):
            kb_result = await _gather_knowledge_base(**kwargs)
            if kb_result:
                results["knowledge_base"] = kb_result

        if scope in ("conversation_memory", "all"):
            cm_result = await _gather_conversation_memory(**kwargs)
            if cm_result:
                results["conversation_memory"] = cm_result

    except Exception as e:
        log.error(f"[gather_context] 收集上下文时出错: {e}", exc_info=True)
        return {"error": f"收集上下文时出错: {str(e)}"}

    if not results:
        return {
            "scope": scope,
            "results": {},
            "message": "未找到相关信息",
        }

    return {"scope": scope, "results": results}
