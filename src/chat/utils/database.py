import sqlite3
import json
import logging
import os
import asyncio
from functools import partial
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timezone, timedelta
from src.chat.config import chat_config

# --- 常量定义 ---
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "chat.db")

# --- 日志记录器 ---
log = logging.getLogger(__name__)


# --- 辅助函数：获取北京时间的当前日期字符串 ---
def get_beijing_today_str() -> str:
    """获取北京时间（UTC+8）的当前日期字符串，格式为 YYYY-MM-DD。"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz).strftime("%Y-%m-%d")


class ChatDatabaseManager:
    """管理所有与聊天模块相关的 SQLite 数据库的异步交互。"""

    def __init__(self, db_path: str = DB_PATH):
        """初始化数据库管理器。"""
        self.db_path = db_path
        # 不再需要 self.conn 和 self.cursor 实例变量

    async def init_async(self):
        """异步初始化数据库，在事件循环中运行同步的建表逻辑。"""
        log.info("开始异步 Chat 数据库初始化...")
        # 确保 data 目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        await self._execute(self._init_database_logic)
        log.info("异步 Chat 数据库初始化完成。")

    def _init_database_logic(self):
        """包含所有同步数据库初始化逻辑的方法。"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            # --- AI对话上下文表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_conversation_contexts (
                    context_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    conversation_history TEXT NOT NULL DEFAULT '[]',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, guild_id)
                );
            """)

            # 检查并添加 personal_message_count 列到 ai_conversation_contexts
            cursor.execute("PRAGMA table_info(ai_conversation_contexts);")
            columns_contexts = [info[1] for info in cursor.fetchall()]
            if "personal_message_count" not in columns_contexts:
                cursor.execute("""
                    ALTER TABLE ai_conversation_contexts
                    ADD COLUMN personal_message_count INTEGER NOT NULL DEFAULT 0;
                """)
                log.info(
                    "已向 ai_conversation_contexts 表添加 personal_message_count 列。"
                )

            # --- 频道记忆锚点表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_memory_anchors (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    anchor_message_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, channel_id)
                );
            """)

            # --- 游戏状态表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_states (
                    game_id TEXT PRIMARY KEY,
                    player_hand TEXT NOT NULL,
                    ai_hand TEXT NOT NULL,
                    ai_strategy TEXT NOT NULL,
                    current_turn TEXT NOT NULL,
                    game_over BOOLEAN NOT NULL DEFAULT 0,
                    winner TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # --- 21点游戏表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blackjack_games (
                    user_id INTEGER PRIMARY KEY,
                    bet_amount INTEGER NOT NULL,
                    game_state TEXT NOT NULL,
                    deck TEXT,
                    player_hand TEXT,
                    dealer_hand TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # --- 迁移：为 blackjack_games 添加新列 ---
            cursor.execute("PRAGMA table_info(blackjack_games);")
            blackjack_columns = [info[1] for info in cursor.fetchall()]
            if "deck" not in blackjack_columns:
                cursor.execute("ALTER TABLE blackjack_games ADD COLUMN deck TEXT;")
                log.info("已向 blackjack_games 表添加 deck 列。")
            if "player_hand" not in blackjack_columns:
                cursor.execute(
                    "ALTER TABLE blackjack_games ADD COLUMN player_hand TEXT;"
                )
                log.info("已向 blackjack_games 表添加 player_hand 列。")
            if "dealer_hand" not in blackjack_columns:
                cursor.execute(
                    "ALTER TABLE blackjack_games ADD COLUMN dealer_hand TEXT;"
                )
                log.info("已向 blackjack_games 表添加 dealer_hand 列。")

            # --- AI提示词配置表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_prompts (
                    prompt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    prompt_name TEXT NOT NULL,
                    prompt_content TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    UNIQUE(guild_id, prompt_name)
                );
            """)

            # --- 黑名单表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blacklisted_users (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    PRIMARY KEY (user_id, guild_id)
                );
            """)

            # --- 全局黑名单表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS globally_blacklisted_users (
                    user_id INTEGER PRIMARY KEY,
                    expires_at TIMESTAMP NOT NULL
                );
            """)

            # --- 用户警告表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_warnings (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    warning_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                );
            """)

            # --- AI好感度表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_affection (
                    user_id INTEGER PRIMARY KEY NOT NULL,
                    affection_points INTEGER NOT NULL DEFAULT 0,
                    daily_affection_gain INTEGER NOT NULL DEFAULT 0,
                    last_update_date TEXT,
                    last_interaction_date TEXT
                );
            """)

            # 检查并添加 last_gift_date 列到 ai_affection
            cursor.execute("PRAGMA table_info(ai_affection);")
            columns_affection = [info[1] for info in cursor.fetchall()]
            if "last_gift_date" not in columns_affection:
                cursor.execute("""
                    ALTER TABLE ai_affection
                    ADD COLUMN last_gift_date TEXT;
                """)
                log.info("已向 ai_affection 表添加 last_gift_date 列。")

            # --- 投喂日志表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feeding_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL
                );
            """)

            # --- 忏悔日志表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS confession_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL
                );
            """)

            # --- 用户核心档案表 (User Profile) ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    has_personal_memory BOOLEAN NOT NULL DEFAULT 0,
                    personal_summary TEXT
                );
            """)

            # --- 类脑币系统表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_coins (
                    user_id INTEGER PRIMARY KEY,
                    balance INTEGER NOT NULL DEFAULT 0,
                    last_daily_message_date TEXT
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS shop_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    price INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    target TEXT NOT NULL DEFAULT 'self',
                    effect_id TEXT,
                    is_available BOOLEAN NOT NULL DEFAULT 1
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_inventory (
                    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES user_coins(user_id) ON DELETE CASCADE,
                    FOREIGN KEY (item_id) REFERENCES shop_items(item_id) ON DELETE CASCADE
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coin_transactions (
                    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_coins(user_id) ON DELETE CASCADE
                );
            """)

            # --- 新增：类脑币借贷表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS coin_loans (
                    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'paid'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    paid_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_coins(user_id) ON DELETE CASCADE
                );
            """)

            # 检查并向 user_coins 添加列
            cursor.execute("PRAGMA table_info(user_coins);")
            columns_coins = [info[1] for info in cursor.fetchall()]
            if "coffee_effect_expires_at" not in columns_coins:
                cursor.execute("""
                    ALTER TABLE user_coins
                    ADD COLUMN coffee_effect_expires_at TIMESTAMP;
                """)
                log.info("已向 user_coins 表添加 coffee_effect_expires_at 列。")

            if "has_withered_sunflower" not in columns_coins:
                cursor.execute("""
                    ALTER TABLE user_coins
                    ADD COLUMN has_withered_sunflower BOOLEAN DEFAULT NULL;
                """)
                log.info("已向 user_coins 表添加 has_withered_sunflower 列。")

            if "blocks_thread_replies" not in columns_coins:
                cursor.execute("""
                    ALTER TABLE user_coins
                    ADD COLUMN blocks_thread_replies BOOLEAN NOT NULL DEFAULT 0;
                """)
                log.info("已向 user_coins 表添加 blocks_thread_replies 列。")

            if "thread_cooldown_seconds" not in columns_coins:
                cursor.execute(
                    "ALTER TABLE user_coins ADD COLUMN thread_cooldown_seconds INTEGER;"
                )
                log.info("已向 user_coins 表添加 thread_cooldown_seconds 列。")

            if "thread_cooldown_duration" not in columns_coins:
                cursor.execute(
                    "ALTER TABLE user_coins ADD COLUMN thread_cooldown_duration INTEGER;"
                )
                log.info("已向 user_coins 表添加 thread_cooldown_duration 列。")

            if "thread_cooldown_limit" not in columns_coins:
                cursor.execute(
                    "ALTER TABLE user_coins ADD COLUMN thread_cooldown_limit INTEGER;"
                )
                log.info("已向 user_coins 表添加 thread_cooldown_limit 列。")

            # 个人记忆功能的'memory_feature_unlocked'列已迁移至'users'表，此处不再需要
            # 保留此注释以作记录

            # --- 聊天CD与功能开关 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_chat_config (
                    guild_id INTEGER PRIMARY KEY,
                    chat_enabled BOOLEAN NOT NULL DEFAULT 1,
                    warm_up_enabled BOOLEAN NOT NULL DEFAULT 1
                );
            """)

            # --- 暖贴功能频道设置 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS warm_up_channels (
                    guild_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, channel_id)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_chat_config (
                    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    entity_id INTEGER NOT NULL, -- 频道ID或分类ID
                    entity_type TEXT NOT NULL, -- 'channel' or 'category'
                    is_chat_enabled BOOLEAN, -- 可空，为空则继承上级或全局
                    cooldown_seconds INTEGER, -- 可空
                    UNIQUE(guild_id, entity_id)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_channel_cooldown (
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    last_message_timestamp TIMESTAMP NOT NULL,
                    PRIMARY KEY (user_id, channel_id)
                );
            """)

            # --- 新增：频率限制CD的时间戳记录表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_channel_timestamps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                );
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_channel_ts ON user_channel_timestamps (user_id, channel_id, timestamp)"
            )

            # --- 扩展 channel_chat_config 以支持频率限制 ---
            cursor.execute("PRAGMA table_info(channel_chat_config);")
            column_names_config = [info[1] for info in cursor.fetchall()]
            if "cooldown_duration" not in column_names_config:
                cursor.execute(
                    "ALTER TABLE channel_chat_config ADD COLUMN cooldown_duration INTEGER;"
                )
                log.info("已向 channel_chat_config 表添加 cooldown_duration 列。")
            if "cooldown_limit" not in column_names_config:
                cursor.execute(
                    "ALTER TABLE channel_chat_config ADD COLUMN cooldown_limit INTEGER;"
                )
                log.info("已向 channel_chat_config 表添加 cooldown_limit 列。")

            # --- 活动系统表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_faction_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    faction_id TEXT NOT NULL,
                    total_points INTEGER NOT NULL DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(event_id, faction_id)
                );
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_contribution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_id TEXT NOT NULL,
                    faction_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    points_contributed INTEGER NOT NULL,
                    transaction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # --- 全局设置表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS global_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

            # --- 打工游戏状态表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_work_status (
                    user_id INTEGER PRIMARY KEY,
                    last_work_timestamp TIMESTAMP,
                    consecutive_work_days INTEGER NOT NULL DEFAULT 0,
                    last_streak_date TEXT,
                    last_sell_body_timestamp TIMESTAMP
                );
            """)

            # 检查并添加 last_sell_body_timestamp 列
            cursor.execute("PRAGMA table_info(user_work_status);")
            columns_work = [info[1] for info in cursor.fetchall()]
            if "last_sell_body_timestamp" not in columns_work:
                cursor.execute("""
                    ALTER TABLE user_work_status
                    ADD COLUMN last_sell_body_timestamp TIMESTAMP;
                """)
                log.info("已向 user_work_status 表添加 last_sell_body_timestamp 列。")

            if "work_count_today" not in columns_work:
                cursor.execute(
                    "ALTER TABLE user_work_status ADD COLUMN work_count_today INTEGER NOT NULL DEFAULT 0;"
                )
                log.info("已向 user_work_status 表添加 work_count_today 列。")

            if "sell_body_count_today" not in columns_work:
                cursor.execute(
                    "ALTER TABLE user_work_status ADD COLUMN sell_body_count_today INTEGER NOT NULL DEFAULT 0;"
                )
                log.info("已向 user_work_status 表添加 sell_body_count_today 列。")

            if "last_count_date" not in columns_work:
                cursor.execute(
                    "ALTER TABLE user_work_status ADD COLUMN last_count_date TEXT;"
                )
                log.info("已向 user_work_status 表添加 last_count_date 列。")

            if "total_sell_body_count" not in columns_work:
                cursor.execute(
                    "ALTER TABLE user_work_status ADD COLUMN total_sell_body_count INTEGER NOT NULL DEFAULT 0;"
                )
                log.info("已向 user_work_status 表添加 total_sell_body_count 列。")

            # --- 打工/卖屁股事件表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS work_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL, -- 'work' or 'sell_body'
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    reward_range_min INTEGER NOT NULL,
                    reward_range_max INTEGER NOT NULL,
                    good_event_description TEXT,
                    good_event_modifier REAL,
                    bad_event_description TEXT,
                    bad_event_modifier REAL,
                    is_enabled BOOLEAN NOT NULL DEFAULT 1,
                    custom_event_by INTEGER, -- NULL for default events
                    UNIQUE(event_type, name)
                );
            """)

            # --- 频道禁言表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS muted_channels (
                    channel_id INTEGER PRIMARY KEY,
                    muted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    muted_until TIMESTAMP
                );
            """)

            # 检查并添加 muted_until 列到 muted_channels
            cursor.execute("PRAGMA table_info(muted_channels);")
            columns_muted = [info[1] for info in cursor.fetchall()]
            if "muted_until" not in columns_muted:
                cursor.execute("""
                    ALTER TABLE muted_channels
                    ADD COLUMN muted_until TIMESTAMP;
                """)
                log.info("已向 muted_channels 表添加 muted_until 列。")

            # --- AI模型使用计数表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_model_usage (
                    model_name TEXT PRIMARY KEY,
                    usage_count INTEGER NOT NULL DEFAULT 0
                );
            """)

            # --- 每日模型使用计数表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_model_usage (
                    model_name TEXT NOT NULL,
                    usage_date TEXT NOT NULL,
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (model_name, usage_date)
                );
            """)

            # --- 年度总结日志表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS yearly_summary_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # --- 21点每日战绩表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS blackjack_daily_stats (
                    stat_date TEXT PRIMARY KEY,
                    net_win_loss INTEGER NOT NULL DEFAULT 0
                );
            """)

            # --- 每日综合统计表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    stat_date TEXT PRIMARY KEY,
                    issue_user_warning_count INTEGER NOT NULL DEFAULT 0,
                    confession_count INTEGER NOT NULL DEFAULT 0,
                    feeding_count INTEGER NOT NULL DEFAULT 0,
                    tarot_reading_count INTEGER NOT NULL DEFAULT 0,
                    forum_search_count INTEGER NOT NULL DEFAULT 0
                );
            """)

            # --- 每日拉黑工具统计表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_issue_user_warning_stats (
                    stat_date TEXT PRIMARY KEY,
                    issue_user_warning_count INTEGER NOT NULL DEFAULT 0
                );
            """)

            conn.commit()
            log.info(f"数据库表在 {self.db_path} 同步初始化成功。")
        except sqlite3.Error as e:
            log.error(f"同步初始化数据库表时出错: {e}")
            if conn:
                conn.rollback()  # 如果初始化失败则回滚
            raise
        finally:
            if conn:
                conn.close()

    async def _execute(self, func: Callable, *args, **kwargs) -> Any:
        """在线程池中执行一个同步的数据库操作。"""
        try:
            blocking_task = partial(func, *args, **kwargs)
            result = await asyncio.get_running_loop().run_in_executor(
                None, blocking_task
            )
            return result
        except Exception as e:
            log.error(f"数据库执行器出错: {e}", exc_info=True)
            raise

    def _db_transaction(
        self,
        query: str,
        params: tuple = (),
        *,
        fetch: str = "none",
        commit: bool = False,
    ):
        """
        一个完全线程安全的同步事务函数。
        它为每个操作创建一个新的数据库连接，以确保完全隔离。
        """
        conn = None
        try:
            # 为此操作创建一个新的、独立的连接
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(query, params)

            if fetch == "one":
                result = cursor.fetchone()
            elif fetch == "all":
                result = cursor.fetchall()
            elif fetch == "lastrowid":
                result = cursor.lastrowid
            elif fetch == "rowcount":
                result = cursor.rowcount
            else:
                result = None

            if commit:
                conn.commit()

            return result
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            log.error(f"数据库事务失败，已回滚: {e} | Query: {query}")
            raise
        finally:
            if conn:
                conn.close()

    async def disconnect(self):
        """关闭数据库连接（在新模式下无需操作）。"""
        log.info("数据库管理器现在是无状态的，无需显式断开连接。")
        pass

    # --- AI对话上下文管理 ---
    async def get_ai_conversation_context(
        self, user_id: int, guild_id: int
    ) -> Optional[Dict[str, Any]]:
        query = (
            "SELECT * FROM ai_conversation_contexts WHERE user_id = ? AND guild_id = ?"
        )
        row = await self._execute(
            self._db_transaction, query, (user_id, guild_id), fetch="one"
        )
        if row:
            try:
                context = dict(row)
                context["conversation_history"] = json.loads(
                    context["conversation_history"]
                )
                return context
            except (json.JSONDecodeError, TypeError):
                log.warning(f"解析用户 {user_id} 的对话上下文JSON时出错。")
        return None

    async def update_ai_conversation_context(
        self, user_id: int, guild_id: int, conversation_history: List[Dict]
    ) -> None:
        history_json = json.dumps(conversation_history, ensure_ascii=False)
        query = """
            INSERT INTO ai_conversation_contexts (user_id, guild_id, conversation_history)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                conversation_history = excluded.conversation_history,
                last_updated = CURRENT_TIMESTAMP
        """
        await self._execute(
            self._db_transaction, query, (user_id, guild_id, history_json), commit=True
        )

    async def clear_ai_conversation_context(self, user_id: int, guild_id: int) -> None:
        query = (
            "DELETE FROM ai_conversation_contexts WHERE user_id = ? AND guild_id = ?"
        )
        await self._execute(
            self._db_transaction, query, (user_id, guild_id), commit=True
        )
        log.info(f"已清除用户 {user_id} 在服务器 {guild_id} 的AI对话上下文")

    async def increment_personal_message_count(
        self, user_id: int, guild_id: int
    ) -> int:
        """增加用户的个人消息计数器，并返回新的计数值。"""
        query = """
            INSERT INTO ai_conversation_contexts (user_id, guild_id, personal_message_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                personal_message_count = personal_message_count + 1
            RETURNING personal_message_count;
        """
        result = await self._execute(
            self._db_transaction, query, (user_id, guild_id), fetch="one", commit=True
        )
        return result["personal_message_count"] if result else 0

    async def reset_personal_message_count(self, user_id: int, guild_id: int) -> None:
        """重置用户的个人消息计数器。"""
        query = """
            UPDATE ai_conversation_contexts
            SET personal_message_count = 0
            WHERE user_id = ? AND guild_id = ?
        """
        await self._execute(
            self._db_transaction, query, (user_id, guild_id), commit=True
        )

    # --- 频道记忆锚点管理 ---
    async def get_channel_memory_anchor(
        self, guild_id: int, channel_id: int
    ) -> Optional[int]:
        query = "SELECT anchor_message_id FROM channel_memory_anchors WHERE guild_id = ? AND channel_id = ?"
        row = await self._execute(
            self._db_transaction, query, (guild_id, channel_id), fetch="one"
        )
        return row["anchor_message_id"] if row else None

    async def set_channel_memory_anchor(
        self, guild_id: int, channel_id: int, anchor_message_id: int
    ) -> None:
        query = """
            INSERT INTO channel_memory_anchors (guild_id, channel_id, anchor_message_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, channel_id) DO UPDATE SET
                anchor_message_id = excluded.anchor_message_id;
        """
        await self._execute(
            self._db_transaction,
            query,
            (guild_id, channel_id, anchor_message_id),
            commit=True,
        )
        log.info(
            f"已为服务器 {guild_id} 的频道 {channel_id} 设置记忆锚点: {anchor_message_id}"
        )

    async def delete_channel_memory_anchor(self, guild_id: int, channel_id: int) -> int:
        query = (
            "DELETE FROM channel_memory_anchors WHERE guild_id = ? AND channel_id = ?"
        )
        deleted_rows = await self._execute(
            self._db_transaction,
            query,
            (guild_id, channel_id),
            commit=True,
            fetch="rowcount",
        )
        if deleted_rows > 0:
            log.info(f"已删除服务器 {guild_id} 频道 {channel_id} 的记忆锚点。")
        return deleted_rows

    # --- AI提示词管理 ---
    async def get_ai_prompt(self, guild_id: int, prompt_name: str) -> Optional[str]:
        query = "SELECT prompt_content FROM ai_prompts WHERE guild_id = ? AND prompt_name = ? AND is_active = 1"
        row = await self._execute(
            self._db_transaction, query, (guild_id, prompt_name), fetch="one"
        )
        return row["prompt_content"] if row else None

    async def set_ai_prompt(
        self, guild_id: int, prompt_name: str, prompt_content: str
    ) -> None:
        query = """
            INSERT INTO ai_prompts (guild_id, prompt_name, prompt_content)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, prompt_name) DO UPDATE SET
                prompt_content = excluded.prompt_content,
                is_active = 1
        """
        await self._execute(
            self._db_transaction,
            query,
            (guild_id, prompt_name, prompt_content),
            commit=True,
        )
        log.info(f"已为服务器 {guild_id} 设置AI提示词: {prompt_name}")

    async def get_all_ai_prompts(self, guild_id: int) -> Dict[str, str]:
        query = "SELECT prompt_name, prompt_content FROM ai_prompts WHERE guild_id = ? AND is_active = 1"
        rows = await self._execute(
            self._db_transaction, query, (guild_id,), fetch="all"
        )
        return {row["prompt_name"]: row["prompt_content"] for row in rows}

    # --- 黑名单管理 ---
    async def add_to_blacklist(self, user_id: int, guild_id: int, expires_at) -> None:
        query = """
            INSERT INTO blacklisted_users (user_id, guild_id, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                expires_at = excluded.expires_at;
        """
        await self._execute(
            self._db_transaction, query, (user_id, guild_id, expires_at), commit=True
        )
        log.info(
            f"已将用户 {user_id} 添加到服务器 {guild_id} 的黑名单，到期时间: {expires_at}"
        )

    async def remove_from_blacklist(self, user_id: int, guild_id: int) -> None:
        query = "DELETE FROM blacklisted_users WHERE user_id = ? AND guild_id = ?"
        await self._execute(
            self._db_transaction, query, (user_id, guild_id), commit=True
        )
        log.info(f"已将用户 {user_id} 从服务器 {guild_id} 的黑名单中移除")

    async def is_user_blacklisted(self, user_id: int, guild_id: int) -> bool:
        # 清理过期黑名单记录
        await self._execute(
            self._db_transaction,
            "DELETE FROM blacklisted_users WHERE expires_at < datetime('now')",
            commit=True,
        )

        # 检查用户是否在黑名单中
        query = "SELECT expires_at FROM blacklisted_users WHERE user_id = ? AND guild_id = ?"
        result = await self._execute(
            self._db_transaction, query, (user_id, guild_id), fetch="one"
        )

        if result:
            db_expires_at_str = result["expires_at"]
            # 将数据库中的时间字符串转换为 datetime 对象，并假设它是 UTC
            db_expires_at = datetime.fromisoformat(db_expires_at_str).replace(
                tzinfo=timezone.utc
            )
            current_utc_time = datetime.now(timezone.utc)

            log.info(f"检查用户 {user_id} 在服务器 {guild_id} 的黑名单状态:")
            log.info(f"  数据库过期时间 (UTC): {db_expires_at}")
            log.info(f"  当前 UTC 时间: {current_utc_time}")

            if db_expires_at > current_utc_time:
                log.info(f"  用户 {user_id} 仍在黑名单中。")
                return True
            else:
                log.info(
                    f"  用户 {user_id} 的黑名单已过期，但未被清理 (应在下次检查时清理)。"
                )
                return False

        log.info(f"用户 {user_id} 不在服务器 {guild_id} 的黑名单中。")
        return False

    # --- 全局黑名单管理 ---
    async def add_to_global_blacklist(self, user_id: int, expires_at: datetime) -> None:
        """将用户添加到全局黑名单。"""
        query = """
            INSERT INTO globally_blacklisted_users (user_id, expires_at)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                expires_at = excluded.expires_at;
        """
        await self._execute(
            self._db_transaction, query, (user_id, expires_at), commit=True
        )
        log.info(f"已将用户 {user_id} 添加到全局黑名单，到期时间: {expires_at}")

    async def remove_from_global_blacklist(self, user_id: int) -> None:
        """将用户从全局黑名单中移除。"""
        query = "DELETE FROM globally_blacklisted_users WHERE user_id = ?"
        await self._execute(self._db_transaction, query, (user_id,), commit=True)
        log.info(f"已将用户 {user_id} 从全局黑名单中移除")

    async def is_user_globally_blacklisted(self, user_id: int) -> bool:
        """检查用户是否在全局黑名单中。"""
        await self._execute(
            self._db_transaction,
            "DELETE FROM globally_blacklisted_users WHERE expires_at < datetime('now', 'utc')",
            commit=True,
        )

        query = "SELECT expires_at FROM globally_blacklisted_users WHERE user_id = ?"
        result = await self._execute(
            self._db_transaction, query, (user_id,), fetch="one"
        )

        if result:
            try:
                db_expires_at = datetime.fromisoformat(result["expires_at"]).replace(
                    tzinfo=timezone.utc
                )
            except (ValueError, TypeError):
                # 兼容旧格式或None值
                db_expires_at = datetime.strptime(
                    result["expires_at"], "%Y-%m-%d %H:%M:%S.%f"
                ).replace(tzinfo=timezone.utc)

            if db_expires_at > datetime.now(timezone.utc):
                log.info(f"用户 {user_id} 仍在全局黑名单中。")
                return True

        return False

    # --- 警告管理 ---
    async def record_warning_and_check_blacklist(
        self, user_id: int, guild_id: int, expires_at
    ) -> Dict[str, Any]:
        """
        记录一次用户警告。如果警告达到3次，则将用户加入黑名单并重置警告计数。
        返回一个字典，包含是否被拉黑以及更新后的警告次数。
        """
        # 增加警告计数
        query_update = """
            INSERT INTO user_warnings (user_id, guild_id, warning_count)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET
                warning_count = warning_count + 1
            RETURNING warning_count;
        """
        result = await self._execute(
            self._db_transaction,
            query_update,
            (user_id, guild_id),
            fetch="one",
            commit=True,
        )
        current_warnings = result["warning_count"] if result else 0

        log.info(
            f"用户 {user_id} 在服务器 {guild_id} 的警告次数更新为: {current_warnings}"
        )

        # 检查是否达到拉黑阈值
        if current_warnings >= 1:
            log.info(
                f"用户 {user_id} 在服务器 {guild_id} 达到3次警告，将被加入黑名单。"
            )
            # --- 扣除好感度 ---
            penalty = chat_config.AFFECTION_CONFIG["BLACKLIST_PENALTY"]
            if penalty != 0:
                query_affection = """
                    INSERT INTO ai_affection (user_id, affection_points)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        affection_points = affection_points + excluded.affection_points;
                """
                await self._execute(
                    self._db_transaction,
                    query_affection,
                    (user_id, penalty),
                    commit=True,
                )
                log.info(f"用户 {user_id} 因被禁言被扣除好感度: {penalty}")

            # 加入黑名单
            await self.add_to_blacklist(user_id, guild_id, expires_at)

            # 重置警告计数
            query_reset = "UPDATE user_warnings SET warning_count = 0 WHERE user_id = ? AND guild_id = ?"
            await self._execute(
                self._db_transaction, query_reset, (user_id, guild_id), commit=True
            )
            log.info(f"已重置用户 {user_id} 在服务器 {guild_id} 的警告计数。")
            return {"was_blacklisted": True, "new_warning_count": 0}

        return {"was_blacklisted": False, "new_warning_count": current_warnings}

    # --- 好感度管理 ---
    async def get_affection(self, user_id: int) -> Optional[sqlite3.Row]:
        query = "SELECT * FROM ai_affection WHERE user_id = ?"
        return await self._execute(self._db_transaction, query, (user_id,), fetch="one")

    async def update_affection(self, user_id: int, **kwargs) -> None:
        updates = {key: value for key, value in kwargs.items() if value is not None}
        if not updates:
            return

        current_affection = await self.get_affection(user_id)
        if not current_affection:
            defaults = {
                "affection_points": 0,
                "daily_affection_gain": 0,
                "last_update_date": None,
                "last_interaction_date": None,
            }
            defaults.update(updates)
            insert_query = """
                INSERT INTO ai_affection (user_id, affection_points, daily_affection_gain, last_update_date, last_interaction_date)
                VALUES (?, ?, ?, ?, ?)
            """
            await self._execute(
                self._db_transaction,
                insert_query,
                (
                    user_id,
                    defaults["affection_points"],
                    defaults["daily_affection_gain"],
                    defaults["last_update_date"],
                    defaults["last_interaction_date"],
                ),
                commit=True,
            )
            log.info(f"为用户 {user_id} 创建了好感度记录: {defaults}")
            return

        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [user_id]
        query = f"UPDATE ai_affection SET {set_clause} WHERE user_id = ?"
        await self._execute(self._db_transaction, query, tuple(values), commit=True)

    async def get_all_affections(self) -> List[sqlite3.Row]:
        query = "SELECT * FROM ai_affection"
        return await self._execute(self._db_transaction, query, fetch="all")

    async def reset_daily_affection_gain(self, new_date: str) -> None:
        query = "UPDATE ai_affection SET daily_affection_gain = 0, last_update_date = ?"
        await self._execute(self._db_transaction, query, (new_date,), commit=True)
        log.info(f"已重置所有用户的每日好感度获得量，日期更新为 {new_date}")

    async def reset_all_affection_points(self) -> int:
        query = "UPDATE ai_affection SET affection_points = 0"
        rowcount = await self._execute(
            self._db_transaction, query, commit=True, fetch="rowcount"
        )
        log.info(f"已将 {rowcount} 名用户的好感度重置为 0。")
        return rowcount

    # --- 用户档案管理 ---
    async def get_user_profile(self, user_id: int) -> Optional[sqlite3.Row]:
        """获取用户的核心档案信息，例如是否解锁了个人记忆功能。"""
        query = "SELECT user_id, has_personal_memory, personal_summary FROM users WHERE user_id = ?"
        try:
            return await self._execute(
                self._db_transaction, query, (user_id,), fetch="one"
            )
        except sqlite3.OperationalError as e:
            # 如果 users 表或列不存在，优雅地处理
            if "no such table" in str(e) or "no such column" in str(e):
                log.warning(
                    f"尝试获取用户 {user_id} 的档案失败，因为 'users' 表或相关列不存在。请确保已运行最新的数据库迁移脚本。"
                )
                return None
            raise

    async def update_personal_summary(self, user_id: int, summary: str) -> None:
        """更新或创建用户的个人记忆摘要 (Upsert)。"""
        query = """
            INSERT INTO users (user_id, personal_summary)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                personal_summary = excluded.personal_summary;
        """
        try:
            await self._execute(
                self._db_transaction, query, (user_id, summary), commit=True
            )
            log.info(f"已为用户 {user_id} 更新或创建了个人记忆摘要。")
        except sqlite3.OperationalError as e:
            log.error(f"为用户 {user_id} 更新或创建个人记忆摘要失败: {e}")
            raise

    # --- 聊天设置管理 ---

    async def get_global_setting(self, key: str) -> Optional[str]:
        """获取一个全局设置的值。"""
        query = "SELECT value FROM global_settings WHERE key = ?"
        row = await self._execute(self._db_transaction, query, (key,), fetch="one")
        return row["value"] if row else None

    async def set_global_setting(self, key: str, value: str) -> None:
        """设置一个全局设置的值。"""
        query = """
            INSERT INTO global_settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value;
        """
        await self._execute(self._db_transaction, query, (key, value), commit=True)
        log.info(f"已更新全局设置: {key} = {value}")

    async def get_global_chat_config(self, guild_id: int) -> Optional[sqlite3.Row]:
        """获取服务器的全局聊天配置。"""
        query = "SELECT * FROM global_chat_config WHERE guild_id = ?"
        return await self._execute(
            self._db_transaction, query, (guild_id,), fetch="one"
        )

    async def update_global_chat_config(
        self,
        guild_id: int,
        chat_enabled: Optional[bool] = None,
        warm_up_enabled: Optional[bool] = None,
    ) -> None:
        """更新或创建服务器的全局聊天配置。"""
        updates = {}
        if chat_enabled is not None:
            updates["chat_enabled"] = chat_enabled
        if warm_up_enabled is not None:
            updates["warm_up_enabled"] = warm_up_enabled

        if not updates:
            return

        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        params = list(updates.values())

        query = f"""
            INSERT INTO global_chat_config (guild_id, {", ".join(updates.keys())})
            VALUES (?, {", ".join(["?"] * len(params))})
            ON CONFLICT(guild_id) DO UPDATE SET
            {set_clause};
        """
        await self._execute(
            self._db_transaction, query, (guild_id, *params, *params), commit=True
        )
        await self._execute(
            self._db_transaction, query, (guild_id, *params, *params), commit=True
        )
        log.info(f"已更新服务器 {guild_id} 的全局聊天配置: {updates}")

    async def get_channel_config(
        self, guild_id: int, entity_id: int
    ) -> Optional[sqlite3.Row]:
        """获取特定频道或分类的聊天配置。"""
        query = "SELECT * FROM channel_chat_config WHERE guild_id = ? AND entity_id = ?"
        return await self._execute(
            self._db_transaction, query, (guild_id, entity_id), fetch="one"
        )

    async def get_all_channel_configs_for_guild(
        self, guild_id: int
    ) -> List[sqlite3.Row]:
        """获取服务器内所有特定频道/分类的配置。"""
        query = "SELECT * FROM channel_chat_config WHERE guild_id = ?"
        return await self._execute(
            self._db_transaction, query, (guild_id,), fetch="all"
        )

    async def update_channel_config(
        self,
        guild_id: int,
        entity_id: int,
        entity_type: str,
        is_chat_enabled: Optional[bool],
        cooldown_seconds: Optional[int],
        cooldown_duration: Optional[int],
        cooldown_limit: Optional[int],
    ) -> None:
        """更新或创建频道/分类的聊天配置，支持两种CD模式。"""
        query = """
            INSERT INTO channel_chat_config (guild_id, entity_id, entity_type, is_chat_enabled, cooldown_seconds, cooldown_duration, cooldown_limit)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, entity_id) DO UPDATE SET
                entity_type = excluded.entity_type,
                is_chat_enabled = excluded.is_chat_enabled,
                cooldown_seconds = excluded.cooldown_seconds,
                cooldown_duration = excluded.cooldown_duration,
                cooldown_limit = excluded.cooldown_limit;
        """
        params = (
            guild_id,
            entity_id,
            entity_type,
            is_chat_enabled,
            cooldown_seconds,
            cooldown_duration,
            cooldown_limit,
        )
        await self._execute(self._db_transaction, query, params, commit=True)
        log.info(
            f"已更新服务器 {guild_id} 的实体 {entity_id} ({entity_type}) 的聊天配置。"
        )

    async def get_user_cooldown(
        self, user_id: int, channel_id: int
    ) -> Optional[sqlite3.Row]:
        """获取用户的最后消息时间戳。"""
        query = "SELECT last_message_timestamp FROM user_channel_cooldown WHERE user_id = ? AND channel_id = ?"
        return await self._execute(
            self._db_transaction, query, (user_id, channel_id), fetch="one"
        )

    async def update_user_cooldown(self, user_id: int, channel_id: int) -> None:
        """更新用户的最后消息时间戳。"""
        query = """
            INSERT INTO user_channel_cooldown (user_id, channel_id, last_message_timestamp)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, channel_id) DO UPDATE SET
                last_message_timestamp = CURRENT_TIMESTAMP;
        """
        await self._execute(
            self._db_transaction, query, (user_id, channel_id), commit=True
        )

    async def add_user_timestamp(self, user_id: int, channel_id: int) -> None:
        """为频率限制系统记录一条新的消息时间戳。"""
        query = "INSERT INTO user_channel_timestamps (user_id, channel_id, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)"
        await self._execute(
            self._db_transaction, query, (user_id, channel_id), commit=True
        )

    async def get_user_timestamps_in_window(
        self, user_id: int, channel_id: int, window_seconds: int
    ) -> List[sqlite3.Row]:
        """获取用户在指定时间窗口内的所有消息时间戳。"""
        query = """
            SELECT timestamp FROM user_channel_timestamps
            WHERE user_id = ? AND channel_id = ? AND timestamp >= datetime('now', ?)
        """
        time_modifier = f"-{window_seconds} seconds"
        return await self._execute(
            self._db_transaction,
            query,
            (user_id, channel_id, time_modifier),
            fetch="all",
        )

    async def update_user_thread_cooldown_settings(
        self, user_id: int, settings: Dict[str, Any]
    ) -> None:
        """更新用户的个人帖子默认冷却设置。"""
        # 确保用户记录存在
        await self._execute(
            self._db_transaction,
            "INSERT OR IGNORE INTO user_coins (user_id) VALUES (?)",
            (user_id,),
            commit=True,
        )

        query = """
            UPDATE user_coins
            SET
                thread_cooldown_seconds = ?,
                thread_cooldown_duration = ?,
                thread_cooldown_limit = ?
            WHERE user_id = ?
        """
        params = (
            settings.get("cooldown_seconds"),
            settings.get("cooldown_duration"),
            settings.get("cooldown_limit"),
            user_id,
        )
        await self._execute(self._db_transaction, query, params, commit=True)
        log.info(f"已更新用户 {user_id} 的个人帖子冷却设置: {settings}")

    # --- 暖贴频道管理 ---
    async def get_warm_up_channels(self, guild_id: int) -> List[int]:
        """获取服务器的所有暖贴频道ID。"""
        query = "SELECT channel_id FROM warm_up_channels WHERE guild_id = ?"
        rows = await self._execute(
            self._db_transaction, query, (guild_id,), fetch="all"
        )
        return [row["channel_id"] for row in rows]

    async def add_warm_up_channel(self, guild_id: int, channel_id: int) -> None:
        """添加一个暖贴频道。"""
        query = "INSERT OR IGNORE INTO warm_up_channels (guild_id, channel_id) VALUES (?, ?)"
        await self._execute(
            self._db_transaction, query, (guild_id, channel_id), commit=True
        )
        log.info(f"已为服务器 {guild_id} 添加暖贴频道 {channel_id}。")

    async def remove_warm_up_channel(self, guild_id: int, channel_id: int) -> None:
        """移除一个暖贴频道。"""
        query = "DELETE FROM warm_up_channels WHERE guild_id = ? AND channel_id = ?"
        await self._execute(
            self._db_transaction, query, (guild_id, channel_id), commit=True
        )
        log.info(f"已为服务器 {guild_id} 移除暖贴频道 {channel_id}。")

    async def is_warm_up_channel(self, guild_id: int, channel_id: int) -> bool:
        """检查一个频道是否是暖贴频道。"""
        query = "SELECT 1 FROM warm_up_channels WHERE guild_id = ? AND channel_id = ?"
        row = await self._execute(
            self._db_transaction, query, (guild_id, channel_id), fetch="one"
        )
        return row is not None

    # --- 打工游戏状态管理 ---
    async def get_user_work_status(self, user_id: int) -> Optional[sqlite3.Row]:
        """获取用户的打工状态。"""
        query = "SELECT * FROM user_work_status WHERE user_id = ?"
        return await self._execute(self._db_transaction, query, (user_id,), fetch="one")

    async def update_user_work_status(
        self,
        user_id: int,
        last_work_timestamp: datetime,
        consecutive_work_days: int,
        last_streak_date: str,
    ) -> None:
        """更新或创建用户的打工状态。"""
        query = """
            INSERT INTO user_work_status (user_id, last_work_timestamp, consecutive_work_days, last_streak_date)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_work_timestamp = excluded.last_work_timestamp,
                consecutive_work_days = excluded.consecutive_work_days,
                last_streak_date = excluded.last_streak_date;
        """
        params = (
            user_id,
            last_work_timestamp,
            consecutive_work_days,
            last_streak_date,
        )
        await self._execute(self._db_transaction, query, params, commit=True)

    async def update_user_sell_body_timestamp(
        self, user_id: int, timestamp: datetime
    ) -> None:
        """更新用户的卖屁股时间戳。"""
        query = """
            INSERT INTO user_work_status (user_id, last_sell_body_timestamp)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_sell_body_timestamp = excluded.last_sell_body_timestamp;
        """
        await self._execute(
            self._db_transaction, query, (user_id, timestamp), commit=True
        )

    # --- 打工/卖屁股事件管理 ---
    async def add_work_event(self, event_data: Dict[str, Any]) -> int:
        """向 work_events 表中添加一个新的事件。"""
        query = """
            INSERT INTO work_events (
                event_type, name, description, reward_range_min, reward_range_max,
                good_event_description, good_event_modifier,
                bad_event_description, bad_event_modifier,
                is_enabled, custom_event_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_type, name) DO UPDATE SET
                description = excluded.description,
                reward_range_min = excluded.reward_range_min,
                reward_range_max = excluded.reward_range_max,
                good_event_description = excluded.good_event_description,
                good_event_modifier = excluded.good_event_modifier,
                bad_event_description = excluded.bad_event_description,
                bad_event_modifier = excluded.bad_event_modifier,
                is_enabled = excluded.is_enabled,
                custom_event_by = excluded.custom_event_by;
        """
        params = (
            event_data["event_type"],
            event_data["name"],
            event_data["description"],
            event_data["reward_range_min"],
            event_data["reward_range_max"],
            event_data.get("good_event_description"),
            event_data.get("good_event_modifier"),
            event_data.get("bad_event_description"),
            event_data.get("bad_event_modifier"),
            event_data.get("is_enabled", 1),
            event_data.get("custom_event_by"),
        )
        return await self._execute(
            self._db_transaction, query, params, commit=True, fetch="lastrowid"
        )

    async def get_work_events(
        self, event_type: str, include_disabled: bool = False
    ) -> List[sqlite3.Row]:
        """根据类型获取所有启用的工作/卖屁股事件。"""
        query = "SELECT * FROM work_events WHERE event_type = ?"
        if not include_disabled:
            query += " AND is_enabled = 1"
        return await self._execute(
            self._db_transaction, query, (event_type,), fetch="all"
        )

    # --- 频道禁言管理 ---
    async def add_muted_channel(self, channel_id: int, duration_minutes: int):
        """将一个频道添加到禁言列表，并设置禁言持续时间。"""
        muted_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
        query = "INSERT OR REPLACE INTO muted_channels (channel_id, muted_until) VALUES (?, ?)"
        await self._execute(
            self._db_transaction, query, (channel_id, muted_until), commit=True
        )
        log.info(
            f"已将频道 {channel_id} 添加到禁言列表，解禁时间: {muted_until.isoformat()}"
        )

    async def remove_muted_channel(self, channel_id: int) -> None:
        """将一个频道从禁言列表中移除。"""
        query = "DELETE FROM muted_channels WHERE channel_id = ?"
        await self._execute(self._db_transaction, query, (channel_id,), commit=True)
        log.info(f"已将频道 {channel_id} 从禁言列表中移除。")

    async def is_channel_muted(self, channel_id: int) -> bool:
        """
        检查一个频道当前是否被禁言。
        如果禁言已过期，则会自动从数据库中移除该记录。
        """
        query = "SELECT muted_until FROM muted_channels WHERE channel_id = ?"
        row = await self._execute(
            self._db_transaction, query, (channel_id,), fetch="one"
        )

        if row:
            muted_until_str = row["muted_until"]
            if not muted_until_str:
                # 兼容旧数据，如果没有设置过期时间，则视为未禁言
                return False

            try:
                # 尝试解析带时区信息的时间字符串
                muted_until = datetime.fromisoformat(muted_until_str)
            except ValueError:
                # 兼容可能不带时区信息的旧格式
                muted_until = datetime.strptime(
                    muted_until_str, "%Y-%m-%d %H:%M:%S.%f"
                ).replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) > muted_until:
                # 禁言已过期，移除记录并返回 False
                await self.remove_muted_channel(channel_id)
                log.info(f"频道 {channel_id} 的禁言已到期，已自动解除。")
                return False
            else:
                # 仍在禁言期
                return True
        # 不在禁言列表
        return False

    # --- AI模型使用计数 ---
    async def increment_model_usage(self, model_name: str) -> None:
        """为一个模型增加累计和每日使用次数。"""
        # 增加总数
        query_total = """
            INSERT INTO ai_model_usage (model_name, usage_count)
            VALUES (?, 1)
            ON CONFLICT(model_name) DO UPDATE SET
                usage_count = usage_count + 1;
        """
        await self._execute(
            self._db_transaction, query_total, (model_name,), commit=True
        )

        # 增加当日计数
        today_date_str = get_beijing_today_str()
        query_daily = """
            INSERT INTO daily_model_usage (model_name, usage_date, usage_count)
            VALUES (?, ?, 1)
            ON CONFLICT(model_name, usage_date) DO UPDATE SET
                usage_count = usage_count + 1;
        """
        await self._execute(
            self._db_transaction, query_daily, (model_name, today_date_str), commit=True
        )

    async def get_model_usage_counts(self) -> List[sqlite3.Row]:
        """获取所有模型累计的使用次数。"""
        query = "SELECT model_name, usage_count FROM ai_model_usage"
        return await self._execute(self._db_transaction, query, fetch="all")

    async def get_model_usage_counts_today(self) -> List[sqlite3.Row]:
        """获取今天所有模型的使用次数。"""
        today_date_str = get_beijing_today_str()
        query = (
            "SELECT model_name, usage_count FROM daily_model_usage WHERE usage_date = ?"
        )
        return await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="all"
        )

    async def get_total_work_count_today(self) -> int:
        """获取今天所有用户的总打工次数。"""
        today_date_str = get_beijing_today_str()
        query = "SELECT SUM(work_count_today) as total FROM user_work_status WHERE last_count_date = ?"
        result = await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="one"
        )
        return result["total"] if result and result["total"] is not None else 0

    async def get_total_sell_body_count_today(self) -> int:
        """获取今天所有用户的总卖屁股次数。"""
        today_date_str = get_beijing_today_str()
        query = "SELECT SUM(sell_body_count_today) as total FROM user_work_status WHERE last_count_date = ?"
        result = await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="one"
        )
        return result["total"] if result and result["total"] is not None else 0

    async def update_blackjack_net_win_loss(self, amount: int) -> None:
        """更新今天的21点游戏净输赢。"""
        today_date_str = get_beijing_today_str()
        query = """
            INSERT INTO blackjack_daily_stats (stat_date, net_win_loss)
            VALUES (?, ?)
            ON CONFLICT(stat_date) DO UPDATE SET
                net_win_loss = net_win_loss + excluded.net_win_loss;
        """
        await self._execute(
            self._db_transaction, query, (today_date_str, amount), commit=True
        )

    async def get_blackjack_net_win_loss_today(self) -> int:
        """获取今天的21点游戏净输赢。"""
        today_date_str = get_beijing_today_str()
        query = "SELECT net_win_loss FROM blackjack_daily_stats WHERE stat_date = ?"
        result = await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="one"
        )
        return result["net_win_loss"] if result else 0

    async def increment_confession_count(self) -> None:
        """增加今天的忏悔次数。"""
        today_date_str = get_beijing_today_str()
        query = """
            INSERT INTO daily_stats (stat_date, confession_count)
            VALUES (?, 1)
            ON CONFLICT(stat_date) DO UPDATE SET
                confession_count = confession_count + 1;
        """
        await self._execute(self._db_transaction, query, (today_date_str,), commit=True)

    async def get_confession_count_today(self) -> int:
        """获取今天的忏悔次数。"""
        today_date_str = get_beijing_today_str()
        query = "SELECT confession_count FROM daily_stats WHERE stat_date = ?"
        result = await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="one"
        )
        return result["confession_count"] if result else 0

    async def increment_feeding_count(self) -> None:
        """增加今天的投喂次数。"""
        today_date_str = get_beijing_today_str()
        query = """
            INSERT INTO daily_stats (stat_date, feeding_count)
            VALUES (?, 1)
            ON CONFLICT(stat_date) DO UPDATE SET
                feeding_count = feeding_count + 1;
        """
        await self._execute(self._db_transaction, query, (today_date_str,), commit=True)

    async def get_feeding_count_today(self) -> int:
        """获取今天的投喂次数。"""
        today_date_str = get_beijing_today_str()
        query = "SELECT feeding_count FROM daily_stats WHERE stat_date = ?"
        result = await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="one"
        )
        return result["feeding_count"] if result else 0

    async def increment_tarot_reading_count(self) -> None:
        """增加今天的塔罗牌占卜次数。"""
        today_date_str = get_beijing_today_str()
        query = """
            INSERT INTO daily_stats (stat_date, tarot_reading_count)
            VALUES (?, 1)
            ON CONFLICT(stat_date) DO UPDATE SET
                tarot_reading_count = tarot_reading_count + 1;
        """
        await self._execute(self._db_transaction, query, (today_date_str,), commit=True)

    async def get_tarot_reading_count_today(self) -> int:
        """获取今天的塔罗牌占卜次数。"""
        today_date_str = get_beijing_today_str()
        query = "SELECT tarot_reading_count FROM daily_stats WHERE stat_date = ?"
        result = await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="one"
        )
        return result["tarot_reading_count"] if result else 0

    async def increment_forum_search_count(self) -> None:
        """增加今天的论坛搜索次数。"""
        today_date_str = get_beijing_today_str()
        query = """
            INSERT INTO daily_stats (stat_date, forum_search_count)
            VALUES (?, 1)
            ON CONFLICT(stat_date) DO UPDATE SET
                forum_search_count = forum_search_count + 1;
        """
        await self._execute(self._db_transaction, query, (today_date_str,), commit=True)

    async def get_forum_search_count_today(self) -> int:
        """获取今天的论坛搜索次数。"""
        today_date_str = get_beijing_today_str()
        query = "SELECT forum_search_count FROM daily_stats WHERE stat_date = ?"
        result = await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="one"
        )
        return result["forum_search_count"] if result else 0

    async def increment_issue_user_warning_count(self) -> None:
        """增加今天的 'issue_user_warning' 工具使用次数。"""
        today_date_str = get_beijing_today_str()
        query = """
            INSERT INTO daily_issue_user_warning_stats (stat_date, issue_user_warning_count)
            VALUES (?, 1)
            ON CONFLICT(stat_date) DO UPDATE SET
                issue_user_warning_count = issue_user_warning_count + 1;
        """
        await self._execute(self._db_transaction, query, (today_date_str,), commit=True)

    async def get_issue_user_warning_count_today(self) -> int:
        """获取今天的 'issue_user_warning' 工具使用次数。"""
        today_date_str = get_beijing_today_str()
        query = "SELECT issue_user_warning_count FROM daily_issue_user_warning_stats WHERE stat_date = ?"
        result = await self._execute(
            self._db_transaction, query, (today_date_str,), fetch="one"
        )
        return result["issue_user_warning_count"] if result else 0


# --- 单例实例 ---
chat_db_manager = ChatDatabaseManager()
