import os
import sys
import argparse
import sqlite3
from dotenv import load_dotenv

# 将 src 目录添加到 Python 路径中
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))


def remove_channel_from_guidance():
    """
    一个一次性脚本，用于从数据库的 'paths' 表中安全地删除一个引导步骤，
    并重新排序受影响的引导路径。
    这会立即生效，影响所有新用户，且无需重新部署任何面板。
    """
    # --- 参数解析 ---
    parser = argparse.ArgumentParser(description="从实时引导路径中移除一个频道步骤。")
    parser.add_argument(
        "--guild-id", required=True, type=int, help="需要操作的服务器ID。"
    )
    parser.add_argument(
        "--channel-id",
        required=True,
        type=int,
        help="需要从引导路径中移除的频道ID (location_id)。",
    )
    args = parser.parse_args()

    guild_id = args.guild_id
    location_id_to_remove = args.channel_id

    # --- 数据库连接 ---
    print("正在加载 .env 文件...")
    load_dotenv()

    # 从 database.py 导入 DB_PATH 以确保路径一致
    try:
        from src.guidance.utils.database import DB_PATH

        db_path = DB_PATH
    except ImportError:
        print("错误：无法从 src.guidance.utils.database 导入 DB_PATH。")
        # 提供一个备用路径
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        db_path = os.path.join(project_root, "data", "guidance.db")
        print(f"将使用备用数据库路径: {db_path}")

    if not os.path.exists(db_path):
        print(f"错误：数据库文件不存在于: {db_path}")
        return

    print(f"正在连接到数据库: {db_path}...")
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print("数据库连接成功。")
    except Exception as e:
        print(f"数据库连接失败: {e}")
        if conn:
            conn.close()
        return

    # --- 核心逻辑 ---
    try:
        # 1. 查找所有包含该 location_id 的路径步骤，并获取它们的 tag_id 和 step_number
        # 我们需要连接 tags 表来确保只操作指定 guild_id 的数据
        find_query = """
            SELECT p.id, p.tag_id, p.step_number
            FROM paths p
            JOIN tags t ON p.tag_id = t.tag_id
            WHERE t.guild_id = ? AND p.location_id = ?
        """
        cursor.execute(find_query, (guild_id, location_id_to_remove))
        steps_to_delete = cursor.fetchall()

        if not steps_to_delete:
            print(
                f"在服务器 {guild_id} 的引导路径中未找到地点ID {location_id_to_remove}。无需操作。"
            )
            return

        print(
            f"找到了 {len(steps_to_delete)} 个包含地点ID {location_id_to_remove} 的引导步骤。"
        )

        # 2. 删除这些步骤
        path_ids_to_delete = [step[0] for step in steps_to_delete]
        # 使用 (?, ?, ...) 语法来安全地处理多个ID
        placeholders = ",".join("?" for _ in path_ids_to_delete)
        delete_query = f"DELETE FROM paths WHERE id IN ({placeholders})"
        cursor.execute(delete_query, path_ids_to_delete)
        print(f"已从 'paths' 表中删除 {cursor.rowcount} 个步骤。")

        # 3. 为每个受影响的 tag 重新排序步骤编号
        # 创建一个字典来存储每个tag被删除的步骤编号
        affected_tags = {}
        for path_id, tag_id, step_number in steps_to_delete:
            if tag_id not in affected_tags:
                affected_tags[tag_id] = []
            affected_tags[tag_id].append(step_number)

        print("正在为受影响的标签重新排序步骤...")
        for tag_id, deleted_steps in affected_tags.items():
            # 对每个tag，我们需要对每个被删除的步骤执行一次更新
            # 为了简化，我们按降序排序删除的步骤，这样可以避免连锁更新问题
            deleted_steps.sort(reverse=True)
            for step_number in deleted_steps:
                update_query = """
                    UPDATE paths
                    SET step_number = step_number - 1
                    WHERE tag_id = ? AND step_number > ?
                """
                cursor.execute(update_query, (tag_id, step_number))
                print(
                    f"  - 已为标签ID {tag_id} 中在步骤 {step_number} 之后的步骤重新编号。"
                )

        # 4. 提交事务
        conn.commit()
        print("\n所有更改已成功提交到数据库！")
        print(
            f"频道 {location_id_to_remove} 已从服务器 {guild_id} 的实时引导流程中移除。"
        )

    except Exception as e:
        print(f"\n处理过程中发生错误: {e}")
        conn.rollback()
    finally:
        print("正在关闭数据库连接。")
        conn.close()


if __name__ == "__main__":
    remove_channel_from_guidance()
