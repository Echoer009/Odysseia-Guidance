import sqlite3

DB_PATH = "data/chat.db"


def check_multi_guild_affection():
    """
    Finds and prints users who have affection records in more than one guild.
    """
    print("正在查询在多个服务器中拥有好感度记录的用户 (最多5条)...")
    try:
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.cursor()
            query = """
                SELECT 
                    user_id, 
                    GROUP_CONCAT(guild_id || ':' || affection_points, ', ') as records
                FROM 
                    ai_affection 
                GROUP BY 
                    user_id 
                HAVING 
                    COUNT(guild_id) > 1 
                LIMIT 5
            """
            results = cursor.execute(query).fetchall()

            if not results:
                print("未找到在多个服务器中拥有好感度记录的用户。")
                return

            print("查询结果:")
            for user_id, records in results:
                print(f"- User ID: {user_id}, Records: [{records}]")

    except sqlite3.Error as e:
        print(f"数据库查询出错: {e}")


if __name__ == "__main__":
    check_multi_guild_affection()
