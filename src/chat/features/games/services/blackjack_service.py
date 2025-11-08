import asyncio
import logging
from typing import Optional

from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)


class BlackjackGame:
    """Represents a single game of blackjack."""

    def __init__(self, user_id: int, bet_amount: int, game_state: str):
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.game_state = game_state


class BlackjackService:
    def __init__(self, db_manager):
        self._db_manager = db_manager
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initializes database table for blackjack games and cleans up stale games."""
        # 首先在主数据库逻辑中创建表
        await self._db_manager._execute(self._db_manager._init_database_logic)
        log.info("Blackjack games table initialized.")
        # --- 新增：在启动时清理过期游戏 ---
        await self.cleanup_stale_games()

    async def cleanup_stale_games(self):
        """Finds and refunds games that have been active for too long."""
        # 延迟导入以避免循环依赖问题
        coin_service = __import__(
            "src.chat.features.odysseia_coin.service.coin_service",
            fromlist=["coin_service"],
        ).coin_service

        log.info("正在检查过期的21点游戏...")
        # 查找24小时前的游戏
        rows = await self._db_manager._execute(
            self._db_manager._db_transaction,
            "SELECT user_id, bet_amount FROM blackjack_games WHERE created_at <= datetime('now', '-24 hours')",
            (),
            fetch="all",
        )
        if not rows:
            log.info("未发现过期的21点游戏。")
            return

        cleaned_count = 0
        for user_id, bet_amount in rows:
            try:
                log.warning(f"正在为用户 {user_id} 清理过期游戏，赌注为 {bet_amount}。")
                # 退还赌注
                await coin_service.add_coins(user_id, bet_amount, "21点过期游戏退款")
                # 删除游戏记录
                await self.delete_game(user_id)
                log.info(f"已成功为用户 {user_id} 退款 {bet_amount} 并删除过期游戏。")
                cleaned_count += 1
            except Exception as e:
                log.error(
                    f"为用户 {user_id} 清理过期游戏失败。错误: {e}",
                    exc_info=True,
                )
        if cleaned_count > 0:
            log.info(f"已完成对 {cleaned_count} 个过期21点游戏的清理。")

    async def create_game(
        self, user_id: int, bet_amount: int
    ) -> Optional[BlackjackGame]:
        """
        Creates a new game record for a user.
        Returns new game if creation is successful, None otherwise.
        """
        async with self._lock:
            # Check if a game already exists
            existing_game = await self.get_active_game(user_id)
            if existing_game:
                log.warning(f"用户 {user_id} 试图在已有活跃游戏时开始新游戏。")
                return None

            await self._db_manager._execute(
                self._db_manager._db_transaction,
                "INSERT INTO blackjack_games (user_id, bet_amount, game_state) VALUES (?, ?, ?)",
                (user_id, bet_amount, "active"),
                commit=True,
            )
            log.info(f"为用户 {user_id} 创建了新的21点游戏，赌注为 {bet_amount}。")
            return BlackjackGame(user_id, bet_amount, "active")

    async def get_active_game(self, user_id: int) -> Optional[BlackjackGame]:
        """Retrieves current active game for a user."""
        row = await self._db_manager._execute(
            self._db_manager._db_transaction,
            "SELECT user_id, bet_amount, game_state FROM blackjack_games WHERE user_id = ?",
            (user_id,),
            fetch="one",
        )
        if row:
            return BlackjackGame(user_id=row[0], bet_amount=row[1], game_state=row[2])
        return None

    async def double_down(
        self, user_id: int, double_cost: int
    ) -> Optional[BlackjackGame]:
        """
        Doubles down bet for an active game.
        """
        async with self._lock:
            game = await self.get_active_game(user_id)
            if not game or game.game_state != "active":
                log.warning(f"用户 {user_id} 无法双倍下注，游戏状态不是 'active'。")
                return None

            new_bet_amount = game.bet_amount + double_cost
            await self._db_manager._execute(
                self._db_manager._db_transaction,
                "UPDATE blackjack_games SET bet_amount = ?, game_state = ? WHERE user_id = ?",
                (new_bet_amount, "doubled", user_id),
                commit=True,
            )
            log.info(f"用户 {user_id} 双倍下注成功。新赌注: {new_bet_amount}。")
            game.bet_amount = new_bet_amount
            game.game_state = "doubled"
            return game

    async def delete_game(self, user_id: int) -> bool:
        """
        Deletes a game record for a user.
        Returns True if a record was deleted, False otherwise.
        """
        async with self._lock:
            result = await self._db_manager._execute(
                self._db_manager._db_transaction,
                "DELETE FROM blackjack_games WHERE user_id = ?",
                (user_id,),
                fetch="rowcount",
                commit=True,
            )
            # result will be > 0 if a row was deleted
            if result > 0:
                log.info(f"已删除用户 {user_id} 的游戏。")
                return True
            log.warning(f"尝试为用户 {user_id} 删除游戏，但未找到活跃游戏。")
            return False


# --- Singleton Instance ---
blackjack_service = BlackjackService(chat_db_manager)
