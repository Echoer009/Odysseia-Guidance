from datetime import datetime, timedelta, timezone
from typing import Tuple, Dict, Any, Optional
import logging

import random
from src.chat.utils.database import chat_db_manager
from src.chat.utils.time_utils import format_time_delta
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
            "total_sell_body_count": 0,
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
        # --- 全勤奖逻辑 (已修复) ---
        # 修复了同一天多次打工导致连续天数重置的BUG
        #
        # 旧逻辑问题:
        # 1. 每次开始时都将 `consecutive_days` 初始化为 1, 导致无法正确继承之前的连续天数。
        # 2. 当用户在同一天第二次打工时, `last_streak_date == yesterday` 和
        #    `last_streak_date != now.date()` 两个条件都不满足, 导致 `consecutive_days`
        #    维持初始值 1, 从而错误地重置了用户的连续记录。
        #
        # 新逻辑:
        # 1. 首先从数据库状态 `status` 中获取当前的连续天数。
        # 2. 检查上次打工日期 `last_streak_date` 是否存在且早于今天。
        # 3. 如果上次打工是昨天, 则连续天数加一。
        # 4. 如果上次打工不是昨天 (且不是今天), 则说明中断, 连续天数重置为 1。
        # 5. 如果上次打工就是今天, 则不进行任何操作, 保持现有连续天数。

        now_date = now.date()
        last_streak_date_str = status.get("last_streak_date")
        consecutive_days = status.get("consecutive_work_days", 0)
        is_streak_achieved = False

        if last_streak_date_str:
            last_streak_date = datetime.fromisoformat(last_streak_date_str).date()

            # [最终修复] 如果今天已经打过工，直接返回现有状态，不进行任何计算
            if last_streak_date == now_date:
                # 在返回前，仍然需要更新数据库以确保状态一致
                status["last_streak_date"] = now_date.isoformat()
                await self._update_user_work_status_from_dict(user_id, status)
                return False, consecutive_days

            yesterday = now_date - timedelta(days=1)
            if last_streak_date == yesterday:
                consecutive_days += 1
            else:
                consecutive_days = 1
        else:
            consecutive_days = 1

        if consecutive_days >= WorkConfig.STREAK_DAYS:
            is_streak_achieved = True
            consecutive_days = 0

        status["consecutive_work_days"] = consecutive_days
        status["last_streak_date"] = now_date.isoformat()

        # --- 更新数据库 ---
        await self._update_user_work_status_from_dict(user_id, status)

        return is_streak_achieved, consecutive_days

    async def increment_sell_body_count(self, user_id: int):
        """更新卖屁股的时间戳和每日计数。"""
        now = datetime.now(timezone.utc)
        status = await self.get_user_work_status(user_id)
        status = await self._reset_daily_counts_if_needed(status)

        status["sell_body_count_today"] += 1
        status["total_sell_body_count"] = status.get("total_sell_body_count", 0) + 1
        status["last_sell_body_timestamp"] = now

        await self._update_user_work_status_from_dict(user_id, status)

    async def check_work_cooldown(self, user_id: int) -> Tuple[bool, str]:
        """
        检查用户的工作冷却时间。
        返回 (is_on_cooldown, remaining_time_str)。
        """
        status = await self.get_user_work_status(user_id)
        last_timestamp = status.get("last_work_timestamp")
        if last_timestamp:
            # 确保时间戳是带时区的 datetime 对象
            if isinstance(last_timestamp, str):
                last_work_time = datetime.fromisoformat(last_timestamp).replace(
                    tzinfo=timezone.utc
                )
            else:
                last_work_time = last_timestamp.replace(tzinfo=timezone.utc)

            cooldown = timedelta(hours=WorkConfig.COOLDOWN_HOURS)
            if datetime.now(timezone.utc) - last_work_time < cooldown:
                remaining = cooldown - (datetime.now(timezone.utc) - last_work_time)
                return True, format_time_delta(remaining)
        return False, ""

    async def check_sell_body_cooldown(self, user_id: int) -> Tuple[bool, str]:
        """
        检查用户的卖屁股冷却时间。
        返回 (is_on_cooldown, remaining_time_str)。
        """
        status = await self.get_user_work_status(user_id)
        last_timestamp = status.get("last_sell_body_timestamp")
        if last_timestamp:
            # 确保时间戳是带时区的 datetime 对象
            if isinstance(last_timestamp, str):
                last_time = datetime.fromisoformat(last_timestamp).replace(
                    tzinfo=timezone.utc
                )
            else:
                last_time = last_timestamp.replace(tzinfo=timezone.utc)

            cooldown = timedelta(hours=WorkConfig.SELL_BODY_COOLDOWN_HOURS)
            if datetime.now(timezone.utc) - last_time < cooldown:
                remaining = cooldown - (datetime.now(timezone.utc) - last_time)
                return True, format_time_delta(remaining)
        return False, ""

    async def _update_user_work_status_from_dict(self, user_id: int, status: dict):
        """使用字典中的值来更新数据库。"""
        query = """
            INSERT INTO user_work_status (
                user_id, last_work_timestamp, consecutive_work_days, last_streak_date,
                last_sell_body_timestamp, work_count_today, sell_body_count_today, last_count_date,
                total_sell_body_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_work_timestamp = excluded.last_work_timestamp,
                consecutive_work_days = excluded.consecutive_work_days,
                last_streak_date = excluded.last_streak_date,
                last_sell_body_timestamp = excluded.last_sell_body_timestamp,
                work_count_today = excluded.work_count_today,
                sell_body_count_today = excluded.sell_body_count_today,
                last_count_date = excluded.last_count_date,
                total_sell_body_count = excluded.total_sell_body_count;
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
            status.get("total_sell_body_count"),
        )
        await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, params, commit=True
        )

    async def add_custom_event(self, event_data: Dict[str, Any]) -> bool:
        """
        将一个通过审核的自定义事件添加到数据库。
        """
        try:
            # 将所有需要的字段打包到一个字典中
            event_to_add = {
                "event_type": event_data["event_type"],
                "name": event_data["name"],
                "description": event_data["description"],
                "reward_range_min": event_data["reward_range_min"],
                "reward_range_max": event_data["reward_range_max"],
                "good_event_description": event_data.get("good_event_description"),
                "good_event_modifier": event_data.get("good_event_modifier"),
                "bad_event_description": event_data.get("bad_event_description"),
                "bad_event_modifier": event_data.get("bad_event_modifier"),
                "is_enabled": True,  # 审核通过的事件默认为启用
                "custom_event_by": event_data.get("contributor_id"),
            }
            await chat_db_manager.add_work_event(event_to_add)
            logging.info(f"成功将自定义事件 '{event_data['name']}' 添加到数据库。")
            return True
        except Exception as e:
            logging.error(
                f"添加自定义事件 '{event_data['name']}' 到数据库时失败: {e}",
                exc_info=True,
            )
            return False

    async def get_random_work_event(self, event_type: str) -> Optional[Dict[str, Any]]:
        """从数据库中随机获取一个指定类型的已启用事件。"""
        try:
            events = await chat_db_manager.get_work_events(event_type)
            if not events:
                return None

            # 将 sqlite3.Row 对象转换为字典
            event_dicts = [dict(event) for event in events]
            return random.choice(event_dicts)

        except Exception as e:
            logging.error(
                f"获取随机事件 (类型: {event_type}) 时失败: {e}", exc_info=True
            )
            return None
