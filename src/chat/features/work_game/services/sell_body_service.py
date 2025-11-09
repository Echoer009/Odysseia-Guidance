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
                return f"你今天已经卖了 **{count}** 次了，身体要紧，明天再来吧！"

        # 2. 检查冷却时间（开发者跳过）
        if user_id not in DEVELOPER_USER_IDS:
            status = await self.work_db_service.get_user_work_status(user_id)
            if status.get("last_sell_body_timestamp"):
                last_time = status["last_sell_body_timestamp"].replace(
                    tzinfo=timezone.utc
                )
                cooldown = timedelta(hours=WorkConfig.SELL_BODY_COOLDOWN_HOURS)
                if datetime.now(timezone.utc) - last_time < cooldown:
                    remaining = cooldown - (datetime.now(timezone.utc) - last_time)
                    return f"卖这么多不好吧... 请在 **{format_time_delta(remaining)}** 后再来。🥵"

        # 3. 执行行为并计算奖励
        action = WorkConfig.get_random_sell_body_action()
        reward, event_description = WorkConfig.get_sell_body_action_reward(action)

        # 4. 更新时间戳和每日计数
        await self.work_db_service.increment_sell_body_count(user_id)

        # 5. 构建结果消息
        message = f"你决定进行 **{action['name']}**... \n"
        message += f"```{action['description']}```\n"

        if event_description:
            message += f"\n**突发事件！ {event_description}**\n"
        else:
            message += "\n"

        if reward > 0:
            message += f"-# 你获得了 **{reward}** 类脑币。"
        elif reward < 0:
            message += f"-# 你损失了 **{-reward}** 类脑币！"
        else:
            message += "-# 你白忙活了一场，什么都没得到。"

        # 6. 更新用户余额
        if reward > 0:
            await self.coin_service.add_coins(user_id, reward, reason="卖屁股奖励")
        elif reward < 0:
            await self.coin_service.remove_coins(user_id, -reward, reason="卖屁股亏损")

        return message
