# -*- coding: utf-8 -*-
import logging
from typing import Dict, Any, Literal, Optional

from pydantic import BaseModel, Field

from src.chat.features.tools.tool_metadata import tool_metadata
from src.chat.features.personal_memory.services.user_memory_note_service import (
    user_memory_note_service,
    CATEGORY_LABELS,
)

log = logging.getLogger(__name__)


class ManageMemoryParams(BaseModel):
    action: Literal["add", "update", "delete"] = Field(
        ...,
        description=(
            "操作类型："
            "add=记住一条新信息（需要提供category和content）；"
            "update=修改已有记忆的内容（需要提供note_id和content）；"
            "delete=删除一条不再适用的记忆（需要提供note_id）。"
        ),
    )
    category: Optional[Literal["emotion", "status", "preference", "positive_event"]] = (
        Field(
            None,
            description=(
                "记忆类别（仅add时需要）："
                "emotion=用户当前的情感/心情（如开心、压力大）；"
                "status=用户的生活处境（如学生、正在找工作）；"
                "preference=用户希望被怎么称呼、互动偏好（只接受平等的昵称，拒绝主人/爸爸/老公等上位称呼）；"
                "positive_event=值得纪念的正面事件。"
            ),
        )
    )
    content: Optional[str] = Field(
        None,
        description=(
            "记忆内容（add/update时必填），简短精炼，不超过30字。"
            "只记正面积极的内容，不记争吵/色情/过分要求。"
        ),
    )
    note_id: Optional[int] = Field(
        None,
        description="已有记忆条目的ID（仅update/delete时必填）。"
    )


@tool_metadata(
    name="管理记忆",
    description=(
        "记住用户的重要信息，或修改/删除已有的记忆。"
        "你记住的信息会在下次对话时自动提醒你，帮助你更好地了解用户。"
        "【重要】不要每句话都记录，只在用户明确提出称呼偏好、分享重要生活变化、"
        "或发生值得纪念的正面事件时才使用。普通闲聊不需要记录。"
        "每次对话最多调用一次此工具。"
    ),
    emoji="📝",
    category="记忆",
)
async def manage_memory(
    params: ManageMemoryParams,
    **kwargs,
) -> Dict[str, Any]:
    """
    什么时候该记：
    - 用户明确要求你怎么称呼ta → add, category=preference
    - 用户主动分享重要的生活变化（换了工作、开始考研等） → add, category=status
    - 发生了值得纪念的正面事件 → add, category=positive_event

    什么时候不该记：
    - 普通闲聊、日常对话中的情绪流露 → 不要记
    - 你自己推断或猜测的信息 → 不要记
    - 用户没有明确表达、只是随口一提 → 不要记

    每次对话最多调用一次。
    preference类：不接受主人/爸爸/老公等上位称呼，类脑娘和用户是平等朋友。
    不记录色情、文爱、过分要求、争吵冲突等负面内容。
    """
    user_id = kwargs.get("user_id")
    if not user_id:
        return {"error": "无法获取当前用户ID"}

    user_id = str(user_id)
    action = params.action

    log.info(f"[manage_memory] action={action}, user_id={user_id}")

    try:
        if action == "add":
            if not params.category:
                return {"error": "add 操作需要提供 category"}
            if not params.content:
                return {"error": "add 操作需要提供 content"}

            success, message, note_id = await user_memory_note_service.add_note(
                user_id=user_id,
                category=params.category,
                content=params.content,
            )
            if success:
                return {
                    "success": True,
                    "note_id": note_id,
                    "category": CATEGORY_LABELS.get(params.category, params.category),
                    "content": params.content.strip(),
                }
            else:
                return {"success": False, "error": message}

        elif action == "update":
            if not params.note_id:
                return {"error": "update 操作需要提供 note_id"}
            if not params.content:
                return {"error": "update 操作需要提供 content"}

            success, message = await user_memory_note_service.update_note(
                user_id=user_id,
                note_id=params.note_id,
                content=params.content,
            )
            if success:
                return {
                    "success": True,
                    "note_id": params.note_id,
                    "content": params.content.strip(),
                }
            else:
                return {"success": False, "error": message}

        elif action == "delete":
            if not params.note_id:
                return {"error": "delete 操作需要提供 note_id"}

            success, message = await user_memory_note_service.delete_note(
                user_id=user_id,
                note_id=params.note_id,
            )
            if success:
                return {"success": True, "note_id": params.note_id}
            else:
                return {"success": False, "error": message}

        else:
            return {"error": f"未知操作: {action}"}

    except Exception as e:
        log.error(f"[manage_memory] 执行 {action} 时出错: {e}", exc_info=True)
        return {"error": f"操作失败: {str(e)}"}
