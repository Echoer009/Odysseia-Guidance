import chromadb
import os
import argparse


def inspect_db(db_path):
    """
    列出指定 ChromaDB 路径下的所有集合，并允许检查特定一个。
    """
    if not os.path.exists(db_path):
        print(f"❌ 错误：数据库路径 '{db_path}' 不存在。")
        return

    print(f"🔍 正在检查 ChromaDB，路径: '{db_path}'")

    try:
        client = chromadb.PersistentClient(path=db_path)
        collections = client.list_collections()

        if not collections:
            print("   - 数据库为空，未发现任何集合。")
            return

        print("\n📚 可用的集合:")
        for i, col in enumerate(collections):
            print(f"   [{i + 1}] {col.name} (ID: {col.id})")

        return collections

    except Exception as e:
        print(f"   - ❌ 发生错误: {e}")
        return None


def peek_collection(db_path, collection_name, limit=3):
    """
    显示指定集合中的几条样本记录。
    """
    print(f"\n👀 正在查看集合 '{collection_name}' (最多显示 {limit} 条记录)...")

    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection(name=collection_name)

        count = collection.count()
        if count == 0:
            print("   - 这个集合是空的。")
            return

        print(f"   - 总记录数: {count}")

        results = collection.get(limit=limit, include=["documents", "metadatas"])

        for i in range(len(results["ids"])):
            print("-" * 40)
            print(f"记录 #{i + 1}")
            print(f"  ID: {results['ids'][i]}")

            metadata = results["metadatas"][i]
            print(f"  元数据 (Metadata): {metadata}")

            doc = results["documents"][i]
            # 为了便于阅读，截断过长的文本
            doc_preview = (doc[:150] + "...") if doc and len(doc) > 150 else doc
            print(f"  文档预览: {doc_preview}")

        print("-" * 40)

    except Exception as e:
        print(f"   - ❌ 无法查看集合 '{collection_name}': {e}")


def main():
    parser = argparse.ArgumentParser(description="检查 ChromaDB 的集合与数据。")
    parser.add_argument(
        "db_path", type=str, help="ChromaDB 数据库目录的路径 (例如: 'data/chroma_db')。"
    )
    parser.add_argument(
        "-c", "--collection", type=str, help="需要查看样本数据的集合名称。"
    )
    parser.add_argument(
        "-n", "--limit", type=int, default=3, help="查看样本数据时显示的记录数量。"
    )

    args = parser.parse_args()

    collections = inspect_db(args.db_path)

    if args.collection:
        if collections and any(c.name == args.collection for c in collections):
            peek_collection(args.db_path, args.collection, args.limit)
        else:
            print(f"\n在数据库中未找到名为 '{args.collection}' 的集合。")
    elif collections:
        print(
            "\nℹ️  提示：如需查看样本数据，请使用 `-c <集合名称>` 参数再次运行此脚本。"
        )


if __name__ == "__main__":
    main()
