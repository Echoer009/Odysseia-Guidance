import logging
from datetime import datetime, timezone
from typing import Optional

from src.chat.utils.database import chat_db_manager
from src.chat.config.chat_config import COIN_CONFIG
from ...affection.service.affection_service import affection_service

log = logging.getLogger(__name__)

# --- 特殊商品效果ID ---
PERSONAL_MEMORY_ITEM_EFFECT_ID = "unlock_personal_memory"
WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID = "contribute_to_world_book"
COMMUNITY_MEMBER_UPLOAD_EFFECT_ID = "upload_community_member"
DISABLE_THREAD_COMMENTOR_EFFECT_ID = "disable_thread_commentor"
BLOCK_THREAD_REPLIES_EFFECT_ID = "block_thread_replies"
ENABLE_THREAD_COMMENTOR_EFFECT_ID = "enable_thread_commentor"
ENABLE_THREAD_REPLIES_EFFECT_ID = "enable_thread_replies"


class CoinService:
    """处理与类脑币相关的所有业务逻辑"""

    def __init__(self):
        pass

    async def get_balance(self, user_id: int) -> int:
        """获取用户的类脑币余额"""
        query = "SELECT balance FROM user_coins WHERE user_id = ?"
        result = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (user_id,), fetch="one"
        )
        return result["balance"] if result else 0

    async def add_coins(self, user_id: int, amount: int, reason: str) -> int:
        """
        为用户增加类脑币并记录交易。
        返回新的余额。
        """
        if amount <= 0:
            raise ValueError("增加的金额必须为正数")

        def _transaction():
            import sqlite3

            conn = None
            try:
                conn = sqlite3.connect(chat_db_manager.db_path)
                cursor = conn.cursor()
                # 插入或更新用户余额
                cursor.execute(
                    """
                    INSERT INTO user_coins (user_id, balance) VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance;
                """,
                    (user_id, amount),
                )

                # 记录交易
                cursor.execute(
                    """
                    INSERT INTO coin_transactions (user_id, amount, reason)
                    VALUES (?, ?, ?);
                """,
                    (user_id, amount, reason),
                )

                # 获取新余额
                cursor.execute(
                    "SELECT balance FROM user_coins WHERE user_id = ?", (user_id,)
                )
                new_balance = cursor.fetchone()[0]

                conn.commit()
                log.info(
                    f"用户 {user_id} 获得 {amount} 类脑币，原因: {reason}。新余额: {new_balance}"
                )
                return new_balance
            except Exception as e:
                if conn:
                    conn.rollback()
                log.error(f"为用户 {user_id} 增加类脑币失败: {e}")
                raise
            finally:
                if conn:
                    conn.close()

        return await chat_db_manager._execute(_transaction)

    async def remove_coins(
        self, user_id: int, amount: int, reason: str
    ) -> Optional[int]:
        """
        扣除用户的类脑币并记录交易。
        如果余额不足，则返回 None，否则返回新的余额。
        """
        if amount <= 0:
            raise ValueError("扣除的金额必须为正数")

        current_balance = await self.get_balance(user_id)
        if current_balance < amount:
            log.warning(
                f"用户 {user_id} 扣款失败，余额不足。需要 {amount}，拥有 {current_balance}"
            )
            return None

        def _transaction():
            import sqlite3

            conn = None
            try:
                conn = sqlite3.connect(chat_db_manager.db_path)
                cursor = conn.cursor()
                # 更新余额
                cursor.execute(
                    "UPDATE user_coins SET balance = balance - ? WHERE user_id = ?",
                    (amount, user_id),
                )

                # 记录交易
                cursor.execute(
                    """
                    INSERT INTO coin_transactions (user_id, amount, reason)
                    VALUES (?, ?, ?);
                """,
                    (user_id, -amount, reason),
                )

                # 获取新余额
                cursor.execute(
                    "SELECT balance FROM user_coins WHERE user_id = ?", (user_id,)
                )
                new_balance = cursor.fetchone()[0]

                conn.commit()
                log.info(
                    f"用户 {user_id} 消费 {amount} 类脑币，原因: {reason}。新余额: {new_balance}"
                )
                return new_balance
            except Exception as e:
                if conn:
                    conn.rollback()
                log.error(f"为用户 {user_id} 扣除类脑币失败: {e}")
                raise
            finally:
                if conn:
                    conn.close()

        return await chat_db_manager._execute(_transaction)

    async def grant_daily_message_reward(self, user_id: int) -> bool:
        """
        检查并授予每日首次发言奖励。
        如果成功授予奖励，返回 True，否则返回 False。
        """
        from datetime import timedelta

        def _transaction():
            import sqlite3

            conn = None
            try:
                conn = sqlite3.connect(chat_db_manager.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT last_daily_message_date FROM user_coins WHERE user_id = ?",
                    (user_id,),
                )
                result = cursor.fetchone()

                # 使用北京时间 (UTC+8)
                beijing_tz = timezone(timedelta(hours=8))
                today_beijing = datetime.now(beijing_tz).date()

                if result:
                    last_daily_str = result[0]
                    if last_daily_str:
                        last_daily_date = datetime.fromisoformat(last_daily_str).date()
                        if last_daily_date >= today_beijing:
                            return False  # 今天已经发过了

                # 更新最后发言日期并增加金币
                reward_amount = COIN_CONFIG["DAILY_FIRST_CHAT_REWARD"]
                cursor.execute(
                    """
                    INSERT INTO user_coins (user_id, balance, last_daily_message_date)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        balance = balance + ?,
                        last_daily_message_date = excluded.last_daily_message_date;
                """,
                    (user_id, reward_amount, today_beijing.isoformat(), reward_amount),
                )

                # 记录交易
                cursor.execute(
                    """
                    INSERT INTO coin_transactions (user_id, amount, reason)
                    VALUES (?, ?, '每日首次与AI对话奖励');
                """,
                    (user_id, reward_amount),
                )

                conn.commit()
                log.info(
                    f"用户 {user_id} 获得每日首次与AI对话奖励 ({reward_amount} 类脑币)。"
                )
                return True
            except Exception as e:
                if conn:
                    conn.rollback()
                log.error(f"处理用户 {user_id} 的每日奖励失败: {e}")
                raise
            finally:
                if conn:
                    conn.close()

        return await chat_db_manager._execute(_transaction)

    async def add_item_to_shop(
        self,
        name: str,
        description: str,
        price: int,
        category: str,
        target: str = "self",
        effect_id: Optional[str] = None,
    ):
        """向商店添加或更新一件商品"""
        query = """
            INSERT INTO shop_items (name, description, price, category, target, effect_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description = excluded.description,
                price = excluded.price,
                category = excluded.category,
                target = excluded.target,
                effect_id = excluded.effect_id,
                is_available = 1;
        """
        await chat_db_manager._execute(
            chat_db_manager._db_transaction,
            query,
            (name, description, price, category, target, effect_id),
            commit=True,
        )
        log.info(f"已添加或更新商品: {name} ({category})")

    async def get_items_by_category(self, category: str) -> list:
        """根据类别获取所有可用的商品"""
        query = "SELECT * FROM shop_items WHERE category = ? AND is_available = 1 ORDER BY price ASC"
        return await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (category,), fetch="all"
        )

    async def get_all_items(self) -> list:
        """获取所有可用的商品"""
        query = "SELECT * FROM shop_items WHERE is_available = 1 ORDER BY category, price ASC"
        return await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (), fetch="all"
        )

    async def get_item_by_id(self, item_id: int):
        """通过ID获取商品信息"""
        query = "SELECT * FROM shop_items WHERE item_id = ?"
        return await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (item_id,), fetch="one"
        )

    async def purchase_item(
        self, user_id: int, guild_id: int, item_id: int, quantity: int = 1
    ) -> tuple[bool, str, Optional[int], bool, bool]:
        """
        处理用户购买商品的逻辑。
        返回一个元组 (success: bool, message: str, new_balance: Optional[int], should_show_modal: bool, should_generate_gift_response: bool)。
        """
        item = await self.get_item_by_id(item_id)
        if not item:
            return False, "找不到该商品。", None, False, False

        total_cost = item["price"] * quantity
        current_balance = await self.get_balance(user_id)

        if current_balance < total_cost:
            return (
                False,
                f"你的余额不足！需要 {total_cost} 类脑币，但你只有 {current_balance}。",
                None,
                False,
                False,
            )

        # 扣款并记录（仅当费用大于0时）
        new_balance = current_balance
        if total_cost > 0:
            reason = f"购买 {quantity}x {item['name']}"
            new_balance = await self.remove_coins(user_id, total_cost, reason)
            if new_balance is None:
                return False, "购买失败，无法扣除类脑币。", None, False, False

        # 根据物品目标执行不同操作
        item_target = item["target"]
        item_effect = item["effect_id"]

        if item_target == "ai":
            # --- 送给类脑娘的物品 ---
            points_to_add = max(1, item["price"] // 10)
            (
                gift_success,
                gift_message,
            ) = await affection_service.increase_affection_for_gift(
                user_id, guild_id, points_to_add
            )

            if gift_success:
                # 购买成功，返回空消息，并标记需要生成AI回应
                return True, "", new_balance, False, True
            else:
                # 送礼失败，回滚交易
                await self.add_coins(
                    user_id, total_cost, f"送礼失败返还: {item['name']}"
                )
                log.warning(
                    f"用户 {user_id} 送礼失败，已返还 {total_cost} 类脑币。原因: {gift_message}"
                )
                return False, gift_message, current_balance, False, False

        elif item_target == "self" and item_effect:
            # --- 给自己用且有立即效果的物品 ---
            if item_effect == "coffee_chat_cooldown":
                from datetime import timedelta

                expires_at = datetime.now(timezone.utc) + timedelta(days=1)

                def _transaction():
                    import sqlite3

                    conn = None
                    try:
                        conn = sqlite3.connect(chat_db_manager.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE user_coins
                            SET coffee_effect_expires_at = ?
                            WHERE user_id = ?
                        """,
                            (expires_at.isoformat(), user_id),
                        )

                        # 如果用户不存在于表中，需要插入
                        if cursor.rowcount == 0:
                            cursor.execute(
                                """
                                INSERT INTO user_coins (user_id, balance, coffee_effect_expires_at)
                                VALUES (?, 0, ?)
                                ON CONFLICT(user_id) DO UPDATE SET
                                    coffee_effect_expires_at = excluded.coffee_effect_expires_at;
                            """,
                                (user_id, expires_at.isoformat()),
                            )

                        conn.commit()
                        log.info(
                            f"用户 {user_id} 购买了咖啡，聊天冷却效果持续到 {expires_at.isoformat()}"
                        )
                    except Exception as e:
                        if conn:
                            conn.rollback()
                        log.error(f"为用户 {user_id} 更新咖啡效果时出错: {e}")
                        raise
                    finally:
                        if conn:
                            conn.close()

                await chat_db_manager._execute(_transaction)

                return (
                    True,
                    f"你使用了 **{item['name']}**，花费了 {total_cost} 类脑币。在接下来的24小时内，你与类脑娘的对话冷却时间将大幅缩短！",
                    new_balance,
                    False,
                    False,
                )
            elif item_effect == PERSONAL_MEMORY_ITEM_EFFECT_ID:
                # 检查用户是否已经拥有个人记忆功能
                user_profile = await chat_db_manager.get_user_profile(user_id)
                has_personal_memory = (
                    user_profile and user_profile["has_personal_memory"]
                )

                if has_personal_memory:
                    # 用户已经拥有该功能，扣除10个类脑币作为更新费用
                    # 用户已经拥有该功能，同样需要弹出模态框让他们编辑
                    return (
                        True,
                        f"你花费了 {total_cost} 类脑币来更新你的个人档案。",
                        new_balance,
                        True,
                        False,
                    )
                else:
                    # 用户尚未拥有该功能，扣除500个类脑币并解锁功能
                    from src.chat.features.personal_memory.services.personal_memory_service import (
                        personal_memory_service,
                    )

                    await personal_memory_service.unlock_feature(user_id)
                    return (
                        True,
                        f"你已成功解锁 **{item['name']}**！现在类脑娘将开始为你记录个人记忆。",
                        new_balance,
                        True,
                        False,
                    )
            elif item_effect == WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID:
                # 购买"知识纸条"商品，需要弹出模态窗口
                return (
                    True,
                    f"你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**。",
                    new_balance,
                    True,
                    False,
                )
            elif item_effect == COMMUNITY_MEMBER_UPLOAD_EFFECT_ID:
                # 购买"社区成员档案上传"商品，需要弹出模态窗口
                return (
                    True,
                    f"你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**。",
                    new_balance,
                    True,
                    False,
                )
            elif item_effect == DISABLE_THREAD_COMMENTOR_EFFECT_ID:
                # 购买“枯萎向日葵”，禁用暖贴功能
                def _transaction():
                    import sqlite3

                    conn = None
                    try:
                        conn = sqlite3.connect(chat_db_manager.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE user_coins
                            SET has_withered_sunflower = 1
                            WHERE user_id = ?
                        """,
                            (user_id,),
                        )
                        if cursor.rowcount == 0:
                            cursor.execute(
                                """
                                INSERT INTO user_coins (user_id, has_withered_sunflower)
                                VALUES (?, 1)
                                ON CONFLICT(user_id) DO UPDATE SET
                                    has_withered_sunflower = 1;
                            """,
                                (user_id,),
                            )
                        conn.commit()
                        log.info(f"用户 {user_id} 购买了枯萎向日葵，已禁用暖贴功能。")
                    except Exception as e:
                        if conn:
                            conn.rollback()
                        log.error(f"为用户 {user_id} 更新枯萎向日葵状态时出错: {e}")
                        raise
                    finally:
                        if conn:
                            conn.close()

                await chat_db_manager._execute(_transaction)
                return (
                    True,
                    f"你“购买”了 **{item['name']}**。从此，类脑娘将不再暖你的贴。",
                    new_balance,
                    False,
                    False,
                )
            elif item_effect == BLOCK_THREAD_REPLIES_EFFECT_ID:

                def _transaction():
                    import sqlite3

                    conn = None
                    try:
                        conn = sqlite3.connect(chat_db_manager.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            """
                            UPDATE user_coins
                            SET blocks_thread_replies = 1
                            WHERE user_id = ?
                        """,
                            (user_id,),
                        )
                        if cursor.rowcount == 0:
                            cursor.execute(
                                """
                                INSERT INTO user_coins (user_id, blocks_thread_replies)
                                VALUES (?, 1)
                                ON CONFLICT(user_id) DO UPDATE SET
                                    blocks_thread_replies = 1;
                            """,
                                (user_id,),
                            )
                        conn.commit()
                        log.info(f"用户 {user_id} 购买了告示牌，已禁用帖子回复功能。")
                    except Exception as e:
                        if conn:
                            conn.rollback()
                        log.error(f"为用户 {user_id} 更新告示牌状态时出错: {e}")
                        raise
                    finally:
                        if conn:
                            conn.close()

                await chat_db_manager._execute(_transaction)
                return (
                    True,
                    f"你举起了 **{item['name']}**，上面写着“禁止通行”。从此，类脑娘将不再进入你的帖子。",
                    new_balance,
                    False,
                    False,
                )
            elif item_effect == ENABLE_THREAD_COMMENTOR_EFFECT_ID:
                # 购买“魔法向日葵”，重新启用暖贴功能
                def _transaction():
                    import sqlite3

                    conn = sqlite3.connect(chat_db_manager.db_path)
                    cursor = conn.cursor()
                    try:
                        cursor.execute(
                            "UPDATE user_coins SET has_withered_sunflower = 0 WHERE user_id = ?",
                            (user_id,),
                        )
                        conn.commit()
                        log.info(
                            f"用户 {user_id} 购买了魔法向日葵，已重新启用暖贴功能。"
                        )
                    finally:
                        conn.close()

                await chat_db_manager._execute(_transaction)
                return (
                    True,
                    f"你使用了 **{item['name']}**，枯萎的向日葵恢复了生机。类脑娘现在会重新暖你的贴了。",
                    new_balance,
                    False,
                    False,
                )
            elif item_effect == ENABLE_THREAD_REPLIES_EFFECT_ID:
                # 购买“通行许可”，重新启用帖子回复并设置默认CD
                def _transaction():
                    import sqlite3

                    conn = sqlite3.connect(chat_db_manager.db_path)
                    cursor = conn.cursor()
                    try:
                        # 设置默认值：60秒2次
                        default_limit = 2
                        default_duration = 60

                        cursor.execute(
                            """
                            INSERT INTO user_coins (user_id, blocks_thread_replies, thread_cooldown_limit, thread_cooldown_duration, thread_cooldown_seconds)
                            VALUES (?, 0, ?, ?, NULL)
                            ON CONFLICT(user_id) DO UPDATE SET
                                blocks_thread_replies = 0,
                                thread_cooldown_limit = excluded.thread_cooldown_limit,
                                thread_cooldown_duration = excluded.thread_cooldown_duration,
                                thread_cooldown_seconds = NULL;
                        """,
                            (user_id, default_limit, default_duration),
                        )

                        conn.commit()
                        log.info(
                            f"用户 {user_id} 购买了通行许可，已重新启用帖子回复功能，并设置默认冷却 (limit={default_limit}, duration={default_duration})。"
                        )
                    finally:
                        conn.close()

                await chat_db_manager._execute(_transaction)

                return (
                    True,
                    f"你使用了 **{item['name']}**，花费了 {total_cost} 类脑币。现在你创建的所有帖子将默认拥有 **60秒2次** 的发言许可，你也可以随时通过弹出的窗口自定义规则。",
                    new_balance,
                    True,
                    False,
                )
            else:
                # 其他未知效果，暂时先放入背包
                await self._add_item_to_inventory(user_id, item_id, quantity)
                return (
                    True,
                    f"购买成功！你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**，已放入你的背包。",
                    new_balance,
                    False,
                    False,
                )
        else:
            # --- 普通物品，放入背包 ---
            await self._add_item_to_inventory(user_id, item_id, quantity)
            return (
                True,
                f"购买成功！你花费了 {total_cost} 类脑币购买了 {quantity}x **{item['name']}**，已放入你的背包。",
                new_balance,
                False,
                False,
            )

    async def _add_item_to_inventory(self, user_id: int, item_id: int, quantity: int):
        """将物品添加到用户背包的内部方法"""

        def _transaction():
            import sqlite3

            conn = None
            try:
                conn = sqlite3.connect(chat_db_manager.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT inventory_id FROM user_inventory WHERE user_id = ? AND item_id = ?",
                    (user_id, item_id),
                )
                existing = cursor.fetchone()
                if existing:
                    cursor.execute(
                        "UPDATE user_inventory SET quantity = quantity + ? WHERE inventory_id = ?",
                        (quantity, existing[0]),
                    )
                else:
                    cursor.execute(
                        "INSERT INTO user_inventory (user_id, item_id, quantity) VALUES (?, ?, ?)",
                        (user_id, item_id, quantity),
                    )
                conn.commit()
            except Exception:
                if conn:
                    conn.rollback()
                raise
            finally:
                if conn:
                    conn.close()

        await chat_db_manager._execute(_transaction)

    async def get_user_cooldown_type(self, user_id: int) -> str:
        """
        获取用户的冷却类型 ('default' 或 'coffee')。
        """
        query = "SELECT coffee_effect_expires_at FROM user_coins WHERE user_id = ?"
        result = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (user_id,), fetch="one"
        )

        if result and result["coffee_effect_expires_at"]:
            try:
                expires_at = datetime.fromisoformat(result["coffee_effect_expires_at"])
                if expires_at > datetime.now(timezone.utc):
                    return "coffee"
            except (ValueError, TypeError):
                # 如果日期格式不正确或为 None，则忽略
                pass

        return "default"

    async def has_withered_sunflower(self, user_id: int) -> bool:
        """检查用户是否拥有枯萎向日葵（即是否禁用了暖贴功能）"""
        query = "SELECT has_withered_sunflower FROM user_coins WHERE user_id = ?"
        result = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (user_id,), fetch="one"
        )
        return (
            result["has_withered_sunflower"]
            if result and result["has_withered_sunflower"]
            else False
        )

    async def blocks_thread_replies(self, user_id: int) -> bool:
        """检查用户是否拥有告示牌（即是否禁用了帖子回复功能）"""
        query = "SELECT blocks_thread_replies FROM user_coins WHERE user_id = ?"
        result = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (user_id,), fetch="one"
        )
        return (
            result["blocks_thread_replies"]
            if result and result["blocks_thread_replies"]
            else False
        )

    async def transfer_coins(
        self, sender_id: int, receiver_id: int, amount: int
    ) -> tuple[bool, str, Optional[int]]:
        """
        处理用户之间的转账。
        返回 (success, message, new_balance)。
        """
        if sender_id == receiver_id:
            return False, "❌ 你不能给自己转账。", None

        if amount <= 0:
            return False, "❌ 转账金额必须是正数。", None

        tax = int(amount * COIN_CONFIG["TRANSFER_TAX_RATE"])
        total_deduction = amount + tax

        sender_balance = await self.get_balance(sender_id)
        if sender_balance < total_deduction:
            return (
                False,
                f"❌ 你的余额不足以完成转账。需要 {total_deduction} (包含 {tax} 税费)，你只有 {sender_balance}。",
                None,
            )

        # 使用事务确保操作的原子性
        def _transaction():
            import sqlite3

            conn = None
            try:
                conn = sqlite3.connect(chat_db_manager.db_path)
                cursor = conn.cursor()

                # 扣除发送者余额
                cursor.execute(
                    "UPDATE user_coins SET balance = balance - ? WHERE user_id = ?",
                    (total_deduction, sender_id),
                )
                cursor.execute(
                    "INSERT INTO coin_transactions (user_id, amount, reason) VALUES (?, ?, ?)",
                    (sender_id, -total_deduction, f"转账给用户 {receiver_id} (含税)"),
                )

                # 增加接收者余额
                cursor.execute(
                    "INSERT INTO user_coins (user_id, balance) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance;",
                    (receiver_id, amount),
                )
                cursor.execute(
                    "INSERT INTO coin_transactions (user_id, amount, reason) VALUES (?, ?, ?)",
                    (receiver_id, amount, f"收到来自用户 {sender_id} 的转账"),
                )

                # 获取发送者新余额
                cursor.execute(
                    "SELECT balance FROM user_coins WHERE user_id = ?", (sender_id,)
                )
                new_balance = cursor.fetchone()[0]

                conn.commit()
                log.info(
                    f"用户 {sender_id} 成功转账 {amount} 类脑币给用户 {receiver_id}，税费 {tax}。"
                )
                return new_balance
            except Exception as e:
                if conn:
                    conn.rollback()
                log.error(
                    f"转账失败: 从 {sender_id} 到 {receiver_id}，金额 {amount}。错误: {e}"
                )
                raise

        try:
            new_balance = await chat_db_manager._execute(_transaction)
            return (
                True,
                f"✅ 转账成功！你向 <@{receiver_id}> 转账了 **{amount}** 类脑币，并支付了 **{tax}** 的税费。",
                new_balance,
            )
        except Exception as e:
            return False, f"❌ 转账时发生未知错误: {e}", None

    async def get_active_loan(self, user_id: int) -> Optional[dict]:
        """获取用户当前未还清的贷款"""
        query = "SELECT * FROM coin_loans WHERE user_id = ? AND status = 'active'"
        result = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, (user_id,), fetch="one"
        )
        return dict(result) if result else None

    async def borrow_coins(self, user_id: int, amount: int) -> tuple[bool, str]:
        """处理用户借款"""
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

            query = "INSERT INTO coin_loans (user_id, amount) VALUES (?, ?)"
            await chat_db_manager._execute(
                chat_db_manager._db_transaction, query, (user_id, amount), commit=True
            )

            log.info(f"用户 {user_id} 成功借款 {amount} 类脑币。")
            return True, f"✅ 成功借款 **{amount}** 类脑币！"
        except Exception as e:
            log.error(f"用户 {user_id} 借款失败: {e}")
            return False, f"❌ 借款时发生未知错误: {e}"

    async def repay_loan(self, user_id: int) -> tuple[bool, str]:
        """处理用户还款"""
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

            query = "UPDATE coin_loans SET status = 'paid', paid_at = CURRENT_TIMESTAMP WHERE loan_id = ?"
            await chat_db_manager._execute(
                chat_db_manager._db_transaction,
                query,
                (active_loan["loan_id"],),
                commit=True,
            )

            log.info(f"用户 {user_id} 成功偿还 {loan_amount} 类脑币的贷款。")
            return True, f"✅ 成功偿还 **{loan_amount}** 类脑币的贷款！"
        except Exception as e:
            log.error(f"用户 {user_id} 还款失败: {e}")
            return False, f"❌ 还款时发生未知错误: {e}"


async def _setup_initial_items():
    """设置商店的初始商品（覆盖逻辑）"""
    log.info("正在设置商店初始商品...")

    # --- 新增：先删除所有现有商品以确保覆盖 ---
    delete_query = "DELETE FROM shop_items"
    await chat_db_manager._execute(
        chat_db_manager._db_transaction, delete_query, commit=True
    )
    log.info("已删除所有旧的商店商品。")
    # --- 结束 ---

    # 从配置文件导入商品列表
    from src.chat.config.shop_config import SHOP_ITEMS

    for name, desc, price, cat, target, effect in SHOP_ITEMS:
        await coin_service.add_item_to_shop(name, desc, price, cat, target, effect)
    log.info("商店初始商品设置完毕。")


# 单例实例
coin_service = CoinService()

# 在服务实例化后，这个函数需要由主程序在启动时调用
