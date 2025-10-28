import sqlite3
import json
import logging
import os
import asyncio
from functools import partial
from typing import Optional, List, Dict, Any, Callable

# --- 常量定义 ---
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "guidance.db")

# --- 日志记录器 ---
log = logging.getLogger(__name__)


class GuidanceDatabaseManager:
    """管理所有与引导模块相关的 SQLite 数据库的异步交互。"""

    def __init__(self, db_path: str = DB_PATH):
        """
        初始化数据库管理器。
        连接将在需要时在执行器中创建。
        """
        self.bot = None
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # 初始化现在是一个异步方法，需要在 main.py 中显式调用

    async def init_async(self):
        """异步初始化数据库，在事件循环中运行同步的建表逻辑。"""
        log.info("开始异步数据库初始化...")
        await self._execute(self._init_database_logic)
        log.info("异步数据库初始化完成。")

    def set_bot_instance(self, bot):
        """设置 bot 实例以便在数据库模块中使用。"""
        self.bot = bot

    def _init_database_logic(self):
        """
        包含所有同步数据库初始化逻辑的方法。
        这将在一个执行器中运行，以避免阻塞事件循环。
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # --- 服务器配置表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_configs (
                    guild_id INTEGER PRIMARY KEY,
                    buffer_role_id INTEGER,
                    verified_role_id INTEGER
                );
            """)

            # 检查并添加 default_tag_id 列到 guild_configs
            cursor.execute("PRAGMA table_info(guild_configs);")
            columns = [info[1] for info in cursor.fetchall()]
            if "default_tag_id" not in columns:
                cursor.execute("""
                    ALTER TABLE guild_configs
                    ADD COLUMN default_tag_id INTEGER REFERENCES tags(tag_id) ON DELETE SET NULL;
                """)
                log.info("已向 guild_configs 表添加 default_tag_id 列。")

            # --- 兴趣标签表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tags (
                    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    tag_name TEXT NOT NULL,
                    description TEXT,
                    sort_order INTEGER DEFAULT 0,
                    UNIQUE(guild_id, tag_name)
                );
            """)
            # --- 引导路径表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS paths (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    location_type TEXT NOT NULL,
                    message TEXT,
                    step_number INTEGER NOT NULL,
                    deployed_message_id INTEGER,
                    FOREIGN KEY (tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
                );
            """)
            # --- 引导面板配置表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS panel_configs (
                    guild_id INTEGER NOT NULL,
                    location_id INTEGER NOT NULL,
                    location_type TEXT NOT NULL,
                    panel_embed_data TEXT,
                    message_id INTEGER,
                    PRIMARY KEY (guild_id, location_id)
                );
            """)
            # --- 触发引导的身份组表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trigger_roles (
                    guild_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, role_id)
                );
            """)
            # --- 消息模板表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_templates (
                    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    template_name TEXT NOT NULL,
                    template_data TEXT NOT NULL,
                    UNIQUE(guild_id, template_name)
                );
            """)
            # --- 用户引导进度跟踪表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_progress (
                    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    guidance_stage TEXT,
                    selected_tags_json TEXT,
                    generated_path_json TEXT,
                    completed_path_json TEXT,
                    current_step INTEGER,
                    UNIQUE(user_id, guild_id)
                );
            """)

            # 检查并添加 remaining_path_json 列到 user_progress
            cursor.execute("PRAGMA table_info(user_progress);")
            columns = [info[1] for info in cursor.fetchall()]
            if "remaining_path_json" not in columns:
                cursor.execute("""
                    ALTER TABLE user_progress
                    ADD COLUMN remaining_path_json TEXT;
                """)
                log.info("已向 user_progress 表添加 remaining_path_json 列。")

            # --- 已部署面板信息表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deployed_panels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    last_deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # --- 频道专属消息表 ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS channel_messages (
                    channel_id INTEGER PRIMARY KEY,
                    guild_id INTEGER NOT NULL,
                    permanent_message_data TEXT,
                    temporary_message_data TEXT,
                    deployed_message_id INTEGER
                    );
            """)

            conn.commit()
            log.info(f"数据库表在 {self.db_path} 同步初始化成功。")
        except sqlite3.Error as e:
            log.error(f"同步初始化数据库表时出错: {e}")
            raise
        finally:
            if "conn" in locals() and conn:
                conn.close()

    async def _execute(self, func: Callable, *args, **kwargs) -> Any:
        """在线程池中执行一个同步的数据库操作。"""
        conn = None
        try:
            # 使用 functools.partial 将函数和参数绑定在一起
            blocking_task = partial(func, *args, **kwargs)
            # 在默认的执行器（线程池）中运行该任务
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
        一个通用的同步事务函数，用于被 _execute 调用。
        :param query: SQL 查询语句。
        :param params: 查询参数。
        :param fetch: 'one', 'all', or 'none'。
        :param commit: 是否提交事务。
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
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
            log.error(f"数据库事务失败: {e} | Query: {query}")
            raise
        finally:
            if conn:
                conn.close()

    def _db_executemany(self, query: str, params_list: List[tuple]):
        """
        一个同步的 executemany 函数。
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            log.error(f"数据库 executemany 失败: {e} | Query: {query}")
            raise
        finally:
            if conn:
                conn.close()

    async def close(self):
        """关闭数据库连接（在异步模型中通常不需要）。"""
        log.info("数据库管理器正在关闭（异步模式下无操作）。")
        pass

    # --- Guild Configs ---
    async def get_guild_config(self, guild_id: int) -> Optional[sqlite3.Row]:
        query = "SELECT * FROM guild_configs WHERE guild_id = ?"
        return await self._execute(
            self._db_transaction, query, (guild_id,), fetch="one"
        )

    async def set_stage_role(self, guild_id: int, stage: str, role_id: Optional[int]):
        field_name = f"{stage}_role_id"
        if field_name not in ["buffer_role_id", "verified_role_id"]:
            raise ValueError("无效的阶段名称")

        query = f"""
            INSERT INTO guild_configs (guild_id, {field_name})
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                {field_name} = excluded.{field_name};
        """
        await self._execute(
            self._db_transaction, query, (guild_id, role_id), commit=True
        )
        log.info(f"已为服务器 {guild_id} 设置 {stage} 身份组为 {role_id}")

    async def set_default_tag(self, guild_id: int, tag_id: Optional[int]):
        """设置或取消服务器的默认标签。"""
        query = """
            INSERT INTO guild_configs (guild_id, default_tag_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                default_tag_id = excluded.default_tag_id;
        """
        await self._execute(
            self._db_transaction, query, (guild_id, tag_id), commit=True
        )
        log.info(f"已为服务器 {guild_id} 设置默认标签 ID 为 {tag_id}")

    # --- Tags ---
    async def add_tag(
        self,
        guild_id: int,
        name: str,
        description: Optional[str] = None,
        sort_order: int = 0,
    ) -> int:
        query = "INSERT INTO tags (guild_id, tag_name, description, sort_order) VALUES (?, ?, ?, ?)"
        try:
            lastrowid = await self._execute(
                self._db_transaction,
                query,
                (guild_id, name, description, sort_order),
                commit=True,
                fetch="lastrowid",
            )
            log.info(f"已在服务器 {guild_id} 添加标签: {name}")
            return lastrowid
        except sqlite3.IntegrityError:
            log.warning(f"尝试在服务器 {guild_id} 添加已存在的标签: {name}")
            raise

    async def get_tag_by_id(self, tag_id: int) -> Optional[sqlite3.Row]:
        query = "SELECT * FROM tags WHERE tag_id = ?"
        return await self._execute(self._db_transaction, query, (tag_id,), fetch="one")

    async def get_all_tags(self, guild_id: int) -> List[sqlite3.Row]:
        query = "SELECT * FROM tags WHERE guild_id = ? ORDER BY sort_order, tag_name"
        return await self._execute(
            self._db_transaction, query, (guild_id,), fetch="all"
        )

    async def get_tag_by_name(self, guild_id: int, name: str) -> Optional[sqlite3.Row]:
        query = "SELECT * FROM tags WHERE guild_id = ? AND tag_name = ?"
        return await self._execute(
            self._db_transaction, query, (guild_id, name), fetch="one"
        )

    async def update_tag(
        self, tag_id: int, name: str, description: Optional[str], sort_order: int
    ) -> int:
        query = "UPDATE tags SET tag_name = ?, description = ?, sort_order = ? WHERE tag_id = ?"
        try:
            rowcount = await self._execute(
                self._db_transaction,
                query,
                (name, description, sort_order, tag_id),
                commit=True,
                fetch="rowcount",
            )
            if rowcount > 0:
                log.info(f"已更新标签 ID {tag_id} 为: {name}")
            return rowcount
        except sqlite3.IntegrityError:
            log.warning(f"尝试将标签 ID {tag_id} 的名称更新为已存在的名称: {name}")
            raise

    async def delete_tag(self, tag_id: int) -> int:
        query = "DELETE FROM tags WHERE tag_id = ?"
        deleted_rows = await self._execute(
            self._db_transaction, query, (tag_id,), commit=True, fetch="rowcount"
        )
        if deleted_rows > 0:
            log.info(f"已通过 ID {tag_id} 移除标签。")
        return deleted_rows

    async def sync_tags_from_config(self, guild_id: int, config_data: Dict[str, Any]):
        """从解析的 YAML/JSON 配置数据同步标签和路径。"""
        tags_in_config = config_data.get("tags", [])

        def _transaction():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                # 1. 获取当前数据库中的所有标签
                cursor.execute(
                    "SELECT tag_name, tag_id FROM tags WHERE guild_id = ?", (guild_id,)
                )
                db_tags = {row[0]: row[1] for row in cursor.fetchall()}

                # 2. 遍历配置文件中的标签
                config_tag_names = set()
                for i, tag_config in enumerate(tags_in_config):
                    tag_name = tag_config["name"]
                    description = tag_config.get("description")
                    sort_order = i
                    config_tag_names.add(tag_name)

                    if tag_name in db_tags:
                        # 更新现有标签
                        cursor.execute(
                            "UPDATE tags SET description = ?, sort_order = ? WHERE tag_id = ?",
                            (description, sort_order, db_tags[tag_name]),
                        )
                    else:
                        # 插入新标签
                        cursor.execute(
                            "INSERT INTO tags (guild_id, tag_name, description, sort_order) VALUES (?, ?, ?, ?)",
                            (guild_id, tag_name, description, sort_order),
                        )

                # 3. 删除配置文件中不再存在的标签
                tags_to_delete = set(db_tags.keys()) - config_tag_names
                if tags_to_delete:
                    for tag_name in tags_to_delete:
                        cursor.execute(
                            "DELETE FROM tags WHERE tag_id = ?", (db_tags[tag_name],)
                        )
                        log.info(
                            f"已从数据库中删除标签 '{tag_name}'，因为它不再存在于配置文件中。"
                        )

                conn.commit()
                log.info(f"已成功为服务器 {guild_id} 同步标签。")

            except sqlite3.Error as e:
                conn.rollback()
                log.error(f"从配置文件同步标签时出错: {e}")
                raise
            finally:
                conn.close()

        await self._execute(_transaction)

    async def sync_tags_from_config(self, guild_id: int, config_data: Dict[str, Any]):
        """从解析的 YAML/JSON 配置数据同步标签和路径。"""
        tags_in_config = config_data.get("tags", [])

        def _transaction():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                # 1. 获取当前数据库中的所有标签
                cursor.execute(
                    "SELECT tag_name, tag_id FROM tags WHERE guild_id = ?", (guild_id,)
                )
                db_tags = {row[0]: row[1] for row in cursor.fetchall()}

                # 2. 遍历配置文件中的标签
                config_tag_names = set()
                for i, tag_config in enumerate(tags_in_config):
                    tag_name = tag_config["name"]
                    description = tag_config.get("description")
                    sort_order = i
                    config_tag_names.add(tag_name)

                    if tag_name in db_tags:
                        # 更新现有标签
                        cursor.execute(
                            "UPDATE tags SET description = ?, sort_order = ? WHERE tag_id = ?",
                            (description, sort_order, db_tags[tag_name]),
                        )
                    else:
                        # 插入新标签
                        cursor.execute(
                            "INSERT INTO tags (guild_id, tag_name, description, sort_order) VALUES (?, ?, ?, ?)",
                            (guild_id, tag_name, description, sort_order),
                        )

                # 3. 删除配置文件中不再存在的标签
                tags_to_delete = set(db_tags.keys()) - config_tag_names
                if tags_to_delete:
                    for tag_name in tags_to_delete:
                        cursor.execute(
                            "DELETE FROM tags WHERE tag_id = ?", (db_tags[tag_name],)
                        )
                        log.info(
                            f"已从数据库中删除标签 '{tag_name}'，因为它不再存在于配置文件中。"
                        )

                conn.commit()
                log.info(f"已成功为服务器 {guild_id} 同步标签。")

            except sqlite3.Error as e:
                conn.rollback()
                log.error(f"从配置文件同步标签时出错: {e}")
                raise
            finally:
                conn.close()

        await self._execute(_transaction)

    # --- Paths ---
    async def set_path_for_tag(self, tag_id: int, paths_data: List[Dict[str, Any]]):
        # This needs a more complex transaction
        def _transaction():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM paths WHERE tag_id = ?", (tag_id,))
                steps_to_insert = [
                    (
                        tag_id,
                        path["location_id"],
                        path["location_type"],
                        path.get("message"),
                        i + 1,
                    )
                    for i, path in enumerate(paths_data)
                ]
                if steps_to_insert:
                    cursor.executemany(
                        "INSERT INTO paths (tag_id, location_id, location_type, message, step_number) VALUES (?, ?, ?, ?, ?)",
                        steps_to_insert,
                    )
                conn.commit()
                log.info(
                    f"已为标签 {tag_id} 设置新路径，包含 {len(paths_data)} 个步骤。"
                )
            except sqlite3.Error as e:
                conn.rollback()
                log.error(f"为标签 {tag_id} 设置路径失败: {e}")
                raise
            finally:
                conn.close()

        await self._execute(_transaction)

    async def get_path_for_tag(self, tag_id: int) -> List[sqlite3.Row]:
        query = "SELECT * FROM paths WHERE tag_id = ? ORDER BY step_number ASC"
        return await self._execute(self._db_transaction, query, (tag_id,), fetch="all")

    async def remove_path_step(self, path_id: int):
        def _transaction():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT tag_id, step_number FROM paths WHERE id = ?", (path_id,)
                )
                result = cursor.fetchone()
                if not result:
                    return

                tag_id, deleted_step_number = result[0], result[1]
                cursor.execute("DELETE FROM paths WHERE id = ?", (path_id,))
                cursor.execute(
                    "UPDATE paths SET step_number = step_number - 1 WHERE tag_id = ? AND step_number > ?",
                    (tag_id, deleted_step_number),
                )
                conn.commit()
                log.info(f"已删除路径步骤 {path_id} 并重新排序。")
            except sqlite3.Error as e:
                conn.rollback()
                log.error(f"删除路径步骤失败 (path_id: {path_id}): {e}")
                raise
            finally:
                conn.close()

        await self._execute(_transaction)

    async def get_configured_path_locations(self, guild_id: int) -> List[sqlite3.Row]:
        """获取一个服务器中所有已配置在引导路径中的唯一地点（频道/帖子）。"""
        query = """
            SELECT DISTINCT p.location_id, p.location_type
            FROM paths p
            INNER JOIN tags t ON p.tag_id = t.tag_id
            WHERE t.guild_id = ?
        """
        return await self._execute(
            self._db_transaction, query, (guild_id,), fetch="all"
        )

    # --- Trigger Roles ---
    async def get_trigger_roles(self, guild_id: int) -> List[sqlite3.Row]:
        query = "SELECT role_id FROM trigger_roles WHERE guild_id = ?"
        return await self._execute(
            self._db_transaction, query, (guild_id,), fetch="all"
        )

    async def set_trigger_roles(self, guild_id: int, role_ids: List[int]):
        def _transaction():
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "DELETE FROM trigger_roles WHERE guild_id = ?", (guild_id,)
                )
                if role_ids:
                    roles_to_insert = [(guild_id, role_id) for role_id in role_ids]
                    cursor.executemany(
                        "INSERT INTO trigger_roles (guild_id, role_id) VALUES (?, ?)",
                        roles_to_insert,
                    )
                conn.commit()
                log.info(f"已为服务器 {guild_id} 设置 {len(role_ids)} 个触发身份组。")
            except sqlite3.Error as e:
                conn.rollback()
                log.error(f"设置触发身份组失败 (guild_id: {guild_id}): {e}")
                raise
            finally:
                conn.close()

        await self._execute(_transaction)

    # --- Message Templates ---
    async def get_message_template(
        self, guild_id: int, template_name: str
    ) -> Optional[Dict[str, Any]]:
        query = "SELECT template_data FROM message_templates WHERE guild_id = ? AND template_name = ?"
        row = await self._execute(
            self._db_transaction, query, (guild_id, template_name), fetch="one"
        )
        if row:
            try:
                return json.loads(row["template_data"])
            except (json.JSONDecodeError, TypeError):
                log.warning(f"解析服务器 {guild_id} 的模板 {template_name} 时出错。")
        return None

    async def set_message_template(
        self,
        guild_id: int,
        template_name: str,
        template_data: Dict[str, Any] | List[Dict[str, Any]],
    ):
        template_json = json.dumps(template_data, ensure_ascii=False)
        query = """
            INSERT INTO message_templates (guild_id, template_name, template_data)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, template_name) DO UPDATE SET
                template_data = excluded.template_data;
        """
        await self._execute(
            self._db_transaction,
            query,
            (guild_id, template_name, template_json),
            commit=True,
        )
        log.info(f"已为服务器 {guild_id} 设置消息模板: {template_name}")

    async def delete_all_message_templates(self, guild_id: int) -> int:
        """删除一个服务器的所有消息模板。"""
        query = "DELETE FROM message_templates WHERE guild_id = ?"
        deleted_rows = await self._execute(
            self._db_transaction, query, (guild_id,), commit=True, fetch="rowcount"
        )
        if deleted_rows > 0:
            log.info(f"已删除服务器 {guild_id} 的 {deleted_rows} 个消息模板。")
        return deleted_rows

    async def get_all_message_templates(self, guild_id: int) -> Dict[str, Any]:
        query = "SELECT template_name, template_data FROM message_templates WHERE guild_id = ?"
        rows = await self._execute(
            self._db_transaction, query, (guild_id,), fetch="all"
        )
        templates = {}
        for row in rows:
            try:
                templates[row["template_name"]] = json.loads(row["template_data"])
            except (json.JSONDecodeError, TypeError):
                log.warning(
                    f"解析服务器 {guild_id} 的模板 {row['template_name']} 时出错。"
                )
        return templates

    # --- User Progress ---
    async def get_user_progress(
        self, user_id: int, guild_id: int
    ) -> Optional[sqlite3.Row]:
        query = "SELECT * FROM user_progress WHERE user_id = ? AND guild_id = ?"
        return await self._execute(
            self._db_transaction, query, (user_id, guild_id), fetch="one"
        )

    async def create_or_reset_user_progress(
        self,
        user_id: int,
        guild_id: int,
        status: str,
        guidance_stage: Optional[str] = None,
    ) -> sqlite3.Row:
        def _transaction():
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "DELETE FROM user_progress WHERE user_id = ? AND guild_id = ?",
                    (user_id, guild_id),
                )
                cursor.execute(
                    "INSERT INTO user_progress (user_id, guild_id, status, guidance_stage, current_step) VALUES (?, ?, ?, ?, ?)",
                    (user_id, guild_id, status, guidance_stage, 1),
                )
                conn.commit()
                cursor.execute(
                    "SELECT * FROM user_progress WHERE progress_id = ?",
                    (cursor.lastrowid,),
                )
                log.info(
                    f"已为用户 {user_id} 在服务器 {guild_id} 创建或重置了进度记录，新状态: {status}, 阶段: {guidance_stage}"
                )
                return cursor.fetchone()
            except sqlite3.Error as e:
                conn.rollback()
                log.error(f"创建或重置用户进度失败 (user_id: {user_id}): {e}")
                raise
            finally:
                conn.close()

        return await self._execute(_transaction)

    async def update_user_progress(
        self, user_id: int, guild_id: int, **kwargs
    ) -> Optional[sqlite3.Row]:
        updates = {key: value for key, value in kwargs.items() if value is not None}
        if not updates:
            return None

        for key, value in updates.items():
            if isinstance(value, (list, dict)):
                updates[key] = json.dumps(value)

        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values())
        values.append(user_id)
        values.append(guild_id)

        query = (
            f"UPDATE user_progress SET {set_clause} WHERE user_id = ? AND guild_id = ?"
        )
        await self._execute(self._db_transaction, query, tuple(values), commit=True)
        # log.info(f"用户 {user_id} 的进度已更新: {updates}")
        return await self.get_user_progress(user_id, guild_id)

    # --- Deployed Panels ---
    async def log_deployment(self, guild_id: int, channel_id: int, message_id: int):
        query = """
            INSERT INTO deployed_panels (guild_id, channel_id, message_id, last_deployed_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                message_id = excluded.message_id,
                last_deployed_at = excluded.last_deployed_at
        """
        await self._execute(
            self._db_transaction, query, (guild_id, channel_id, message_id), commit=True
        )
        log.info(
            f"已记录服务器 {guild_id} 的面板部署信息 (Channel: {channel_id}, Message: {message_id})"
        )

    async def get_deployed_panel(self, guild_id: int) -> Optional[sqlite3.Row]:
        query = "SELECT channel_id, message_id FROM deployed_panels WHERE guild_id = ?"
        return await self._execute(
            self._db_transaction, query, (guild_id,), fetch="one"
        )

    # --- Channel Messages ---
    async def set_channel_message(
        self,
        guild_id: int,
        channel_id: int,
        permanent_data: Optional[Dict[str, Any]],
        temporary_data: Optional[Dict[str, Any]],
    ):
        permanent_json = json.dumps(permanent_data) if permanent_data else None
        temporary_json = json.dumps(temporary_data) if temporary_data else None
        query = """
            INSERT INTO channel_messages (channel_id, guild_id, permanent_message_data, temporary_message_data)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                guild_id = excluded.guild_id,
                permanent_message_data = excluded.permanent_message_data,
                temporary_message_data = excluded.temporary_message_data
        """
        await self._execute(
            self._db_transaction,
            query,
            (channel_id, guild_id, permanent_json, temporary_json),
            commit=True,
        )
        log.info(f"已为频道 {channel_id} 设置专属消息。")

    async def get_channel_message(self, channel_id: int) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM channel_messages WHERE channel_id = ?"
        row = await self._execute(
            self._db_transaction, query, (channel_id,), fetch="one"
        )
        if not row:
            return None

        data = dict(row)
        try:
            if data.get("permanent_message_data"):
                data["permanent_message_data"] = json.loads(
                    data["permanent_message_data"]
                )
            if data.get("temporary_message_data"):
                data["temporary_message_data"] = json.loads(
                    data["temporary_message_data"]
                )
        except (json.JSONDecodeError, TypeError):
            log.warning(f"解析频道 {channel_id} 的专属消息JSON时出错。")
        return data

    def get_channel_message_sync(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """同步版本的 get_channel_message，用于视图内部的快速查找。"""
        row = self._db_transaction(
            "SELECT * FROM channel_messages WHERE channel_id = ?",
            (channel_id,),
            fetch="one",
        )
        if not row:
            return None

        data = dict(row)
        try:
            if data.get("permanent_message_data"):
                data["permanent_message_data"] = json.loads(
                    data["permanent_message_data"]
                )
            if data.get("temporary_message_data"):
                data["temporary_message_data"] = json.loads(
                    data["temporary_message_data"]
                )
        except (json.JSONDecodeError, TypeError):
            log.warning(f"同步解析频道 {channel_id} 的专属消息JSON时出错。")
        return data

    async def get_all_channel_messages(self, guild_id: int) -> List[Dict[str, Any]]:
        query = "SELECT * FROM channel_messages WHERE guild_id = ?"
        rows = await self._execute(
            self._db_transaction, query, (guild_id,), fetch="all"
        )
        results = []
        for row in rows:
            data = dict(row)
            try:
                if data.get("permanent_message_data"):
                    data["permanent_message_data"] = json.loads(
                        data["permanent_message_data"]
                    )
                if data.get("temporary_message_data"):
                    data["temporary_message_data"] = json.loads(
                        data["temporary_message_data"]
                    )
                results.append(data)
            except (json.JSONDecodeError, TypeError):
                log.warning(f"解析频道 {data['channel_id']} 的专属消息JSON时出错。")
        return results

    async def remove_channel_message(self, channel_id: int) -> int:
        query = "DELETE FROM channel_messages WHERE channel_id = ?"
        deleted_rows = await self._execute(
            self._db_transaction, query, (channel_id,), commit=True, fetch="rowcount"
        )
        if deleted_rows > 0:
            log.info(f"已删除频道 {channel_id} 的专属消息配置。")
        return deleted_rows

    async def update_channel_deployment_id(
        self, channel_id: int, message_id: Optional[int]
    ):
        query = (
            "UPDATE channel_messages SET deployed_message_id = ? WHERE channel_id = ?"
        )
        await self._execute(
            self._db_transaction, query, (message_id, channel_id), commit=True
        )
        log.info(f"已更新频道 {channel_id} 的部署消息ID为 {message_id}。")


# --- 单例实例 ---
guidance_db_manager = GuidanceDatabaseManager()

if __name__ == "__main__":
    print("这是一个异步数据库模块，不能直接运行。请通过主程序导入和使用。")
