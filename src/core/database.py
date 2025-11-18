import sqlite3
import logging
import os
import asyncio
from functools import partial
from typing import Any, Callable, List

# --- 日志记录器 ---
log = logging.getLogger(__name__)


class AsyncDatabaseManager:
    """管理 SQLite 数据库的异步交互的基类。"""

    def __init__(self, db_path: str):
        """
        初始化数据库管理器。
        :param db_path: 数据库文件的绝对路径。
        """
        self.db_path = db_path
        # 确保数据库文件所在的目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    async def init_async(self):
        """异步初始化数据库，在事件循环中运行同步的建表逻辑。"""
        log.info(f"开始异步数据库初始化 for {self.db_path}...")
        await self._execute(self._init_database_logic)
        log.info(f"异步数据库初始化完成 for {self.db_path}。")

    def _init_database_logic(self):
        """
        包含所有同步数据库初始化逻辑的占位符方法。
        子类必须重写此方法以创建其特定的表。
        """
        raise NotImplementedError(
            "子类必须实现 _init_database_logic 方法来定义数据库表结构。"
        )

    async def _execute(self, func: Callable, *args, **kwargs) -> Any:
        """在线程池中执行一个同步的数据库操作。"""
        try:
            blocking_task = partial(func, *args, **kwargs)
            result = await asyncio.get_running_loop().run_in_executor(
                None, blocking_task
            )
            return result
        except Exception as e:
            log.error(f"数据库执行器出错 ({self.db_path}): {e}", exc_info=True)
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
            # 开启 WAL 模式以提高并发性能
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
            log.error(f"数据库事务失败，已回滚 ({self.db_path}): {e} | Query: {query}")
            raise
        finally:
            if conn:
                conn.close()

    def _db_executemany(self, query: str, params_list: List[tuple]):
        """
        一个同步的 executemany 函数，用于批量插入或更新。
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=15)
            conn.execute("PRAGMA journal_mode=WAL;")
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            log.error(f"数据库 executemany 失败 ({self.db_path}): {e} | Query: {query}")
            raise
        finally:
            if conn:
                conn.close()

    async def close(self):
        """关闭数据库连接（在当前无状态模型中无需操作）。"""
        log.info(f"数据库管理器 ({self.db_path}) 是无状态的，无需显式断开连接。")
        pass
