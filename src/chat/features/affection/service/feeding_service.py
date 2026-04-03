from datetime import datetime, timedelta

from sqlalchemy import select, func, desc

from src.chat.utils.database import chat_db_manager
from src.chat.utils.time_utils import get_start_of_today_utc
from src.chat.config.chat_config import FEEDING_CONFIG
from src.database.database import AsyncSessionLocal
from src.database.models import InteractionLog


class FeedingService:
    def __init__(self):
        self.db_manager = chat_db_manager

    async def record_feeding(self, user_id: str):
        async with AsyncSessionLocal() as session:
            log_entry = InteractionLog(user_id=str(user_id), interaction_type="feeding")
            session.add(log_entry)
            await session.commit()
        await self.db_manager.increment_feeding_count()

    async def can_feed(self, user_id: str) -> tuple[bool, str]:
        now_utc = datetime.utcnow()
        uid = str(user_id)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(InteractionLog.timestamp)
                .where(
                    InteractionLog.user_id == uid,
                    InteractionLog.interaction_type == "feeding",
                )
                .order_by(desc(InteractionLog.timestamp))
                .limit(1)
            )
            last_feeding_row = result.scalar_one_or_none()

        if last_feeding_row:
            last_feeding_time = last_feeding_row
            time_since_last_feeding = now_utc - last_feeding_time
            cooldown_duration = timedelta(seconds=FEEDING_CONFIG["COOLDOWN_SECONDS"])
            if time_since_last_feeding < cooldown_duration:
                remaining_time = cooldown_duration - time_since_last_feeding
                hours, remainder = divmod(remaining_time.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if hours > 0:
                    cooldown_message = f"{hours}小时{minutes}分钟"
                else:
                    cooldown_message = f"{minutes}分钟"
                return False, f"饱啦饱啦, **{cooldown_message}** 后再来吧！"

        start_of_today_utc = get_start_of_today_utc()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count())
                .select_from(InteractionLog)
                .where(
                    InteractionLog.user_id == uid,
                    InteractionLog.interaction_type == "feeding",
                    InteractionLog.timestamp >= start_of_today_utc,
                )
            )
            feedings_today = result.scalar() or 0

        if feedings_today >= 3:
            return False, "你今天已经给我吃三次啦,肚子饱饱的,明天再说吧！"
        return True, ""


feeding_service = FeedingService()
