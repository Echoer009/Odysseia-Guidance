import random
from datetime import datetime, timedelta, timezone
from src.chat.features.odysseia_coin.service.coin_service import CoinService
from ..config.work_config import WorkConfig
from .work_db_service import WorkDBService
from src.chat.utils.time_utils import format_time_delta
from src.config import DEVELOPER_USER_IDS


class SellBodyService:
    def __init__(self, coin_service: CoinService):
        self.coin_service = coin_service
        self.work_db_service = WorkDBService()

    async def perform_sell_body(self, user_id: int):
        """
        为用户执行一次卖屁股行为。
        """
        # 1. 检查每日次数限制（开发者跳过）
        if user_id not in DEVELOPER_USER_IDS:
            (
                is_limit_reached,
                count,
            ) = await self.work_db_service.check_daily_limit(user_id, "sell_body")
            if is_limit_reached:
                return {
                    "success": False,
                    "message": f"你今天已经卖了 **{count}** 次了，身体要紧，明天再来吧！",
                }

        # 2. 检查冷却时间（开发者跳过）
        if user_id not in DEVELOPER_USER_IDS:
            status = await self.work_db_service.get_user_work_status(user_id)
            if status.get("last_sell_body_timestamp"):
                last_time_value = status["last_sell_body_timestamp"]

                if isinstance(last_time_value, str):
                    last_time = datetime.fromisoformat(last_time_value)
                else:
                    last_time = last_time_value

                if last_time.tzinfo is None:
                    last_time = last_time.replace(tzinfo=timezone.utc)
                else:
                    last_time = last_time.astimezone(timezone.utc)

                cooldown = timedelta(hours=WorkConfig.SELL_BODY_COOLDOWN_HOURS)
                if datetime.now(timezone.utc) - last_time < cooldown:
                    remaining = cooldown - (datetime.now(timezone.utc) - last_time)
                    return {
                        "success": False,
                        "message": f"卖这么多不好吧... **{format_time_delta(remaining)}** 后再卖吧🥵",
                    }

        # 3. 从数据库获取随机事件
        event = await self.work_db_service.get_random_work_event("sell_body")
        if not event:
            return {
                "success": False,
                "message": f"今天好像没什么客人，你暂时安全...我是说，真不巧。",
            }

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

        # 5. 更新时间戳和每日计数
        await self.work_db_service.increment_sell_body_count(user_id)

        # 6. 更新用户余额
        if reward > 0:
            await self.coin_service.add_coins(user_id, reward, reason="卖屁股奖励")
        elif reward < 0:
            await self.coin_service.remove_coins(user_id, -reward, reason="卖屁股亏损")

        # 7. 构建成功结果
        title = f"🥵 {event['name']}"
        description = event["description"]
        if outcome_description:
            description += f"\n\n{outcome_description}"

        if reward > 0:
            reward_text = f"你获得了 {reward} 类脑币。"
        elif reward < 0:
            reward_text = f"你损失了 {-reward} 类脑币！"
        else:
            reward_text = "你白忙活了一场，什么都没得到。"

        return {
            "success": True,
            "embed_data": {
                "title": title,
                "description": description,
                "reward_text": reward_text,
                "user_id": user_id,
            },
        }
