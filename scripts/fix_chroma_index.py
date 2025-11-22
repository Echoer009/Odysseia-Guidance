#!/usr/bin/env python
# -*- coding: utf-8 -*-

import chromadb
import sys
import time

# === 配置区 ===
# 请确保此路径相对于您运行脚本的根目录是正确的
PERSIST_DIRECTORY = "data/forum_chroma_db"
# 这是您在日志中崩溃时操作的集合名称
COLLECTION_NAME = "forum_threads"
# ============


def fix_index():
    """
    通过将数据读出、删除旧集合、重建新集合并写回数据的方式，强制重建 ChromaDB 集合的索引。
    """
    print(f"🔧 正在连接 ChromaDB，数据目录: {PERSIST_DIRECTORY} ...")
    try:
        client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)
        # 尝试获取集合以验证连接和集合存在
        old_collection = client.get_collection(name=COLLECTION_NAME)
        count = old_collection.count()
        print(f"✅ 连接成功! 当前集合 '{COLLECTION_NAME}' 中共有 {count} 条数据。")
    except Exception as e:
        print(f"❌ 连接或获取集合失败: {e}")
        print("请检查 PERSIST_DIRECTORY 和 COLLECTION_NAME 是否配置正确。")
        return

    if count == 0:
        print("⚠️ 集合为空，无需执行修复操作。")
        return

    print("\n📦 步骤 1: 将所有数据分批读取到内存中...")

    all_ids = []
    all_embeddings = []
    all_metadatas = []
    all_documents = []

    batch_size = 1000  # 调整批次大小以适应您的内存情况
    offset = 0

    start_time = time.monotonic()

    while offset < count:
        try:
            results = old_collection.get(
                limit=batch_size,
                offset=offset,
                include=["metadatas", "documents", "embeddings"],
            )

            if not results.get("ids"):
                break  # 没有更多数据了

            all_ids.extend(results["ids"])
            all_embeddings.extend(results["embeddings"])
            all_metadatas.extend(results["metadatas"])
            all_documents.extend(results["documents"])

            # 使用 \r 实现原地更新，避免刷屏
            print(f"   已读取 {len(all_ids)} / {count} 条...", end="\r")
            offset += batch_size

        except Exception as e:
            print(f"\n❌ 在偏移量 {offset} 处读取数据时发生严重错误: {e}")
            print("   这可能表明 SQLite 数据文件本身也已损坏。操作无法继续。")
            return

    end_time = time.monotonic()
    print(f"\n✅ 数据全部读取完毕，耗时 {end_time - start_time:.2f} 秒。")

    print("\n🚨 警告: 下一步将永久删除并重建集合。请务必确认您已备份了 'data' 目录！")
    confirm = input("👉 请输入 'yes' 以继续执行: ")
    if confirm.lower() != "yes":
        print("操作已取消。")
        return

    # 2. 删除旧集合 (这将删除损坏的索引文件和相关数据)
    print("\n🗑️ 步骤 2: 正在删除旧集合，以清除损坏的索引...")
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"   集合 '{COLLECTION_NAME}' 已成功删除。")
    except Exception as e:
        print(f"\n❌ 删除集合时出错: {e}")
        return

    # 3. 重建集合
    print("\n🆕 步骤 3: 正在创建同名新集合...")
    try:
        new_collection = client.create_collection(name=COLLECTION_NAME)
        print(f"   新集合 '{COLLECTION_NAME}' 创建成功。")
    except Exception as e:
        print(f"\n❌ 创建新集合时出错: {e}")
        return

    # 4. 重新写入数据 (这将触发全新的、健康的索引构建)
    print("\n💾 步骤 4: 正在将数据分批写回新集合，并自动构建新索引...")

    total_batches = (len(all_ids) + batch_size - 1) // batch_size
    start_time = time.monotonic()

    for i in range(total_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, len(all_ids))

        print(
            f"   正在写入批次 {i + 1}/{total_batches} (条目 {start_idx} - {end_idx})...",
            end="\r",
        )

        new_collection.add(
            ids=all_ids[start_idx:end_idx],
            embeddings=all_embeddings[start_idx:end_idx],
            metadatas=all_metadatas[start_idx:end_idx],
            documents=all_documents[start_idx:end_idx],
        )

    end_time = time.monotonic()
    print(f"\n✅ 数据全部写入完毕，耗时 {end_time - start_time:.2f} 秒。")

    final_count = new_collection.count()
    print("\n🎉 修复完成！索引已成功重建。")
    print(f"   - 原始数据量: {count}")
    print(f"   - 修复后数据量: {final_count}")

    if count != final_count:
        print(
            f"   ⚠️ 警告: 数据量不匹配！可能在过程中丢失了 {count - final_count} 条数据。"
        )
    else:
        print("   ✅ 数据量一致，修复成功！")


if __name__ == "__main__":
    fix_index()
