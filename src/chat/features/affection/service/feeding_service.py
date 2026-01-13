from datetime import datetime, timedelta, timezone
from src.chat.utils.database import chat_db_manager
from src.chat.utils.time_utils import get_start_of_today_utc
from src.chat.config.chat_config import FEEDING_CONFIG


class FeedingService:
    def __init__(self):
        self.db_manager = chat_db_manager

    async def record_feeding(self, user_id: str):
        """记录一次投喂事件"""
        query = "INSERT INTO feeding_log (user_id, timestamp) VALUES (?, ?)"
        # 数据库中统一使用 UTC 时间
        await self.db_manager._execute(
            self.db_manager._db_transaction,
            query,
            (user_id, datetime.now(timezone.utc).isoformat()),
            commit=True,
        )
        await self.db_manager.increment_feeding_count()

    async def can_feed(self, user_id: str) -> tuple[bool, str]:
        """
        检查用户是否可以投喂。
        返回一个元组 (can_feed: bool, message: str)
        """
        # 1. 检查最近一次投喂时间（冷却时间）
        query1 = "SELECT timestamp FROM feeding_log WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1"
        last_feeding_row = await self.db_manager._execute(
            self.db_manager._db_transaction, query1, (user_id,), fetch="one"
        )

        now_utc = datetime.now(timezone.utc)
        if last_feeding_row:
            # fromisoformat 产生的是 naive datetime，但我们知道它代表 UTC
            last_feeding_time = datetime.fromisoformat(last_feeding_row[0]).replace(
                tzinfo=timezone.utc
            )
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

        # 2. 检查今天（北京时间）的投喂次数
        start_of_today_utc = get_start_of_today_utc()

        query2 = "SELECT COUNT(*) FROM feeding_log WHERE user_id = ? AND timestamp >= ?"
        count_row = await self.db_manager._execute(
            self.db_manager._db_transaction,
            query2,
            (user_id, start_of_today_utc.isoformat()),
            fetch="one",
        )

        feedings_today = count_row[0] if count_row else 0

        if feedings_today >= 3:
            return False, "你今天已经给我吃三次啦,肚子饱饱的,明天再说吧！"

        return True, ""


feeding_service = FeedingService()
