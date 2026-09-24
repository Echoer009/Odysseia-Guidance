import logging
from typing import List, Dict, Any, Optional

from src.chat.services.event_service import event_service
from src.chat.utils.database import ChatDatabaseManager, chat_db_manager

log = logging.getLogger(__name__)


class FactionService:
    """
    处理与活动派系积分相关的所有业务逻辑。
    """

    def __init__(self, db_manager: ChatDatabaseManager):
        """
        初始化 FactionService。

        Args:
            db_manager: ChatDatabaseManager 的实例。
        """
        self.db = db_manager
        self.event_service = event_service

    async def add_points_to_faction(
        self, user_id: int, item_id: str, points_to_add: int, faction_id: str
    ) -> bool:
        """
        为一个派系增加点数，并记录贡献日志。
        """
        active_event = self.event_service.get_active_event()
        if not active_event:
            log.error("当前没有激活的活动，无法增加点数。")
            return False

        event_id = active_event["event_id"]

        try:
            # 使用事务来确保数据一致性
            # 1. 更新或插入派系分数
            update_query = """
                INSERT INTO event_faction_points (event_id, faction_id, total_points)
                VALUES (?, ?, ?)
                ON CONFLICT(event_id, faction_id) DO UPDATE SET
                    total_points = total_points + excluded.total_points;
            """
            await self.db._execute(
                self.db._db_transaction,
                update_query,
                (event_id, faction_id, points_to_add),
                commit=True,
            )

            # 2. 记录贡献日志
            log_query = """
                INSERT INTO event_contribution_log (user_id, event_id, faction_id, item_id, points_contributed)
                VALUES (?, ?, ?, ?, ?);
            """
            await self.db._execute(
                self.db._db_transaction,
                log_query,
                (user_id, event_id, faction_id, item_id, points_to_add),
                commit=True,
            )

            log.info(f"成功为派系 '{faction_id}' 增加了 {points_to_add} 点分数。")
            return True

        except Exception as e:
            log.error(f"为派系增加点数时发生错误: {e}", exc_info=True)
            return False

    async def get_faction_leaderboard(
        self, event_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取活动的派系点数排行榜，缺省时使用当前激活的活动。
        """
        if event_id is None:
            active_event = self.event_service.get_active_event()
            if not active_event:
                return []
            event_id = active_event["event_id"]

        query = """
            SELECT faction_id, total_points
            FROM event_faction_points
            WHERE event_id = ?
            ORDER BY total_points DESC;
        """
        rows = await self.db._execute(
            self.db._db_transaction, query, (event_id,), fetch="all"
        )

        return [
            {"faction_id": row["faction_id"], "total_points": row["total_points"]}
            for row in rows
        ]

    async def determine_winner_and_end_event(
        self, event_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        结算活动：决定获胜派系并写入 event_settlements 结算记录。
        已有结算记录则跳过（幂等）。若该活动仍处于激活状态，
        仍会调用 event_service.set_winning_faction 保留内存行为。

        Args:
            event_id: 要结算的活动 ID，缺省时使用当前激活的活动。

        Returns:
            获胜派系信息 {"faction_id", "total_points"}，未结算时返回 None。
        """
        log.info("正在执行活动结算逻辑...")

        target_event_id: str
        if event_id is None:
            active_event = self.event_service.get_active_event()
            if not active_event:
                log.warning("当前没有激活的活动，无法结算。")
                return None
            target_event_id = active_event["event_id"]
        else:
            target_event_id = event_id

        # 幂等保护：已有结算记录则跳过
        if await self.db.get_event_settlement(target_event_id):
            log.info(f"活动 '{target_event_id}' 已有结算记录，跳过结算。")
            return None

        leaderboard = await self.get_faction_leaderboard(target_event_id)
        if not leaderboard:
            log.warning(f"活动 '{target_event_id}' 的排行榜为空，无法决定获胜派系。")
            return None

        winner = leaderboard[0]
        winning_faction_id = winner["faction_id"]

        log.info(
            f"获胜派系是: {winning_faction_id}，总点数: {winner['total_points']}"
        )

        await self.db.insert_event_settlement(
            target_event_id, winning_faction_id, winner["total_points"]
        )

        # 保留内存行为：仅当该活动仍处于激活状态时同步设置获胜派系
        active_event = self.event_service.get_active_event()
        if active_event and active_event.get("event_id") == target_event_id:
            self.event_service.set_winning_faction(winning_faction_id)

        return winner


# --- 单例实例 ---
# 现在 FactionService 依赖于 ChatDatabaseManager，
# 我们可以创建一个默认实例供其他模块使用。
faction_service = FactionService(chat_db_manager)
