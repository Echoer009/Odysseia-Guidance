import random
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
                last_work_timestamp_value = status["last_work_timestamp"]

                if isinstance(last_work_timestamp_value, str):
                    last_work_time_naive = datetime.fromisoformat(
                        last_work_timestamp_value
                    )
                else:
                    last_work_time_naive = last_work_timestamp_value

                last_work_time = last_work_time_naive.replace(tzinfo=timezone.utc)
                cooldown = timedelta(hours=WorkConfig.COOLDOWN_HOURS)
                if datetime.now(timezone.utc) - last_work_time < cooldown:
                    remaining = cooldown - (datetime.now(timezone.utc) - last_work_time)
                    return f"你刚打完一份工，正在休息呢。请在 **{format_time_delta(remaining)}** 后再来吧！"

        # 3. 从数据库获取随机工作事件
        event = await self.work_db_service.get_random_work_event("work")
        if not event:
            return "现在好像没什么工作可做，晚点再来看看吧。"

        # 4. 计算基础奖励和决定事件结果
        base_reward = random.randint(
            event["reward_range_min"], event["reward_range_max"]
        )
        reward = base_reward
        outcome_description = ""

        # 设定好事和坏事发生的概率
        GOOD_EVENT_CHANCE = 0.25
        BAD_EVENT_CHANCE = 0.15
        roll = random.random()

        if roll < GOOD_EVENT_CHANCE and event["good_event_modifier"] is not None:
            # 好事发生
            reward = int(base_reward * event["good_event_modifier"])
            outcome_description = event["good_event_description"]
        elif (
            roll < GOOD_EVENT_CHANCE + BAD_EVENT_CHANCE
            and event["bad_event_modifier"] is not None
        ):
            # 坏事发生
            reward = int(base_reward * event["bad_event_modifier"])
            outcome_description = event["bad_event_description"]

        total_reward = reward

        # 5. 更新工作记录并检查全勤奖
        (
            is_streak_achieved,
            new_streak_days,
        ) = await self.work_db_service.update_work_record_and_check_streak(user_id)

        # 6. 构建结果消息
        message = f"你开始了 **{event['name']}** 的工作。\n"
        message += f"```{event['description']}```\n"
        if outcome_description:
            message += f"{outcome_description}\n"

        if reward > 0:
            message += f"\n你获得了 **{reward}** 类脑币。"
        elif reward < 0:
            message += f"\n你损失了 **{-reward}** 类脑币。"
        else:
            message += "\n你今天一无所获，白忙活了一场。"

        # 7. 如果达成全勤，添加奖励和消息
        if is_streak_achieved:
            streak_reward = WorkConfig.STREAK_REWARD
            total_reward += streak_reward
            message += f"\n\n🎉 **全勤奖励！** 你已连续打工 **{WorkConfig.STREAK_DAYS}** 天，额外获得 **{streak_reward}** 类脑币！"
            message += "\n你的连续打工记录已重置，期待你再次达成！"
        else:
            message += f"\n\n*你已连续打工 **{new_streak_days}** 天。*"

        # 8. 更新用户总余额
        if total_reward != 0:
            await self.coin_service.add_coins(user_id, total_reward, reason="打工奖励")

        return message
