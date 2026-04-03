import logging
from typing import Dict, Any

from src.chat.config import chat_config
from src.chat.utils.database import chat_db_manager
from src.database.database import AsyncSessionLocal
from src.database.models import UserWarningRecord, UserAffection
from sqlalchemy import select

log = logging.getLogger(__name__)


async def record_warning_and_check_blacklist(
    user_id: int, guild_id: int, expires_at
) -> Dict[str, Any]:
    uid = str(user_id)
    gid = str(guild_id)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(
                select(UserWarningRecord)
                .where(
                    UserWarningRecord.user_id == uid,
                    UserWarningRecord.guild_id == gid,
                )
                .with_for_update()
            )
            warning = result.scalar_one_or_none()

            if warning:
                warning.warning_count += 1
                current_warnings = warning.warning_count
            else:
                warning = UserWarningRecord(user_id=uid, guild_id=gid, warning_count=1)
                session.add(warning)
                current_warnings = 1

            await session.flush()

            if current_warnings >= 1:
                penalty = chat_config.AFFECTION_CONFIG["BLACKLIST_PENALTY"]
                if penalty != 0:
                    aff_result = await session.execute(
                        select(UserAffection)
                        .where(UserAffection.user_id == uid)
                        .with_for_update()
                    )
                    affection = aff_result.scalar_one_or_none()
                    if affection:
                        affection.affection_points += penalty
                    else:
                        affection = UserAffection(user_id=uid, affection_points=penalty)
                        session.add(affection)
                    log.info(f"用户 {user_id} 因被禁言被扣除好感度: {penalty}")

    if current_warnings >= 1:
        log.info(f"用户 {user_id} 在服务器 {guild_id} 达到警告阈值，将被加入黑名单。")
        await chat_db_manager.add_to_blacklist(user_id, guild_id, expires_at)

        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserWarningRecord).where(
                        UserWarningRecord.user_id == uid,
                        UserWarningRecord.guild_id == gid,
                    )
                )
                warning = result.scalar_one_or_none()
                if warning:
                    warning.warning_count = 0

        log.info(f"已重置用户 {user_id} 在服务器 {guild_id} 的警告计数。")
        return {"was_blacklisted": True, "new_warning_count": 0}

    return {"was_blacklisted": False, "new_warning_count": current_warnings}
