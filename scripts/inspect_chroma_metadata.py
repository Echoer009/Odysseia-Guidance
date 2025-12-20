import chromadb
import os
import argparse


def inspect_and_manage_chroma_db(delete_category=None):
    """
    连接到 ChromaDB，检查元数据，并根据需要删除指定类别的数据。
    """
    db_path = os.path.abspath("data/chroma_db")
    collection_name = "world_book"

    print(f"--- 正在连接到 ChromaDB ---")
    print(f"路径: {db_path}")
    print(f"集合: {collection_name}")

    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection(name=collection_name)
        print(f"\n--- 成功连接到集合 '{collection_name}' ---")

        total_count = collection.count()
        print(f"集合中当前共有 {total_count} 条记录。")

        if total_count == 0:
            print("\n集合为空，无需任何操作。")
            return

        # 如果指定了要删除的类别
        if delete_category:
            print(f"\n--- 准备删除类别为 '{delete_category}' 的所有数据 ---")

            ids_to_delete_results = collection.get(
                where={"category": delete_category}, include=[]
            )
            ids_to_delete = (
                ids_to_delete_results.get("ids", []) if ids_to_delete_results else []
            )

            if not ids_to_delete:
                print(f"未找到任何类别为 '{delete_category}' 的文档。无需删除。")
                return

            print(
                f"找到了 {len(ids_to_delete)} 条属于类别 '{delete_category}' 的记录。"
            )

            confirm = input("你确定要永久删除这些记录吗？(yes/no): ").lower()
            if confirm != "yes":
                print("操作已取消。")
                return

            collection.delete(ids=ids_to_delete)
            print(f"\n--- 删除成功 ---")
            print(f"已成功删除 {len(ids_to_delete)} 条记录。")

            new_count = collection.count()
            print(f"集合中剩余 {new_count} 条记录。")

        # 否则，执行检查逻辑
        else:
            limit = min(10, total_count)
            print(f"\n--- 正在获取前 {limit} 条记录的元数据进行检查 ---")

            results = collection.get(limit=limit, include=["metadatas"])
            metadatas = results.get("metadatas") if results else []

            if metadatas:
                print("元数据结构示例：")
                for i, meta in enumerate(metadatas):
                    print(f"  记录 #{i + 1}: {meta}")

            print("\n--- 正在统计所有 'category' 的文档数量 ---")
            results_all = collection.get(include=["metadatas"])
            all_metadatas = results_all.get("metadatas", []) if results_all else []

            category_counts = {}
            for meta in all_metadatas:
                category = meta.get("category", "未分类")
                category_counts[category] = category_counts.get(category, 0) + 1

            if category_counts:
                print("统计结果如下：")
                for category, count in sorted(category_counts.items()):
                    print(f"  - 类别 '{category}': {count} 条")
            else:
                print("未能按 'category' 进行统计。")

    except Exception as e:
        print(f"\n--- 操作失败 ---")
        print(f"错误详情: {e}")
        print("\n请确认：")
        print(f"1. ChromaDB 数据库是否存在于 '{db_path}'。")
        print(f"2. 集合名称 '{collection_name}' 是否正确。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="检查 ChromaDB 元数据，并可选择性地删除指定类别的数据。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--delete-category",
        type=str,
        help="指定要删除的元数据类别 (category)。\n"
        "例如: python scripts/inspect_chroma_metadata.py --delete-category '教程'",
    )

    args = parser.parse_args()

    inspect_and_manage_chroma_db(args.delete_category)
