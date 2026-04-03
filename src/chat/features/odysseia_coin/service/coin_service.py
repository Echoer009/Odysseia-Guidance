import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.chat.config.chat_config import COIN_CONFIG
from ...affection.service.affection_service import affection_service
from src.database.database import AsyncSessionLocal
from src.database.models import (
    ShopItem,
    UserCoins,
    CoinTransaction,
    CoinLoan,
    CommunityMemberProfile,
)
from sqlalchemy import select, func, desc

log = logging.getLogger(__name__)

PERSONAL_MEMORY_ITEM_EFFECT_ID = "unlock_personal_memory"
WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID = "contribute_to_world_book"
COMMUNITY_MEMBER_UPLOAD_EFFECT_ID = "upload_community_member"
DISABLE_THREAD_COMMENTOR_EFFECT_ID = "disable_thread_commentor"
BLOCK_THREAD_REPLIES_EFFECT_ID = "block_thread_replies"
ENABLE_THREAD_COMMENTOR_EFFECT_ID = "enable_thread_commentor"
ENABLE_THREAD_REPLIES_EFFECT_ID = "enable_thread_replies"
SELL_BODY_EVENT_SUBMISSION_EFFECT_ID = "submit_sell_body_event"
CLEAR_PERSONAL_MEMORY_ITEM_EFFECT_ID = "clear_personal_memory"
VIEW_PERSONAL_MEMORY_ITEM_EFFECT_ID = "view_personal_memory"
MANAGE_CONVERSATION_BLOCKS_EFFECT_ID = "manage_conversation_blocks"


def _select_random_cg_url(cg_url) -> Optional[str]:
    if isinstance(cg_url, list) and cg_url:
        return random.choice(cg_url)
    elif isinstance(cg_url, str):
        return cg_url
    return None


