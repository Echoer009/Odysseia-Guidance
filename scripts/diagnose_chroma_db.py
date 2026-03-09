#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ChromaDB 诊断脚本

检查：
1. ChromaDB 集合是否存在
2. 向量维度
3. 数据是否损坏
4. 数据量统计
"""

import os
import sys
import sqlite3
import chromadb
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.chat.config import chat_config as config


def check_chroma_collection(db_path: str, collection_name: str, db_label: str):
    """
    检查指定的 ChromaDB 集合

    Args:
        db_path: ChromaDB 数据库路径
        collection_name: 集合名称
        db_label: 数据库标签（用于输出）
    """
    print(f"\n{'=' * 80}")
    print(f"检查 {db_label}")
    print(f"{'=' * 80}")
    print(f"路径: {db_path}")
    print(f"集合: {collection_name}")

    # 检查路径是否存在
    if not os.path.exists(db_path):
        print(f"❌ 数据库路径不存在: {db_path}")
        return

    print(f"✅ 数据库路径存在")

    # 检查 SQLite 文件
    sqlite_path = os.path.join(db_path, "chroma.sqlite3")
    if not os.path.exists(sqlite_path):
        print(f"❌ SQLite 文件不存在: {sqlite_path}")
        return

    print(f"✅ SQLite 文件存在")

    # 检查 SQLite 文件大小
    file_size = os.path.getsize(sqlite_path)
    print(f"📊 SQLite 文件大小: {file_size / (1024 * 1024):.2f} MB")

    # 尝试连接到 ChromaDB
    try:
        client = chromadb.PersistentClient(path=db_path)
        print(f"✅ 成功连接到 ChromaDB")
    except Exception as e:
        print(f"❌ 连接 ChromaDB 失败: {e}")
        return

    # 检查集合是否存在
    try:
        collection = client.get_collection(name=collection_name)
        print(f"✅ 集合 '{collection_name}' 存在")
    except Exception as e:
        print(f"❌ 集合 '{collection_name}' 不存在或无法访问: {e}")
        return

    # 获取集合元数据
    try:
        metadata = collection.metadata
        print(f"\n📋 集合元数据:")
        print(f"   {metadata}")

        # 检查距离度量
        if metadata and "hnsw:space" in metadata:
            space = metadata["hnsw:space"]
            print(f"   ✅ 距离度量: {space}")
        else:
            print(f"   ⚠️  未找到距离度量信息")
    except Exception as e:
        print(f"⚠️  无法获取集合元数据: {e}")

    # 获取数据统计
    try:
        count = collection.count()
        print(f"\n📊 数据统计:")
        print(f"   总文档数: {count}")

        if count == 0:
            print(f"   ⚠️  集合为空")
            return
    except Exception as e:
        print(f"❌ 无法获取文档数量: {e}")
        return

    # 检查向量维度
    try:
        # 获取前几个文档来检查维度
        results = collection.get(limit=5, include=["embeddings"])

        # 修复：正确检查results字典
        if results is not None and "embeddings" in results:
            embeddings = results["embeddings"]

            if (
                embeddings is not None
                and len(embeddings) > 0
                and embeddings[0] is not None
            ):
                dimension = len(embeddings[0])
                print(f"   ✅ 向量维度: {dimension}")

                # 检查是否所有向量维度一致
                all_same_dim = all(
                    len(emb) == dimension for emb in embeddings if emb is not None
                )
                if all_same_dim:
                    print(f"   ✅ 所有向量维度一致")
                else:
                    print(f"   ❌ 向量维度不一致！")
                    for i, emb in enumerate(embeddings):
                        if emb is not None:
                            print(f"      文档 {i}: {len(emb)} 维")
            else:
                print(f"   ⚠️  未找到向量数据")
        else:
            print(f"   ⚠️  无法获取向量数据")
    except Exception as e:
        print(f"❌ 检查向量维度时出错: {e}")
        import traceback

        traceback.print_exc()

    # 检查 SQLite 数据完整性
    print(f"\n🔍 检查 SQLite 数据完整性...")
    try:
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"   ✅ 找到 {len(tables)} 个表:")
        for table in tables:
            print(f"      - {table[0]}")

        # 检查 segments 表
        cursor.execute("SELECT COUNT(*) FROM segments;")
        segment_count = cursor.fetchone()[0]
        print(f"   📊 segments 表记录数: {segment_count}")

        # 检查是否有损坏的数据
        cursor.execute("SELECT COUNT(*) FROM segments WHERE id IS NULL OR id = '';")
        null_id_count = cursor.fetchone()[0]
        if null_id_count > 0:
            print(f"   ⚠️  发现 {null_id_count} 条记录的 ID 为空")
        else:
            print(f"   ✅ 所有记录都有有效的 ID")

        # 检查segments表结构
        cursor.execute("PRAGMA table_info(segments);")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        print(f"   📋 segments 表列: {', '.join(column_names)}")

        # 检查是否有vector列
        if "vector" in column_names:
            # 检查是否有损坏的向量数据
            cursor.execute("SELECT COUNT(*) FROM segments WHERE vector IS NULL;")
            null_vector_count = cursor.fetchone()[0]
            if null_vector_count > 0:
                print(f"   ⚠️  发现 {null_vector_count} 条记录的向量为空")
            else:
                print(f"   ✅ 所有记录都有有效的向量")
        else:
            print(
                f"   ℹ️  segments 表没有 vector 列（ChromaDB v5+ 可能使用不同的存储方式）"
            )

        conn.close()
    except Exception as e:
        print(f"❌ 检查 SQLite 数据完整性时出错: {e}")
        import traceback

        traceback.print_exc()

    # 测试查询功能
    print(f"\n🧪 测试查询功能...")
    try:
        # 尝试执行一个简单的查询
        results = collection.get(limit=1)
        if results and results.get("ids"):
            print(f"   ✅ 查询功能正常")
            print(f"   📄 示例文档 ID: {results['ids'][0]}")
        else:
            print(f"   ⚠️  查询返回空结果")
    except Exception as e:
        print(f"❌ 查询功能异常: {e}")
        import traceback

        traceback.print_exc()


def main():
    """主函数"""
    print(f"\n{'=' * 80}")
    print(f"ChromaDB 诊断工具")
    print(f"{'=' * 80}")

    # 检查论坛搜索 ChromaDB
    check_chroma_collection(
        db_path=config.FORUM_VECTOR_DB_PATH,
        collection_name=config.FORUM_VECTOR_DB_COLLECTION_NAME,
        db_label="论坛搜索 ChromaDB",
    )

    # 检查世界书 ChromaDB（遗留配置）
    check_chroma_collection(
        db_path=config.VECTOR_DB_PATH,
        collection_name=config.VECTOR_DB_COLLECTION_NAME,
        db_label="世界书 ChromaDB (遗留配置)",
    )

    print(f"\n{'=' * 80}")
    print(f"诊断完成")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    main()
