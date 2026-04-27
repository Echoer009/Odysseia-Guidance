import random
import logging
from datetime import datetime
from typing import Optional, Dict, Any
import yaml

from sqlalchemy import select, func

from src.chat.config.chat_config import AFFECTION_CONFIG
from src.config import DEVELOPER_USER_IDS
from src.chat.utils.time_utils import BEIJING_TZ
from src.database.database import AsyncSessionLocal
from src.database.models import UserAffection

log = logging.getLogger(__name__)


class AffectionService:
    def __init__(self):
        self.affection_levels = self._load_affection_levels()

    def _load_affection_levels(self) -> list:
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

    async def _get_or_create_affection(self, user_id: int) -> Dict[str, Any]:
        uid = str(user_id)
        today = datetime.now(BEIJING_TZ).date().isoformat()

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserAffection).where(UserAffection.user_id == uid)
            )
            record = result.scalar_one_or_none()

            if record:
                if record.last_update_date != today:
                    record.daily_affection_gain = 0
                    record.last_update_date = today
                    await session.commit()
                    await session.refresh(record)
                    log.info(f"用户 {user_id} 的每日聊天好感度上限已于 {today} 重置。")

                return {
                    "user_id": record.user_id,
                    "affection_points": record.affection_points,
                    "daily_affection_gain": record.daily_affection_gain,
                    "last_update_date": record.last_update_date,
                    "last_interaction_date": record.last_interaction_date,
                    "last_gift_date": record.last_gift_date,
                }
            else:
                new_record = UserAffection(
                    user_id=uid,
                    affection_points=0,
                    daily_affection_gain=0,
                    last_update_date=today,
                    last_interaction_date=today,
                    last_gift_date=None,
                )
                session.add(new_record)
                await session.commit()
                log.info(f"为用户 {user_id} 创建了新的好感度记录。")
                return {
                    "user_id": uid,
                    "affection_points": 0,
                    "daily_affection_gain": 0,
                    "last_update_date": today,
                    "last_interaction_date": today,
                    "last_gift_date": None,
                }

    async def _update_affection(self, user_id: int, **kwargs) -> None:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserAffection)
                    .where(UserAffection.user_id == uid)
                    .with_for_update()
                )
                record = result.scalar_one_or_none()
                if record:
                    for key, value in kwargs.items():
                        setattr(record, key, value)
                else:
                    new_record = UserAffection(user_id=uid, **kwargs)
                    session.add(new_record)

    async def increase_affection_on_message(self, user_id: int) -> Optional[int]:
        if random.random() > AFFECTION_CONFIG["INCREASE_CHANCE"]:
            return None

        affection_data = await self._get_or_create_affection(user_id)

        if (
            affection_data["daily_affection_gain"]
            >= AFFECTION_CONFIG["DAILY_CHAT_AFFECTION_CAP"]
        ):
            log.info(f"用户 {user_id} 今日通过聊天获取好感度已达上限。")
            return None

        points_to_add = min(
            AFFECTION_CONFIG["INCREASE_AMOUNT"],
            AFFECTION_CONFIG["DAILY_CHAT_AFFECTION_CAP"]
            - affection_data["daily_affection_gain"],
        )

        new_points = affection_data["affection_points"] + points_to_add
        new_daily_gain = affection_data["daily_affection_gain"] + points_to_add

        await self._update_affection(
            user_id,
            affection_points=new_points,
            daily_affection_gain=new_daily_gain,
            last_interaction_date=datetime.now(BEIJING_TZ).date().isoformat(),
        )
        log.info(f"用户 {user_id} 的好感度增加了 {points_to_add} 点。")
        return points_to_add

    async def decrease_affection_on_blacklist(self, user_id: int) -> int:
        affection_data = await self._get_or_create_affection(user_id)

        new_points = (
            affection_data["affection_points"] + AFFECTION_CONFIG["BLACKLIST_PENALTY"]
        )

        await self._update_affection(user_id, affection_points=new_points)
        log.warning(
            f"用户 {user_id} 因被列入黑名单，好感度扣除了 {abs(AFFECTION_CONFIG['BLACKLIST_PENALTY'])} 点。"
        )
        return new_points

    async def increase_affection_for_gift(
        self, user_id: int, points_to_add: int
    ) -> tuple[bool, str]:
        affection_data = await self._get_or_create_affection(user_id)
        today = datetime.now(BEIJING_TZ).date().isoformat()

        if (
            user_id not in DEVELOPER_USER_IDS
            and affection_data.get("last_gift_date") == today
        ):
            log.info(f"用户 {user_id} 今天已经送过礼物了，送礼失败。")
            return False, "你今天已经送过礼物啦，类脑娘很开心，不过明天再来吧！"
        elif user_id in DEVELOPER_USER_IDS:
            log.info(f"开发者用户 {user_id} 正在送礼，已绕过每日限制。")

        new_points = affection_data["affection_points"] + points_to_add

        await self._update_affection(
            user_id,
            affection_points=new_points,
            last_gift_date=today,
            last_interaction_date=today,
        )
        log.info(f"用户 {user_id} 通过送礼增加了 {points_to_add} 点好感度。")
        return True, f"你送的礼物类脑娘很喜欢！好感度增加了 {points_to_add} 点。"

    async def add_affection_points(self, user_id: int, points_to_add: int) -> int:
        affection_data = await self._get_or_create_affection(user_id)

        new_points = affection_data["affection_points"] + points_to_add

        await self._update_affection(
            user_id,
            affection_points=new_points,
            last_interaction_date=datetime.now(BEIJING_TZ).date().isoformat(),
        )
        log.info(
            f"用户 {user_id} 的好感度直接增加了 {points_to_add} 点。新总点数: {new_points}"
        )
        return new_points

    async def get_affection_status(self, user_id: int) -> Dict[str, Any]:
        affection_data = await self._get_or_create_affection(user_id)

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
        if not self.affection_levels:
            log.error("好感度等级配置为空，返回默认等级。")
            return {
                "id": "default",
                "min_affection": 0,
                "max_affection": 19,
                "level_name": "陌生",
                "prompt": "你对用户还不太熟悉，保持礼貌和一定的距离感。",
            }

        sorted_levels = sorted(self.affection_levels, key=lambda x: x["min_affection"])

        for level in reversed(sorted_levels):
            if points >= level["min_affection"]:
                return level

        log.warning(f"好感度点数 {points} 低于所有定义的最低标准，返回最低等级。")
        return sorted_levels[0]

    async def apply_daily_fluctuation(self):
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(UserAffection))
            all_affections = result.scalars().all()

            for record in all_affections:
                fluctuation = random.randint(*AFFECTION_CONFIG["DAILY_FLUCTUATION"])
                record.affection_points += fluctuation
                log.info(
                    f"用户 {record.user_id} 的好感度每日浮动: {fluctuation}，新点数: {record.affection_points}"
                )
            await session.commit()

    async def reset_daily_affection_gain(self, new_date: str) -> None:
        async with AsyncSessionLocal() as session:
            await session.execute(
                UserAffection.__table__.update().values(
                    daily_affection_gain=0, last_update_date=new_date
                )
            )
            await session.commit()
            log.info(f"已重置所有用户的每日好感度获得量，日期更新为 {new_date}")


affection_service = AffectionService()
