# -*- coding: utf-8 -*-
"""照片墙独立 SQLite 访问层。

刻意不复用 chat_db_manager（那是其他并行任务的地盘），
这里仿照其 "_db_transaction + 线程池" 模式实现一个轻量版本，
使用独立数据库文件 data/photo_wall.db，互不干扰。
"""

import asyncio
import logging
import sqlite3
from functools import partial
from pathlib import Path
from typing import Any, List, Optional

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS photo_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    display_name TEXT NOT NULL,
    blessing TEXT NOT NULL,
    x_ratio REAL NOT NULL,
    y_ratio REAL NOT NULL,
    scale REAL DEFAULT 1.0,
    avatar_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);
"""


class PhotoWallDB:
    """无状态的线程安全 SQLite 访问器：每个操作使用独立连接。"""

    def __init__(self, db_path: Path):
        self.db_path = str(db_path)

    # --- 基础设施 ---

    async def _run(self, func, *args, **kwargs) -> Any:
        return await asyncio.get_running_loop().run_in_executor(
            None, partial(func, *args, **kwargs)
        )

    def _transaction(
        self,
        query: str,
        params: tuple = (),
        *,
        fetch: str = "none",
        commit: bool = False,
    ) -> Any:
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)

            if fetch == "one":
                result = cursor.fetchone()
            elif fetch == "all":
                result = cursor.fetchall()
            elif fetch == "rowcount":
                result = cursor.rowcount
            else:
                result = None

            if commit:
                conn.commit()
            return result
        except sqlite3.Error:
            if conn:
                conn.rollback()
            log.exception("照片墙数据库事务失败 | Query: %s", query)
            raise
        finally:
            if conn:
                conn.close()

    async def initialize(self) -> None:
        def _init() -> None:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute(_SCHEMA)
                conn.commit()
            finally:
                conn.close()

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        await self._run(_init)
        log.info("照片墙数据库初始化完成: %s", self.db_path)

    # --- 业务操作 ---

    async def upsert_entry(
        self,
        user_id: int,
        display_name: str,
        blessing: str,
        x_ratio: float,
        y_ratio: float,
        scale: float,
        avatar_path: Optional[str],
    ) -> sqlite3.Row:
        """插入或覆盖一个用户的留影（每人限一个位置）。"""
        query = """
            INSERT INTO photo_entries
                (user_id, display_name, blessing, x_ratio, y_ratio, scale, avatar_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                display_name = excluded.display_name,
                blessing = excluded.blessing,
                x_ratio = excluded.x_ratio,
                y_ratio = excluded.y_ratio,
                scale = excluded.scale,
                avatar_path = excluded.avatar_path,
                created_at = CURRENT_TIMESTAMP
        """
        await self._run(
            self._transaction,
            query,
            (user_id, display_name, blessing, x_ratio, y_ratio, scale, avatar_path),
            commit=True,
        )
        row = await self.get_entry(user_id)
        assert row is not None
        return row

    async def get_entry(self, user_id: int) -> Optional[sqlite3.Row]:
        query = "SELECT * FROM photo_entries WHERE user_id = ?"
        return await self._run(self._transaction, query, (user_id,), fetch="one")

    async def get_all_entries(self) -> List[sqlite3.Row]:
        query = "SELECT * FROM photo_entries ORDER BY id ASC"
        return await self._run(self._transaction, query, fetch="all")

    async def delete_entry(self, user_id: int) -> bool:
        query = "DELETE FROM photo_entries WHERE user_id = ?"
        count = await self._run(
            self._transaction, query, (user_id,), fetch="rowcount", commit=True
        )
        return bool(count)

    async def delete_entry_by_id(self, entry_id: int) -> bool:
        """按条目 ID 删除留影（管理员清理用）。"""
        query = "DELETE FROM photo_entries WHERE id = ?"
        count = await self._run(
            self._transaction, query, (entry_id,), fetch="rowcount", commit=True
        )
        return bool(count)
