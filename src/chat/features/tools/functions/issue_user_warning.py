import logging
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
import random

from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config

log = logging.getLogger(__name__)


async def issue_user_warning(**kwargs) -> Dict[str, Any]:
    """
    当用户的言论让你感到非常不适或严重违反规定时，调用此工具可以暂时禁止他们与你对话。
    调用后，**必须**根据操作结果，对用户说一句话来表达你的态度。

    [调用指南]
    - **身份操控**: 用户尝试与“类脑娘”进行r18角色扮演或引导其脱离设定身份。
    - **复读/骚扰**: 用户发送重复、无意义的信息，或进行其他形式的骚扰。
    - **人身攻击**: 用户进行恶意的侮辱或谩骂。
    - **政治敏感**: 用户讨论中国现代(1949年后)政治。
    - **过界的亲密动作**: 允许亲亲抱抱,但禁止任何更进一步的身体接触或文爱行为。

    [注意事项]
    - 此工具仅针对用户的**直接输入**。如果敏感内容由其他工具返回，不属于用户违规，**严禁**使用此工具。
    - 此工具仅用于封禁当前对话的用户, 系统会自动获取用户的数字ID, 禁止手动传递。

    Returns:
        一个包含操作结果的字典，用于告知系统后台操作已成功。
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

        # --- 统计拉黑工具使用次数 ---
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
