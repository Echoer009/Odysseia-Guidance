import sqlite3
import os
import logging

# --- 日志记录器 ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# --- 常量定义 ---
# 脚本位于 scripts/ 目录下, 所以需要向上回退一级到项目根目录
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "chat.db")


def unmute_all_channels():
    """
    连接到数据库并清空 muted_channels 表，以解除所有频道的禁言。
    """
    if not os.path.exists(DB_PATH):
        log.error(f"数据库文件未找到: {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        log.info("正在清空 muted_channels 表...")
        # 使用 PRAGMA foreign_keys=OFF; 和 PRAGMA foreign_keys=ON; 是一种更安全的做法，
        # 但在这里 muted_channels 表没有外键，所以可以直接删除。
        cursor.execute("DELETE FROM muted_channels;")

        # 获取被删除的行数
        # 在DELETE之后，conn.total_changes会返回自连接打开后所有更改的行数，
        # 如果之前没有其他操作，这可以近似等于本次删除的行数。
        # cursor.rowcount 对于 DELETE 来说更准确。
        deleted_rows = cursor.rowcount

        conn.commit()

        log.info(f"操作成功完成。清除了 {deleted_rows} 个频道的禁言状态。")
        if deleted_rows == 0:
            log.info("数据库中没有发现需要解除的禁言频道。")

    except sqlite3.Error as e:
        log.error(f"操作数据库时出错: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    log.info("开始执行一次性解除所有频道禁言的脚本...")
    unmute_all_channels()
    log.info("脚本执行完毕。")
