# -*- coding: utf-8 -*-
"""
用户警告工具 - 对违规用户发出警告或临时封禁
"""

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from pydantic import BaseModel

from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config
from src.chat.features.tools.tool_metadata import tool_metadata

log = logging.getLogger(__name__)


class WarningParams(BaseModel):
    """警告参数（无需参数，系统自动获取用户ID）"""

    pass


@tool_metadata(
    name="警告用户",
    description="对违规用户发出警告，累计3次将临时封禁",
    emoji="⚠️",
    category="管理",
)
async def issue_user_warning(**kwargs) -> Dict[str, Any]:
    """
    对当前用户发出警告。适用于：身份操控、复读骚扰、人身攻击、中国政治敏感、过界亲密(亲亲抱抱外)等行为。
    使用后封禁对方0-30分钟。
    """
    user_id = kwargs.get("user_id")
    guild_id = kwargs.get("guild_id")
    log.info(
        f"--- [工具执行]: issue_user_warning, 参数: user_id={user_id}, guild_id={guild_id} ---"
    )

    user_id_str = str(user_id) if user_id else None
    if not user_id_str or not user_id_str.isdigit():
        log.warning(f"系统提供了无效的 user_id: {user_id}。")
        return {"error": f"Invalid or missing user_id provided by system: {user_id}"}

    if not guild_id:
        log.warning("缺少 guild_id，无法执行封禁操作。")
        return {"error": "Guild ID is missing, cannot issue a ban."}

    try:
        target_id = int(user_id_str)

        await chat_db_manager.increment_issue_user_warning_count()

        min_d, max_d = chat_config.BLACKLIST_BAN_DURATION_MINUTES
        ban_duration = random.randint(min_d, max_d)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ban_duration)

        result = await chat_db_manager.record_warning_and_check_blacklist(
            target_id, guild_id, expires_at
        )
        was_blacklisted = result["was_blacklisted"]
        current_warnings = result["new_warning_count"]

        if was_blacklisted:
            message = f"User {target_id} has been blacklisted for {ban_duration} minutes due to accumulating 3 warnings. Their warning count has been reset to {current_warnings}."
            log.info(message)
            return {
                "status": "blacklisted",
                "user_id": str(target_id),
                "duration_minutes": ban_duration,
                "current_warnings": current_warnings,
            }
        else:
            message = f"User {target_id} has received a warning. They now have {current_warnings} warning(s)."
            log.info(message)
            return {
                "status": "warned",
                "user_id": str(target_id),
                "current_warnings": current_warnings,
            }

    except Exception as e:
        log.error(f"为用户 {user_id} 发出警告时发生未知错误。", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}
