import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import random

from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config

log = logging.getLogger(__name__)


async def issue_user_warning(
    user_id: Optional[str] = None,
    reason: Optional[str] = "No reason provided by the model.",
    **kwargs,
) -> Dict[str, Any]:
    """
    对指定用户发出一次警告。当用户的行为违反了规定时，应调用此工具。
    系统会自动记录用户的警告次数。当警告累计达到3次时，用户将被自动加入黑名单一段时间。
    请仅在绝对必要时使用此工具。

    Args:
        user_id (Optional[str]): 目标用户的纯数字 Discord ID。如果模型认为当前对话的用户需要被警告，则无需传入此参数，系统会自动填充。
        reason (Optional[str]): 本次警告的原因。模型应提供一个简洁明了的理由。

    Returns:
        一个包含操作结果的字典，例如发出了第几次警告，或者用户是否因此被拉黑。
    """
    guild_id = kwargs.get("guild_id")
    log.info(
        f"--- [工具执行]: issue_user_warning, 参数: user_id={user_id}, guild_id={guild_id}, reason='{reason}' ---"
    )

    if not user_id or not user_id.isdigit():
        log.warning(f"提供了无效的 user_id: {user_id}。")
        return {"error": f"Invalid or missing user_id provided: {user_id}"}

    if not guild_id:
        log.warning("缺少 guild_id，无法执行警告操作。")
        return {"error": "Guild ID is missing, cannot issue a warning."}

    try:
        target_id = int(user_id)

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
                "reason": reason,
                "duration_minutes": ban_duration,
                "current_warnings": current_warnings,
            }
        else:
            message = f"User {target_id} has received a warning. They now have {current_warnings} warning(s)."
            log.info(message)
            return {
                "status": "warned",
                "user_id": str(target_id),
                "reason": reason,
                "current_warnings": current_warnings,
            }

    except Exception as e:
        log.error(f"为用户 {user_id} 发出警告时发生未知错误。", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}
