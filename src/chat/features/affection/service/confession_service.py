from datetime import datetime, timedelta

from sqlalchemy import select, func, desc

from src.chat.utils.database import chat_db_manager
from src.chat.utils.time_utils import get_start_of_today_utc
from src.chat.config.chat_config import CONFESSION_CONFIG
from src.database.database import AsyncSessionLocal
from src.database.models import InteractionLog


class ConfessionService:
    def __init__(self):
        self.db_manager = chat_db_manager

    async def record_confession(self, user_id: str):
        async with AsyncSessionLocal() as session:
            log_entry = InteractionLog(
                user_id=str(user_id), interaction_type="confession"
            )
            session.add(log_entry)
            await session.commit()
        await self.db_manager.increment_confession_count()

    async def can_confess(self, user_id: str) -> tuple[bool, str]:
        now_utc = datetime.utcnow()
        uid = str(user_id)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(InteractionLog.timestamp)
                .where(
                    InteractionLog.user_id == uid,
                    InteractionLog.interaction_type == "confession",
                )
                .order_by(desc(InteractionLog.timestamp))
                .limit(1)
            )
            last_confession_row = result.scalar_one_or_none()

        if last_confession_row:
            last_confession_time = last_confession_row
            time_since_last = now_utc - last_confession_time
            cooldown_duration = timedelta(seconds=CONFESSION_CONFIG["COOLDOWN_SECONDS"])
            if time_since_last < cooldown_duration:
                remaining_time = cooldown_duration - time_since_last
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if hours > 0:
                    cooldown_message = f"{hours}小时{minutes}分钟"
                else:
                    cooldown_message = f"{minutes}分钟"
                return (
                    False,
                    f"你的忏悔太频繁了，请在 **{cooldown_message}** 后再来吧！",
                )

        start_of_today_utc = get_start_of_today_utc()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count())
                .select_from(InteractionLog)
                .where(
                    InteractionLog.user_id == uid,
                    InteractionLog.interaction_type == "confession",
                    InteractionLog.timestamp >= start_of_today_utc,
                )
            )
            confessions_today = result.scalar() or 0

        if confessions_today >= 3:
            return False, "今天已经忏悔三次了, 明天再说吧！"
        return True, ""


confession_service = ConfessionService()
