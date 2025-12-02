import chromadb
import psycopg2
import psycopg2.extras
from tqdm import tqdm
import os
import json
import numpy as np  # 确保导入 numpy


# =================================================================
#  辅助类: 解决 NumPy 序列化问题
# =================================================================
class NumpyEncoder(json.JSONEncoder):
    """
    专门用来处理 NumPy 数据类型的 JSON Encoder
    """

    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        return super(NumpyEncoder, self).default(obj)


# =================================================================
#  配置区域
# =================================================================

# --- PostgreSQL 连接信息 ---
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DATABASE = os.getenv("PG_DATABASE", "braingirl_db")
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "000000")

# --- ChromaDB 源信息 ---
CHROMA_WB_PATH = "data/chroma_db"
CHROMA_WB_COLLECTION = "world_book"
TARGET_WB_SCHEMA = "world_book_vectors"
TARGET_WB_TABLE = f"{TARGET_WB_SCHEMA}.vectors"

CHROMA_FORUM_PATH = "data/forum_chroma_db"
CHROMA_FORUM_COLLECTION = "forum_threads"
TARGET_FORUM_SCHEMA = "forum_vectors"
TARGET_FORUM_TABLE = f"{TARGET_FORUM_SCHEMA}.vectors"


# =================================================================
#  迁移逻辑
# =================================================================


def migrate_collection(chroma_path, collection_name, pg_conn, target_table):
    """
    将指定的 ChromaDB 集合迁移到指定的 PostgreSQL 表中。
    """
    print(f"\n{'=' * 20}")
    print(f"▶️ 开始迁移 ChromaDB 集合 '{collection_name}' 从 '{chroma_path}'")
    print(f"▶️ 目标 PostgreSQL 表: '{target_table}'")
    print(f"{'=' * 20}")

    try:
        # 1. 连接到 ChromaDB
        print(f"  - 正在连接到 ChromaDB at '{chroma_path}'...")
        if not os.path.exists(chroma_path):
            print(f"  ❌ 错误: ChromaDB 路径不存在: '{chroma_path}'")
            return
        chroma_client = chromadb.PersistentClient(path=chroma_path)
        collection = chroma_client.get_collection(name=collection_name)
        collection_count = collection.count()
        print(
            f"  ✅ 连接成功. 集合 '{collection_name}' 中有 {collection_count} 个条目."
        )

        if collection_count == 0:
            print("  ⚠️ 集合中没有数据可迁移. 跳过.")
            return

        # 2. 从 ChromaDB 获取所有数据
        print("  - 正在获取所有向量数据... (这可能需要一些时间)")
        data = collection.get(include=["metadatas", "documents", "embeddings"])
        print("  ✅ 数据获取完毕.")

        # 3. 准备数据以便批量插入
        records_to_insert = []
        ids = data.get("ids", [])
        embeddings = data.get("embeddings", [])
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        for i in range(len(ids)):
            # --- 🔥 关键修复点 🔥 ---

            # 1. 处理 Embedding: 如果是 NumPy 数组，转为 List
            curr_embedding = embeddings[i]
            if hasattr(curr_embedding, "tolist"):
                curr_embedding = curr_embedding.tolist()

            # 使用 json.dumps 把它变成字符串，pgvector 会自动解析
            embedding_str = json.dumps(curr_embedding)

            # 2. 处理 Metadata: 使用自定义 Encoder 防止 NumPy 类型报错
            metadata_str = None
            if metadatas and metadatas[i]:
                # cls=NumpyEncoder 会处理 metadata 里的 numpy int/float
                metadata_str = json.dumps(metadatas[i], cls=NumpyEncoder)

            record = (
                ids[i],
                documents[i] if documents else None,
                metadata_str,
                embedding_str,
            )
            records_to_insert.append(record)

        if not records_to_insert:
            print("  ⚠️ 准备数据后发现没有可迁移的条目. 跳过.")
            return

        # 4. 批量插入数据到 PostgreSQL
        print(
            f"  - 准备将 {len(records_to_insert)} 条记录批量插入到 '{target_table}'..."
        )
        with pg_conn.cursor() as cursor:
            # 在迁移前清空目标表
            print(f"  - 清空目标表 '{target_table}'...")
            cursor.execute(f"TRUNCATE TABLE {target_table} RESTART IDENTITY;")

            query = f"""
                INSERT INTO {target_table} (id, document, metadata, embedding)
                VALUES %s
            """

            chunk_size = 500

            with tqdm(
                total=len(records_to_insert), desc=f"插入到 {target_table}"
            ) as pbar:
                for i in range(0, len(records_to_insert), chunk_size):
                    chunk = records_to_insert[i : i + chunk_size]
                    psycopg2.extras.execute_values(cursor, query, chunk, template=None)
                    pbar.update(len(chunk))

        pg_conn.commit()
        print(f"  ✅ 成功迁移 {len(records_to_insert)} 条记录.")

    except Exception as e:
        print(f"  ❌ 迁移过程中发生严重错误: {e}")
        if pg_conn:
            pg_conn.rollback()
        raise


def main():
    pg_conn = None
    try:
        # 连接到 PostgreSQL
        print("正在连接到 PostgreSQL 数据库...")
        conn_string = f"host='{PG_HOST}' port='{PG_PORT}' dbname='{PG_DATABASE}' user='{PG_USER}' password='{PG_PASSWORD}'"
        pg_conn = psycopg2.connect(conn_string)
        print("✅ PostgreSQL 连接成功.")

        # 任务1: 迁移 World Book
        migrate_collection(
            CHROMA_WB_PATH, CHROMA_WB_COLLECTION, pg_conn, TARGET_WB_TABLE
        )

        # 任务2: 迁移论坛
        migrate_collection(
            CHROMA_FORUM_PATH, CHROMA_FORUM_COLLECTION, pg_conn, TARGET_FORUM_TABLE
        )

        print("\n🎉 所有向量数据迁移任务已成功完成!")

    except psycopg2.Error as e:
        print(f"数据库连接或操作失败: {e}")
    except Exception as e:
        print(f"发生未知错误: {e}")
    finally:
        if pg_conn:
            pg_conn.close()
            print("PostgreSQL 连接已关闭.")


if __name__ == "__main__":
    main()
