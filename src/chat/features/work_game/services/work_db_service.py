from datetime import datetime, timedelta, timezone
from typing import Tuple

from src.chat.utils.database import chat_db_manager
from ..config.work_config import WorkConfig


class WorkDBService:
    """处理与打工功能相关的数据库交互。"""

    async def get_user_work_status(self, user_id: int) -> dict:
        """获取用户的打工状态，如果不存在则返回一个包含默认值的字典。"""
        row = await chat_db_manager.get_user_work_status(user_id)
        if row:
            return dict(row)
        return {
            "user_id": user_id,
            "last_work_timestamp": None,
            "consecutive_work_days": 0,
            "last_streak_date": None,
            "last_sell_body_timestamp": None,
            "work_count_today": 0,
            "sell_body_count_today": 0,
            "last_count_date": None,
        }

    async def _reset_daily_counts_if_needed(self, status: dict) -> dict:
        """如果日期不是今天，则重置每日计数器。"""
        today_str = datetime.now(timezone.utc).date().isoformat()
        last_count_date_str = status.get("last_count_date")

        if last_count_date_str != today_str:
            status["work_count_today"] = 0
            status["sell_body_count_today"] = 0
            status["last_count_date"] = today_str
        return status

    async def check_daily_limit(
        self, user_id: int, action_type: str
    ) -> Tuple[bool, int]:
        """
        检查用户是否达到了某项操作的每日上限。
        返回 (is_limit_reached, current_count)。
        """
        status = await self.get_user_work_status(user_id)
        status = await self._reset_daily_counts_if_needed(status)

        if action_type == "work":
            count = status["work_count_today"]
            limit = WorkConfig.MAX_WORK_PER_DAY
            return count >= limit, count
        elif action_type == "sell_body":
            count = status["sell_body_count_today"]
            limit = WorkConfig.MAX_SELL_BODY_PER_DAY
            return count >= limit, count
        return True, 0

    async def update_work_record_and_check_streak(
        self, user_id: int
    ) -> Tuple[bool, int]:
        """
        更新用户的工作记录，增加每日计数，并检查是否触发了全勤奖。
        返回一个元组 (is_streak_achieved, new_streak_days)。
        """
        now = datetime.now(timezone.utc)
        today_str = now.date().isoformat()

        status = await self.get_user_work_status(user_id)
        status = await self._reset_daily_counts_if_needed(status)

        # 更新每日工作次数
        status["work_count_today"] += 1
        status["last_work_timestamp"] = now

        # --- 全勤奖逻辑 ---
        consecutive_days = 1
        is_streak_achieved = False
        last_streak_date_str = status.get("last_streak_date")

        if last_streak_date_str:
            last_streak_date = datetime.fromisoformat(last_streak_date_str).date()
            yesterday = now.date() - timedelta(days=1)

            if last_streak_date == yesterday:
                consecutive_days = status.get("consecutive_work_days", 0) + 1
            elif last_streak_date != now.date():
                consecutive_days = 1  # Streak broken

        if consecutive_days >= WorkConfig.STREAK_DAYS:
            is_streak_achieved = True
            consecutive_days = 0  # Reset streak after reward

        status["consecutive_work_days"] = consecutive_days
        status["last_streak_date"] = today_str

        # --- 更新数据库 ---
        await self._update_user_work_status_from_dict(user_id, status)

        return is_streak_achieved, consecutive_days

    async def increment_sell_body_count(self, user_id: int):
        """更新卖屁股的时间戳和每日计数。"""
        now = datetime.now(timezone.utc)
        status = await self.get_user_work_status(user_id)
        status = await self._reset_daily_counts_if_needed(status)

        status["sell_body_count_today"] += 1
        status["last_sell_body_timestamp"] = now

        await self._update_user_work_status_from_dict(user_id, status)

    async def _update_user_work_status_from_dict(self, user_id: int, status: dict):
        """使用字典中的值来更新数据库。"""
        query = """
            INSERT INTO user_work_status (
                user_id, last_work_timestamp, consecutive_work_days, last_streak_date,
                last_sell_body_timestamp, work_count_today, sell_body_count_today, last_count_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_work_timestamp = excluded.last_work_timestamp,
                consecutive_work_days = excluded.consecutive_work_days,
                last_streak_date = excluded.last_streak_date,
                last_sell_body_timestamp = excluded.last_sell_body_timestamp,
                work_count_today = excluded.work_count_today,
                sell_body_count_today = excluded.sell_body_count_today,
                last_count_date = excluded.last_count_date;
        """
        params = (
            user_id,
            status.get("last_work_timestamp"),
            status.get("consecutive_work_days"),
            status.get("last_streak_date"),
            status.get("last_sell_body_timestamp"),
            status.get("work_count_today"),
            status.get("sell_body_count_today"),
            status.get("last_count_date"),
        )
        await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, params, commit=True
        )
