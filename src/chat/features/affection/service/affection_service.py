import random
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import yaml  # 导入yaml库

from src.chat.utils.database import chat_db_manager
from src.chat.config.chat_config import AFFECTION_CONFIG
from src.config import DEVELOPER_USER_IDS
from src.chat.utils.time_utils import BEIJING_TZ

# --- 日志记录器 ---
log = logging.getLogger(__name__)


class AffectionService:
    """处理与AI好感度相关的所有业务逻辑。"""

    def __init__(self):
        self.db = chat_db_manager
        self.affection_levels = self._load_affection_levels()  # 加载好感度等级配置

    def _load_affection_levels(self) -> list:
        """从YAML文件加载好感度等级配置。"""
        try:
            with open(
                "src/chat/features/affection/data/affection_levels.yml",
                "r",
                encoding="utf-8",
            ) as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            log.error(
                "好感度等级配置文件 'src/affection/data/affection_levels.yml' 未找到。"
            )
            return []
        except yaml.YAMLError as e:
            log.error(f"解析好感度等级配置文件时出错: {e}")
            return []

    async def _get_or_create_affection(
        self, user_id: int, guild_id: int
    ) -> Dict[str, Any]:
        """获取或创建用户的好感度记录，并处理每日重置。"""
        affection_record = await self.db.get_affection(user_id, guild_id)
        today = datetime.now(BEIJING_TZ).date().isoformat()

        if affection_record:
            affection_data = dict(affection_record)
            last_update = affection_data.get("last_update_date")

            # 如果上次更新不是今天，则重置每日聊天获得量
            if last_update != today:
                affection_data["daily_affection_gain"] = 0
                affection_data["last_update_date"] = today
                await self.db.update_affection(
                    user_id, guild_id, daily_affection_gain=0, last_update_date=today
                )
                log.info(f"用户 {user_id} 的每日聊天好感度上限已于 {today} 重置。")

                # 重新获取记录以确保数据一致性
                refreshed_record = await self.db.get_affection(user_id, guild_id)
                if refreshed_record:
                    affection_data = dict(refreshed_record)
                # 如果获取失败，继续使用当前数据，但记录一个警告
                else:
                    log.warning(
                        f"在重置每日好感度后，无法重新获取用户 {user_id} 的好感度记录。"
                    )

            # 确保旧记录有 last_gift_date 字段
            if "last_gift_date" not in affection_data:
                affection_data["last_gift_date"] = None

            return affection_data
        else:
            # 如果记录不存在，则创建新的记录
            initial_data = {
                "affection_points": 0,
                "daily_affection_gain": 0,
                "last_update_date": today,
                "last_interaction_date": today,
                "last_gift_date": None,  # 新增字段
            }
            await self.db.update_affection(user_id, guild_id, **initial_data)
            log.info(f"为用户 {user_id} 在服务器 {guild_id} 创建了新的好感度记录。")

            new_record = await self.db.get_affection(user_id, guild_id)
            return dict(new_record)

    async def increase_affection_on_message(
        self, user_id: int, guild_id: int
    ) -> Optional[int]:
        """
        在用户发送消息后，根据几率增加好感度。
        返回增加的好感度点数，如果未增加则返回 None。
        """
        if random.random() > AFFECTION_CONFIG["INCREASE_CHANCE"]:
            return None

        affection_data = await self._get_or_create_affection(user_id, guild_id)

        # 检查每日聊天上限
        if (
            affection_data["daily_affection_gain"]
            >= AFFECTION_CONFIG["DAILY_CHAT_AFFECTION_CAP"]
        ):
            log.info(f"用户 {user_id} 今日通过聊天获取好感度已达上限。")
            return None

        # 计算可增加的点数
        points_to_add = min(
            AFFECTION_CONFIG["INCREASE_AMOUNT"],
            AFFECTION_CONFIG["DAILY_CHAT_AFFECTION_CAP"]
            - affection_data["daily_affection_gain"],
        )

        new_points = affection_data["affection_points"] + points_to_add
        new_daily_gain = affection_data["daily_affection_gain"] + points_to_add

        await self.db.update_affection(
            user_id,
            guild_id,
            affection_points=new_points,
            daily_affection_gain=new_daily_gain,
            last_interaction_date=datetime.now(BEIJING_TZ).date().isoformat(),
        )
        log.info(f"用户 {user_id} 的好感度增加了 {points_to_add} 点。")
        return points_to_add

    async def decrease_affection_on_blacklist(self, user_id: int, guild_id: int) -> int:
        """
        当用户被列入黑名单时，扣除好感度。
        返回扣除后的总好感度点数。
        """
        affection_data = await self._get_or_create_affection(user_id, guild_id)

        new_points = (
            affection_data["affection_points"] + AFFECTION_CONFIG["BLACKLIST_PENALTY"]
        )

        await self.db.update_affection(user_id, guild_id, affection_points=new_points)
        log.warning(
            f"用户 {user_id} 因被列入黑名单，好感度扣除了 {abs(AFFECTION_CONFIG['BLACKLIST_PENALTY'])} 点。"
        )
        return new_points

    async def increase_affection_for_gift(
        self, user_id: int, guild_id: int, points_to_add: int
    ) -> (bool, str):
        """
        当用户赠送礼物时增加好感度。礼物每天只能送一次。
        返回一个元组 (success: bool, message: str)。
        """
        affection_data = await self._get_or_create_affection(user_id, guild_id)
        today = datetime.now(BEIJING_TZ).date().isoformat()

        # 检查今天是否已经送过礼物，但开发者不受此限制
        if (
            user_id not in DEVELOPER_USER_IDS
            and affection_data.get("last_gift_date") == today
        ):
            log.info(f"用户 {user_id} 今天已经送过礼物了，送礼失败。")
            return False, "你今天已经送过礼物啦，类脑娘很开心，不过明天再来吧！"
        elif user_id in DEVELOPER_USER_IDS:
            log.info(f"开发者用户 {user_id} 正在送礼，已绕过每日限制。")

        # 增加好感度
        new_points = affection_data["affection_points"] + points_to_add

        await self.db.update_affection(
            user_id,
            guild_id,
            affection_points=new_points,
            last_gift_date=today,  # 更新送礼日期
            last_interaction_date=today,
        )
        log.info(f"用户 {user_id} 通过送礼增加了 {points_to_add} 点好感度。")
        return True, f"你送的礼物类脑娘很喜欢！好感度增加了 {points_to_add} 点。"

    async def add_affection_points(
        self, user_id: int, guild_id: int, points_to_add: int
    ) -> int:
        """
        直接为用户增加指定数量的好感度点数，不包含任何业务逻辑限制。
        返回新的好感度总点数。
        """
        affection_data = await self._get_or_create_affection(user_id, guild_id)

        new_points = affection_data["affection_points"] + points_to_add

        await self.db.update_affection(
            user_id,
            guild_id,
            affection_points=new_points,
            last_interaction_date=datetime.now(BEIJING_TZ).date().isoformat(),
        )
        log.info(
            f"用户 {user_id} 的好感度直接增加了 {points_to_add} 点。新总点数: {new_points}"
        )
        return new_points

    async def get_affection_status(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """
        获取用户当前的好感度状态，包括点数和等级。
        """
        affection_data = await self._get_or_create_affection(user_id, guild_id)

        points = affection_data["affection_points"]
        level_info = self.get_affection_level_info(points)

        return {
            "points": points,
            "level_name": level_info["level_name"],
            "prompt": level_info["prompt"],
            "daily_gain": affection_data["daily_affection_gain"],
            "daily_cap": AFFECTION_CONFIG["DAILY_CHAT_AFFECTION_CAP"],
        }

    def get_affection_level_info(self, points: float) -> Dict[str, Any]:
        """根据好感度点数获取对应的等级信息和提示词，现在可以处理浮点数和超出范围的值。"""
        if not self.affection_levels:
            log.error("好感度等级配置为空，返回默认等级。")
            return {
                "id": "default",
                "min_affection": 0,
                "max_affection": 19,
                "level_name": "陌生",
                "prompt": "你对用户还不太熟悉，保持礼貌和一定的距离感。",
            }

        # 按 min_affection 升序排序
        sorted_levels = sorted(self.affection_levels, key=lambda x: x["min_affection"])

        # 从最高等级开始反向查找，找到第一个低于或等于当前点数的等级
        for level in reversed(sorted_levels):
            if points >= level["min_affection"]:
                return level

        # 如果点数低于所有定义的最低标准，则返回最低等级
        log.warning(f"好感度点数 {points} 低于所有定义的最低标准，返回最低等级。")
        return sorted_levels[0]

    async def apply_daily_fluctuation(self, guild_id: int):
        """为服务器中的所有用户应用每日好感度随机浮动。"""
        all_affections = await self.db.get_all_affections_for_guild(guild_id)

        for record in all_affections:
            user_id = record["user_id"]
            current_points = record["affection_points"]

            fluctuation = random.randint(*AFFECTION_CONFIG["DAILY_FLUCTUATION"])
            new_points = current_points + fluctuation

            await self.db.update_affection(
                user_id, guild_id, affection_points=new_points
            )
            log.info(
                f"用户 {user_id} 的好感度每日浮动: {fluctuation}，新点数: {new_points}"
            )


# --- 单例实例 ---
affection_service = AffectionService()
