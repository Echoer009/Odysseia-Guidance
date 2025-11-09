from datetime import datetime, timedelta, timezone
from src.chat.features.odysseia_coin.service.coin_service import CoinService
from ..config.work_config import WorkConfig
from .work_db_service import WorkDBService
from src.chat.utils.time_utils import format_time_delta
from src.config import DEVELOPER_USER_IDS


class WorkService:
    def __init__(self, coin_service: CoinService):
        self.coin_service = coin_service
        self.work_db_service = WorkDBService()

    async def perform_work(self, user_id: int):
        """
        为用户执行一次随机工作，包含冷却、每日次数和全勤奖励逻辑。
        """
        # 1. 检查每日次数限制（开发者跳过）
        if user_id not in DEVELOPER_USER_IDS:
            is_limit_reached, count = await self.work_db_service.check_daily_limit(
                user_id, "work"
            )
            if is_limit_reached:
                return f"你今天已经工作了 **{count}** 次，够辛苦了，明天再来吧！"

        # 2. 检查冷却时间（开发者跳过）
        if user_id not in DEVELOPER_USER_IDS:
            status = await self.work_db_service.get_user_work_status(user_id)
            if status.get("last_work_timestamp"):
                last_work_time = status["last_work_timestamp"].replace(
                    tzinfo=timezone.utc
                )
                cooldown = timedelta(hours=WorkConfig.COOLDOWN_HOURS)
                if datetime.now(timezone.utc) - last_work_time < cooldown:
                    remaining = cooldown - (datetime.now(timezone.utc) - last_work_time)
                    return f"你刚打完一份工，正在休息呢。请在 **{format_time_delta(remaining)}** 后再来吧！"

        # 3. 执行工作并计算基础奖励
        job = WorkConfig.get_random_job()
        reward, event_description = WorkConfig.get_job_reward(job)
        total_reward = reward

        # 4. 更新工作记录并检查全勤奖
        (
            is_streak_achieved,
            new_streak_days,
        ) = await self.work_db_service.update_work_record_and_check_streak(user_id)

        # 5. 构建结果消息
        message = f"你成为了一名 **{job['name']}**。\n"
        message += f"```{job['description']}```\n"

        if event_description:
            message += f"**突发事件！** {event_description}\n"

        if reward > 0:
            message += f"\n你获得了 **{reward}** 类脑币。"
        elif reward < 0:
            message += f"\n你损失了 **{-reward}** 类脑币。"
        else:
            message += "\n你今天一无所获，白忙活了一场。"

        # 6. 如果达成全勤，添加奖励和消息
        if is_streak_achieved:
            streak_reward = WorkConfig.STREAK_REWARD
            total_reward += streak_reward
            message += f"\n\n🎉 **全勤奖励！** 你已连续打工 **{WorkConfig.STREAK_DAYS}** 天，额外获得 **{streak_reward}** 类脑币！"
            message += "\n你的连续打工记录已重置，期待你再次达成！"
        else:
            message += f"\n\n*你已连续打工 **{new_streak_days}** 天。*"

        # 7. 更新用户总余额
        if total_reward != 0:
            await self.coin_service.add_coins(user_id, total_reward, reason="打工奖励")

        return message
