import sqlite3
import os
import sys

# --- 常量定义 ---
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(_PROJECT_ROOT, "data", "chat.db")


def diagnose_user_memory(user_id: int):
    """
    直接连接到数据库，查询指定用户的个人记忆摘要。
    """
    print(f"--- 开始诊断用户 {user_id} 的个人记忆 ---")

    if not os.path.exists(DB_PATH):
        print(f"错误：数据库文件不存在于路径: {DB_PATH}")
        return

    print(f"数据库路径: {DB_PATH}")
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        print(f"执行查询: SELECT * FROM users WHERE user_id = {user_id}")
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user_profile = cursor.fetchone()

        if user_profile:
            print("\n[成功] 找到了该用户的记录。")
            print("--- 原始数据 ---")
            for key in user_profile.keys():
                print(f"  - {key}: {user_profile[key]}")

            summary = user_profile["personal_summary"]
            if summary:
                print("\n[诊断结果] 'personal_summary' 字段包含以下内容:")
                print("--------------------")
                print(summary)
                print("--------------------")
                print(
                    "\n结论：数据存在于数据库中。如果应用中无法显示，问题可能出在数据检索或处理的代码逻辑中。"
                )
            else:
                print("\n[诊断结果] 'personal_summary' 字段为空 (NULL 或空字符串)。")
                print(
                    "结论：数据库中没有为该用户存储摘要。问题可能出在数据保存的环节。"
                )

        else:
            print("\n[失败] 在 'users' 表中未找到该用户的记录。")
            print(
                "结论：数据库中没有该用户的数据。请检查用户ID是否正确，以及用户数据是否已正确创建。"
            )

    except sqlite3.Error as e:
        print(f"\n[错误] 查询数据库时发生错误: {e}")
    finally:
        if conn:
            conn.close()
        print("\n--- 诊断结束 ---")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python scripts/diagnose_memory.py <user_id>")
        sys.exit(1)

    try:
        target_user_id = int(sys.argv[1])
        diagnose_user_memory(target_user_id)
    except ValueError:
        print("错误: <user_id> 必须是一个有效的数字。")
        sys.exit(1)
