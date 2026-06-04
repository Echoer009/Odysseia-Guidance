# -*- coding: utf-8 -*-
"""
用户上下文收集工具 - 获取当前用户的个人印象和最近对话记录
"""

import logging
from typing import Dict, Any, Literal

from pydantic import BaseModel, Field

from src.chat.features.tools.tool_metadata import tool_metadata
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.chat.features.personal_memory.services.conversation_block_service import (
    conversation_block_service,
)

log = logging.getLogger(__name__)


class GatherContextParams(BaseModel):
    scope: Literal["impression", "conversation", "all"] = Field(
        default="all",
        description=(
            "查询范围："
            "impression=你对当前用户的个人印象和了解；"
            "conversation=你和当前用户最近的对话记录；"
            "all=以上全部，一次性获取。"
            "如果不确定需要什么，使用 all。"
        ),
    )


async def _gather_impression(**kwargs) -> str | None:
    user_id = kwargs.get("user_id")
    if not user_id:
        return None
    user_profile_data = await world_book_service.get_profile_by_discord_id(int(user_id))
    if user_profile_data:
        return user_profile_data.get("personal_summary")
    return None


async def _gather_conversation(**kwargs) -> str | None:
    user_id = kwargs.get("user_id")
    if not user_id:
        return None
    latest_block = await conversation_block_service.get_latest_block_content(user_id)
    if latest_block:
        time_desc = latest_block.get("time_description", "最近")
        conversation_text = latest_block.get("conversation_text", "")
        return f"以下是你与用户在 {time_desc} 的对话记录：\n{conversation_text}"
    return None


@tool_metadata(
    name="获取用户上下文",
    description="获取当前用户的个人印象和最近对话记录。当你需要了解用户背景或回忆最近的互动时调用。",
    emoji="🧠",
    category="查询",
)
async def gather_context(
    params: GatherContextParams,
    **kwargs,
) -> Dict[str, Any]:
    """
    获取当前用户的个人印象和最近对话记录。

    当你对当前用户的偏好、历史互动等信息不确定时，
    应主动调用此工具获取相关上下文，而非凭猜测回复。
    """
    user_id = kwargs.get("user_id")
    if not user_id:
        return {"error": "无法获取当前用户ID"}

    user_id = str(user_id)
    scope = params.scope

    kwargs["user_id"] = user_id

    log.info(f"[gather_context] scope={scope}, user_id={user_id}")

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