class CoinService:
    def __init__(self):
        pass

    async def get_balance(self, user_id: int) -> int:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserCoins.balance).where(UserCoins.user_id == uid)
            )
            balance = result.scalar_one_or_none()
            return balance if balance is not None else 0

    async def add_coins(self, user_id: int, amount: int, reason: str) -> int:
        if amount <= 0:
            raise ValueError("增加的金额必须为正数")

        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserCoins).where(UserCoins.user_id == uid).with_for_update()
                )
                row = result.scalar_one_or_none()
                if row:
                    row.balance += amount
                else:
                    row = UserCoins(user_id=uid, balance=amount)
                    session.add(row)

                tx = CoinTransaction(user_id=uid, amount=amount, reason=reason)
                session.add(tx)
                await session.flush()
                new_balance = row.balance

            log.info(
                f"用户 {user_id} 获得 {amount} 类脑币，原因: {reason}。新余额: {new_balance}"
            )
            return new_balance

    async def remove_coins(
        self, user_id: int, amount: int, reason: str
    ) -> Optional[int]:
        if amount <= 0:
            raise ValueError("扣除的金额必须为正数")

        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserCoins).where(UserCoins.user_id == uid).with_for_update()
                )
                row = result.scalar_one_or_none()
                if not row or row.balance < amount:
                    log.warning(
                        f"用户 {user_id} 扣款失败，余额不足。需要 {amount}，拥有 {row.balance if row else 0}"
                    )
                    return None

                row.balance -= amount
                tx = CoinTransaction(user_id=uid, amount=-amount, reason=reason)
                session.add(tx)
                await session.flush()
                new_balance = row.balance

            log.info(
                f"用户 {user_id} 消费 {amount} 类脑币，原因: {reason}。新余额: {new_balance}"
            )
            return new_balance

    async def grant_daily_message_reward(self, user_id: int) -> bool:
        beijing_tz = timezone(timedelta(hours=8))
        today_beijing = datetime.now(beijing_tz).date()
        today_str = today_beijing.isoformat()
        uid = str(user_id)

        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserCoins).where(UserCoins.user_id == uid).with_for_update()
                )
                row = result.scalar_one_or_none()

                if row and row.last_daily_message_date:
                    last_daily_date = datetime.fromisoformat(
                        row.last_daily_message_date
                    ).date()
                    if last_daily_date >= today_beijing:
                        return False

                reward_amount = COIN_CONFIG["DAILY_FIRST_CHAT_REWARD"]
                if row:
                    row.balance += reward_amount
                    row.last_daily_message_date = today_str
                else:
                    row = UserCoins(
                        user_id=uid,
                        balance=reward_amount,
                        last_daily_message_date=today_str,
                    )
                    session.add(row)

                tx = CoinTransaction(
                    user_id=uid, amount=reward_amount, reason="每日首次与AI对话奖励"
                )
                session.add(tx)

        log.info(f"用户 {user_id} 获得每日首次与AI对话奖励 ({reward_amount} 类脑币)。")
        return True

    async def add_item_to_shop(
        self,
        name: str,
        description: str,
        price: int,
        category: str,
        target: str = "self",
        effect_id: Optional[str] = None,
    ):
        async with AsyncSessionLocal() as session:
            existing_item = await session.execute(
                select(ShopItem).where(ShopItem.name == name)
            )
            existing = existing_item.scalar_one_or_none()

            if existing:
                existing.description = description
                existing.price = price
                existing.category = category
                existing.target = target
                existing.effect_id = effect_id
                existing.is_available = 1
            else:
                new_item = ShopItem(
                    name=name,
                    description=description,
                    price=price,
                    category=category,
                    target=target,
                    effect_id=effect_id,
                    cg_url=None,
                    is_available=1,
                )
                session.add(new_item)

            await session.commit()
            log.info(f"已添加或更新商品: {name} ({category})")

    async def get_items_by_category(self, category: str) -> list:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ShopItem)
                .where(ShopItem.category == category)
                .where(ShopItem.is_available == 1)
                .order_by(ShopItem.price)
            )
            items = result.scalars().all()
            return [
                {
                    "item_id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": item.price,
                    "category": item.category,
                    "target": item.target,
                    "effect_id": item.effect_id,
                    "cg_url": item.cg_url,
                    "is_available": item.is_available,
                }
                for item in items
            ]

    async def get_all_items(self) -> list:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ShopItem)
                .where(ShopItem.is_available == 1)
                .order_by(ShopItem.category, ShopItem.price)
            )
            items = result.scalars().all()
            return [
                {
                    "item_id": item.id,
                    "name": item.name,
                    "description": item.description,
                    "price": item.price,
                    "category": item.category,
                    "target": item.target,
                    "effect_id": item.effect_id,
                    "cg_url": item.cg_url,
                    "is_available": item.is_available,
                }
                for item in items
            ]

    async def get_item_by_id(self, item_id: int):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ShopItem).where(ShopItem.id == item_id)
            )
            item = result.scalar_one_or_none()
            if not item:
                return None
            return {
                "item_id": item.id,
                "name": item.name,
                "description": item.description,
                "price": item.price,
                "category": item.category,
                "target": item.target,
                "effect_id": item.effect_id,
                "cg_url": item.cg_url,
                "is_available": item.is_available,
            }

    async def purchase_item(
        self, user_id: int, guild_id: int, item_id: int, quantity: int = 1
    ) -> tuple[bool, str, Optional[int], bool, Optional[dict], Optional[str]]:
        item = await self.get_item_by_id(item_id)
        if not item:
            return False, "找不到该商品。", None, False, None, None

        total_cost = item["price"] * quantity
        current_balance = await self.get_balance(user_id)

        if current_balance < total_cost:
            return (
                False,
                f"你的余额不足！需要 {total_cost} 类脑币，但你只有 {current_balance}。",
                None,
                False,
                None,
                None,
            )

        new_balance = current_balance
        if total_cost > 0:
            reason = f"购买 {quantity}x {item['name']}"
            new_balance = await self.remove_coins(user_id, total_cost, reason)
            if new_balance is None:
                return False, "购买失败，无法扣除类脑币。", None, False, None, None

        item_target = item["target"]
        item_effect = item["effect_id"]

        if item_target == "ai":
            points_to_add = max(1, item["price"] // 10)
            (
                gift_success,
                gift_message,
            ) = await affection_service.increase_affection_for_gift(
                user_id, points_to_add
            )

            if gift_success:
                cg_url = _select_random_cg_url(item.get("cg_url"))
                return True, "", new_balance, False, None, cg_url
            else:
                await self.add_coins(
                    user_id, total_cost, f"送礼失败返还: {item['name']}"
                )
                log.warning(
                    f"用户 {user_id} 送礼失败，已返还 {total_cost} 类脑币。原因: {gift_message}"
                )
                return False, gift_message, current_balance, False, None, None

        elif item_target == "self" and item_effect:
            if item_effect == CLEAR_PERSONAL_MEMORY_ITEM_EFFECT_ID:
                from src.chat.features.personal_memory.services.personal_memory_service import (
                    personal_memory_service,
                )

                await personal_memory_service.clear_personal_memory(user_id)
                return (
                    True,
                    f"一道耀眼的闪光后，类脑娘关于 **{item['name']}** 的记忆...呃，不对，是类脑娘关于你的记忆被清除了。你们可以重新开始了。",
                    new_balance,
                    False,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == MANAGE_CONVERSATION_BLOCKS_EFFECT_ID:
                return (
                    True,
                    "show_conversation_blocks_panel",
                    new_balance,
                    False,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == VIEW_PERSONAL_MEMORY_ITEM_EFFECT_ID:
                from src.chat.features.personal_memory.services.personal_memory_service import (
                    personal_memory_service,
                )

                summary = await personal_memory_service.get_memory_summary(user_id)
                embed_data = {
                    "title": "午后闲谈",
                    "description": f"经过一次愉快的闲谈，你得知了在她心中，你的印象是这样的：\n\n>>> {summary}",
                }
                return (
                    True,
                    "你与类脑娘进行了一次成功的\u201c午后闲谈\u201d。",
                    new_balance,
                    False,
                    embed_data,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == PERSONAL_MEMORY_ITEM_EFFECT_ID:
                has_personal_memory = await self._has_personal_memory(user_id)

                if has_personal_memory:
                    return (
                        True,
                        f"你花费了 {total_cost} 类脑币来更新你的个人档案。",
                        new_balance,
                        True,
                        None,
                        _select_random_cg_url(item.get("cg_url")),
                    )
                else:
                    return (
                        True,
                        f"你已成功解锁 **{item['name']}**！现在类脑娘将开始为你记录个人记忆。",
                        new_balance,
                        True,
                        None,
                        _select_random_cg_url(item.get("cg_url")),
                    )
            elif item_effect == WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID:
                return (
                    True,
                    f"你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**。",
                    new_balance,
                    True,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == COMMUNITY_MEMBER_UPLOAD_EFFECT_ID:
                return (
                    True,
                    f"你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**。",
                    new_balance,
                    True,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == SELL_BODY_EVENT_SUBMISSION_EFFECT_ID:
                return (
                    True,
                    f"你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**。",
                    new_balance,
                    True,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == DISABLE_THREAD_COMMENTOR_EFFECT_ID:
                await self.set_warmup_preference(user_id, wants_warmup=False)
                return (
                    True,
                    f"你购买了 **{item['name']}**。从此，类脑娘将不再暖你的贴。",
                    new_balance,
                    False,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == BLOCK_THREAD_REPLIES_EFFECT_ID:
                await self._set_user_coins_field(user_id, blocks_thread_replies=1)
                log.info(f"用户 {user_id} 购买了告示牌，已禁用帖子回复功能。")
                return (
                    True,
                    f"你举起了 **{item['name']}**，上面写着禁止通行。从此，类脑娘将不再进入你的帖子。",
                    new_balance,
                    False,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == ENABLE_THREAD_COMMENTOR_EFFECT_ID:
                await self.set_warmup_preference(user_id, wants_warmup=True)
                return (
                    True,
                    f"你使用了 **{item['name']}**，枯萎的向日葵恢复了生机。类脑娘现在会重新暖你的贴了。",
                    new_balance,
                    False,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            elif item_effect == ENABLE_THREAD_REPLIES_EFFECT_ID:
                default_limit = 2
                default_duration = 60
                await self._set_user_coins_field(
                    user_id,
                    blocks_thread_replies=0,
                    thread_cooldown_limit=default_limit,
                    thread_cooldown_duration=default_duration,
                    thread_cooldown_seconds=None,
                )
                log.info(
                    f"用户 {user_id} 购买了通行许可，已重新启用帖子回复功能，并设置默认冷却 (limit={default_limit}, duration={default_duration})。"
                )
                return (
                    True,
                    f"你使用了 **{item['name']}**，花费了 {total_cost} 类脑币。现在你创建的所有帖子将默认拥有 **60秒2次** 的发言许可，你也可以随时通过弹出的窗口自定义规则。",
                    new_balance,
                    True,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
            else:
                return (
                    True,
                    f"购买成功！你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**。",
                    new_balance,
                    False,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )
        else:
            if item["category"] == "给类脑娘买点好吃的!":
                points_to_add = max(1, item["price"] // 10)
                (
                    meal_success,
                    meal_message,
                ) = await affection_service.increase_affection_for_gift(
                    user_id, points_to_add
                )

                if meal_success:
                    cg_url = _select_random_cg_url(item.get("cg_url"))
                    return (
                        True,
                        f"你花 {total_cost} 类脑币请类脑娘吃了 **{item['name']}**。",
                        new_balance,
                        False,
                        None,
                        cg_url,
                    )
                else:
                    await self.add_coins(
                        user_id, total_cost, f"请吃饭失败返还: {item['name']}"
                    )
                    log.warning(
                        f"用户 {user_id} 请类脑娘吃饭失败，已返还 {total_cost} 类脑币。原因: {meal_message}"
                    )
                    return False, meal_message, current_balance, False, None, None
            else:
                return (
                    True,
                    f"购买成功！你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**。",
                    new_balance,
                    False,
                    None,
                    _select_random_cg_url(item.get("cg_url")),
                )

    async def purchase_event_item(
        self, user_id: int, item_name: str, price: int
    ) -> tuple[bool, str, Optional[int]]:
        if price < 0:
            return False, "商品价格不能为负数。", None

        current_balance = await self.get_balance(user_id)
        if current_balance < price:
            return (
                False,
                f"你的余额不足！需要 {price} 类脑币，但你只有 {current_balance}。",
                None,
            )

        new_balance = current_balance
        if price > 0:
            reason = f"购买活动商品: {item_name}"
            new_balance = await self.remove_coins(user_id, price, reason)
            if new_balance is None:
                return False, "购买失败，无法扣除类脑币。", None

        return True, f"成功购买 {item_name}！", new_balance

    async def has_withered_sunflower(self, user_id: int) -> bool:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserCoins.has_withered_sunflower).where(UserCoins.user_id == uid)
            )
            val = result.scalar_one_or_none()
            return bool(val) if val else False

    async def blocks_thread_replies(self, user_id: int) -> bool:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserCoins.blocks_thread_replies).where(UserCoins.user_id == uid)
            )
            val = result.scalar_one_or_none()
            return bool(val) if val else False

    async def has_made_warmup_choice(self, user_id: int) -> bool:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserCoins.has_withered_sunflower).where(UserCoins.user_id == uid)
            )
            val = result.scalar_one_or_none()
            return val is not None

    async def set_warmup_preference(self, user_id: int, wants_warmup: bool):
        has_withered_sunflower = 0 if wants_warmup else 1
        await self._set_user_coins_field(
            user_id, has_withered_sunflower=has_withered_sunflower
        )
        log.info(f"用户 {user_id} 的暖贴偏好已设置为: {wants_warmup}")

    async def get_active_loan(self, user_id: int) -> Optional[dict]:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CoinLoan).where(
                    CoinLoan.user_id == uid, CoinLoan.status == "active"
                )
            )
            loan = result.scalar_one_or_none()
            if not loan:
                return None
            return {
                "loan_id": loan.id,
                "user_id": loan.user_id,
                "amount": loan.amount,
                "status": loan.status,
                "created_at": loan.created_at,
                "paid_at": loan.paid_at,
            }

    async def borrow_coins(self, user_id: int, amount: int) -> tuple[bool, str]:
        if amount <= 0:
            return False, "❌ 借款金额必须是正数。"

        max_loan = COIN_CONFIG["MAX_LOAN_AMOUNT"]
        if amount > max_loan:
            return False, f"❌ 单次最多只能借 {max_loan} 类脑币。"

        active_loan = await self.get_active_loan(user_id)
        if active_loan:
            return (
                False,
                f"❌ 你还有一笔 **{active_loan['amount']}** 类脑币的借款尚未还清，请先还款。",
            )

        try:
            await self.add_coins(user_id, amount, "从系统借款")

            uid = str(user_id)
            async with AsyncSessionLocal() as session:
                loan = CoinLoan(user_id=uid, amount=amount)
                session.add(loan)
                await session.commit()

            log.info(f"用户 {user_id} 成功借款 {amount} 类脑币。")
            return True, f"✅ 成功借款 **{amount}** 类脑币！"
        except Exception as e:
            log.error(f"用户 {user_id} 借款失败: {e}")
            return False, f"❌ 借款时发生未知错误: {e}"

    async def repay_loan(self, user_id: int) -> tuple[bool, str]:
        active_loan = await self.get_active_loan(user_id)
        if not active_loan:
            return False, "❌ 你当前没有需要偿还的贷款。"

        loan_amount = active_loan["amount"]
        current_balance = await self.get_balance(user_id)

        if current_balance < loan_amount:
            return (
                False,
                f"❌ 你的余额不足以偿还贷款。需要 **{loan_amount}**，你只有 **{current_balance}**。",
            )

        try:
            new_balance = await self.remove_coins(user_id, loan_amount, "偿还系统贷款")
            if new_balance is None:
                return False, "❌ 还款失败，无法扣除类脑币。"

            uid = str(user_id)
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(CoinLoan).where(CoinLoan.id == active_loan["loan_id"])
                )
                loan = result.scalar_one_or_none()
                if loan:
                    loan.status = "paid"
                    loan.paid_at = datetime.utcnow()
                    await session.commit()

            log.info(f"用户 {user_id} 成功偿还 {loan_amount} 类脑币的贷款。")
            return True, f"✅ 成功偿还 **{loan_amount}** 类脑币的贷款！"
        except Exception as e:
            log.error(f"用户 {user_id} 还款失败: {e}")
            return False, f"❌ 还款时发生未知错误: {e}"

    async def get_transaction_history(
        self, user_id: int, limit: int = 10, offset: int = 0
    ) -> list[dict]:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CoinTransaction)
                .where(CoinTransaction.user_id == uid)
                .order_by(desc(CoinTransaction.timestamp))
                .limit(limit)
                .offset(offset)
            )
            transactions = result.scalars().all()
            return [
                {
                    "timestamp": tx.timestamp.isoformat() if tx.timestamp else None,
                    "amount": tx.amount,
                    "reason": tx.reason,
                }
                for tx in transactions
            ]

    async def get_transaction_count(self, user_id: int) -> int:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count())
                .select_from(CoinTransaction)
                .where(CoinTransaction.user_id == uid)
            )
            return result.scalar() or 0

    async def get_thread_cooldown_settings(self, user_id: int) -> Optional[dict]:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserCoins).where(UserCoins.user_id == uid)
            )
            row = result.scalar_one_or_none()
            if not row:
                return None
            return {
                "thread_cooldown_seconds": row.thread_cooldown_seconds,
                "thread_cooldown_duration": row.thread_cooldown_duration,
                "thread_cooldown_limit": row.thread_cooldown_limit,
                "blocks_thread_replies": row.blocks_thread_replies,
            }

    async def update_thread_cooldown_settings(
        self, user_id: int, settings: dict
    ) -> None:
        await self._set_user_coins_field(
            user_id,
            thread_cooldown_seconds=settings.get("cooldown_seconds"),
            thread_cooldown_duration=settings.get("cooldown_duration"),
            thread_cooldown_limit=settings.get("cooldown_limit"),
        )
        log.info(f"已更新用户 {user_id} 的个人帖子冷却设置: {settings}")

    async def get_last_red_envelope_date(self, user_id: int) -> Optional[str]:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserCoins.last_red_envelope_date).where(UserCoins.user_id == uid)
            )
            return result.scalar_one_or_none()

    async def set_last_red_envelope_date(self, user_id: int, date: str) -> None:
        await self._set_user_coins_field(user_id, last_red_envelope_date=date)
        log.info(f"已更新用户 {user_id} 的红包领取日期为 {date}")

    async def _has_personal_memory(self, user_id: int) -> bool:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CommunityMemberProfile.personal_summary).where(
                    CommunityMemberProfile.discord_id == uid
                )
            )
            summary = result.scalars().first()
            return bool(summary and summary.strip())

    async def _set_user_coins_field(self, user_id: int, **fields) -> None:
        uid = str(user_id)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(UserCoins).where(UserCoins.user_id == uid).with_for_update()
                )
                row = result.scalar_one_or_none()
                if row:
                    for key, value in fields.items():
                        setattr(row, key, value)
                else:
                    row = UserCoins(user_id=uid, **fields)
                    session.add(row)


coin_service = CoinService()
