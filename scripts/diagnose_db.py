import os
import sqlite3
from datetime import datetime

# --- 常量定义 ---
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "chat.db")


def diagnose_and_fix_database():
    """
    诊断并修复数据库 'file is not a database' 的问题。
    如果文件损坏或为空，则将其重命名备份。
    """
    print(f"正在诊断数据库文件: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print("数据库文件不存在。程序将在下次启动时自动创建。")
        return

    # 检查文件大小是否为0
    if os.path.getsize(DB_PATH) == 0:
        print("错误: 数据库文件大小为 0KB，这是一个空文件。")
        rename_corrupt_db()
        return

    # 尝试连接数据库并检查完整性
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        result = cursor.fetchone()
        conn.close()

        if result[0] == "ok":
            print("数据库文件状态正常。")
        else:
            print(f"数据库完整性检查失败: {result}")
            print("错误: 数据库文件已损坏。")
            rename_corrupt_db()

    except sqlite3.DatabaseError as e:
        if "file is not a database" in str(e):
            print("错误: 确认数据库文件已损坏或格式不正确。")
            rename_corrupt_db()
        else:
            print(f"发生未知的数据库错误: {e}")
    except Exception as e:
        print(f"发生意外错误: {e}")


def rename_corrupt_db():
    """
    重命名损坏的数据库文件作为备份。
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.corrupt.{timestamp}"

    try:
        os.rename(DB_PATH, backup_path)
        print(f"已将损坏的数据库文件备份到: {backup_path}")
        print("下次启动应用程序时，将自动创建一个新的数据库。")
    except OSError as e:
        print(f"重命名文件失败: {e}")


if __name__ == "__main__":
    diagnose_and_fix_database()
