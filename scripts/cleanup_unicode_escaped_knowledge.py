#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交互式脚本：检查和删除通用知识中包含Unicode转义序列的记录
"""

import asyncio
import sys
import os
import re
import codecs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.database.database import AsyncSessionLocal

# 检测Unicode转义序列的正则表达式
UNICODE_ESCAPE_PATTERN = re.compile(r"\\u[0-9a-fA-F]{4}")


def decode_unicode_escapes(text: str) -> str:
    """解码Unicode转义序列"""
    if not text:
        return text

    try:
        # 使用正则表达式替换所有\\uXXXX序列
        def replace_unicode_escape(match):
            hex_code = match.group(1)
            try:
                return chr(int(hex_code, 16))
            except:
                return match.group(0)

        decoded = re.sub(r"\\u([0-9a-fA-F]{4})", replace_unicode_escape, text)
        return decoded
    except Exception as e:
        # 如果解码失败，返回原始文本
        print(f"解码失败: {e}")
        return text


def has_unicode_escape(text: str) -> bool:
    """检查文本是否包含Unicode转义序列"""
    if not text:
        return False
    return bool(UNICODE_ESCAPE_PATTERN.search(text))


async def find_unicode_escaped_records():
    """查找包含Unicode转义序列的记录"""
    print("=== 查找包含Unicode转义序列的通用知识记录 ===\n")

    async with AsyncSessionLocal() as session:
        # 查找knowledge_documents中包含Unicode转义的记录
        result = await session.execute(
            text("""
                SELECT id, title, full_text
                FROM general_knowledge.knowledge_documents
                WHERE full_text LIKE '%\\u%'
                ORDER BY id
            """)
        )
        doc_rows = result.fetchall()

        # 查找knowledge_chunks中包含Unicode转义的记录
        result = await session.execute(
            text("""
                SELECT id, document_id, chunk_text
                FROM general_knowledge.knowledge_chunks
                WHERE chunk_text LIKE '%\\u%'
                ORDER BY id
            """)
        )
        chunk_rows = result.fetchall()

        return doc_rows, chunk_rows


async def get_all_records():
    """获取所有记录（用于检查和批量删除）"""
    async with AsyncSessionLocal() as session:
        # 获取所有knowledge_documents记录
        result = await session.execute(
            text("""
                SELECT id, title, full_text
                FROM general_knowledge.knowledge_documents
                ORDER BY id
            """)
        )
        doc_rows = result.fetchall()

        # 获取所有knowledge_chunks记录
        result = await session.execute(
            text("""
                SELECT id, document_id, chunk_text
                FROM general_knowledge.knowledge_chunks
                ORDER BY id
            """)
        )
        chunk_rows = result.fetchall()

        return doc_rows, chunk_rows


async def delete_records(record_ids: list, table_name: str):
    """删除指定的记录"""
    if not record_ids:
        print("没有需要删除的记录")
        return

    print(f"\n准备从 {table_name} 中删除 {len(record_ids)} 条记录...")
    print(f"删除的ID: {record_ids}")

    async with AsyncSessionLocal() as session:
        if table_name == "knowledge_documents":
            for record_id in record_ids:
                await session.execute(
                    text(
                        "DELETE FROM general_knowledge.knowledge_documents WHERE id = :id"
                    ),
                    {"id": record_id},
                )
        elif table_name == "knowledge_chunks":
            for record_id in record_ids:
                await session.execute(
                    text(
                        "DELETE FROM general_knowledge.knowledge_chunks WHERE id = :id"
                    ),
                    {"id": record_id},
                )

        await session.commit()
        print(f"✓ 已从 {table_name} 中删除 {len(record_ids)} 条记录")


async def interactive_cleanup():
    """交互式清理流程"""
    # 1. 查找包含Unicode转义的记录
    doc_rows, chunk_rows = await find_unicode_escaped_records()

    print(f"\n找到 {len(doc_rows)} 条包含Unicode转义的文档记录")
    print(f"找到 {len(chunk_rows)} 条包含Unicode转义的chunk记录\n")

    # 2. 显示文档记录
    if doc_rows:
        print("=== 文档记录 (knowledge_documents) ===")
        for i, row in enumerate(doc_rows, 1):
            print(f"\n[{i}] ID: {row[0]}")
            print(f"    Title: {row[1]}")
            # 显示原始内容（前200个字符）
            original_content = row[2][:200]
            print(f"    原始内容: {original_content}...")

        # 询问是否删除文档记录
        print("\n" + "=" * 60)
        print("由于Docker环境限制，无法使用交互式输入。")
        print("如需删除，请使用命令行参数：")
        print(
            "  docker exec Odysseia_Guidance python scripts/cleanup_unicode_escaped_knowledge.py --delete-docs <id1,id2,...>"
        )
        print(
            "  docker exec Odysseia_Guidance python scripts/cleanup_unicode_escaped_knowledge.py --delete-docs all"
        )
        print("或直接修改脚本中的delete_ids列表\n")

    # 3. 显示chunk记录
    if chunk_rows:
        print("\n\n=== Chunk记录 (knowledge_chunks) ===")
        for i, row in enumerate(chunk_rows, 1):
            print(f"\n[{i}] ID: {row[0]}, Document ID: {row[1]}")
            # 显示原始内容（前200个字符）
            original_content = row[2][:200]
            print(f"    原始内容: {original_content}...")

        # 询问是否删除chunk记录
        print("\n" + "=" * 60)
        print("由于Docker环境限制，无法使用交互式输入。")
        print("如需删除，请使用命令行参数：")
        print(
            "  docker exec Odysseia_Guidance python scripts/cleanup_unicode_escaped_knowledge.py --delete-chunks <id1,id2,...>"
        )
        print(
            "  docker exec Odysseia_Guidance python scripts/cleanup_unicode_escaped_knowledge.py --delete-chunks all"
        )
        print("或直接修改脚本中的delete_ids列表\n")

    print("\n=== 清理完成 ===")


async def main():
    """主函数"""
    # 解析命令行参数
    delete_docs = None
    delete_chunks = None
    keep_docs = None
    check_only = False

    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv[1:], 1):
            if arg == "--delete-docs" and i + 1 < len(sys.argv):
                next_arg = sys.argv[i + 1]
                if next_arg.lower() == "all":
                    delete_docs = "all"
                else:
                    try:
                        delete_docs = [
                            int(id_str.strip()) for id_str in next_arg.split(",")
                        ]
                    except ValueError:
                        print(f"错误：无效的ID格式: {next_arg}")
                        sys.exit(1)
            elif arg == "--delete-chunks" and i + 1 < len(sys.argv):
                next_arg = sys.argv[i + 1]
                if next_arg.lower() == "all":
                    delete_chunks = "all"
                else:
                    try:
                        delete_chunks = [
                            int(id_str.strip()) for id_str in next_arg.split(",")
                        ]
                    except ValueError:
                        print(f"错误：无效的ID格式: {next_arg}")
                        sys.exit(1)
            elif arg == "--keep-docs" and i + 1 < len(sys.argv):
                try:
                    keep_docs = [
                        int(id_str.strip()) for id_str in sys.argv[i + 1].split(",")
                    ]
                except ValueError:
                    print(f"错误：无效的ID格式: {sys.argv[i + 1]}")
                    sys.exit(1)
            elif arg == "--check":
                check_only = True

    print("通用知识Unicode转义清理工具\n")

    try:
        # 检查模式：显示所有记录
        if check_only:
            print("=== 检查所有通用知识记录 ===\n")
            doc_rows, chunk_rows = await get_all_records()

            print(f"共有 {len(doc_rows)} 条文档记录")
            print(f"共有 {len(chunk_rows)} 条chunk记录\n")

            if doc_rows:
                print("=== 文档记录列表 ===")
                for row in doc_rows:
                    print(f"  ID: {row[0]}, Title: {row[1]}")

            if chunk_rows:
                print("\n=== Chunk记录列表 ===")
                for row in chunk_rows:
                    print(f"  ID: {row[0]}, Document ID: {row[1]}")

            return

        # 保留模式：删除除指定ID外的所有记录
        if keep_docs is not None:
            print(f"=== 保留模式：保留ID {keep_docs}，删除其他所有文档记录 ===\n")
            doc_rows, chunk_rows = await get_all_records()

            # 计算需要删除的ID
            all_doc_ids = [row[0] for row in doc_rows]
            ids_to_delete = [
                doc_id for doc_id in all_doc_ids if doc_id not in keep_docs
            ]

            if ids_to_delete:
                print(f"将删除 {len(ids_to_delete)} 条记录: {ids_to_delete}")
                await delete_records(ids_to_delete, "knowledge_documents")
            else:
                print("没有需要删除的记录")

            return

        # 删除模式：删除指定的记录
        if delete_docs is not None or delete_chunks is not None:
            print("此工具将查找包含Unicode转义序列的记录\n")
            doc_rows, chunk_rows = await find_unicode_escaped_records()

            # 先删除chunk（因为外键约束，必须先删除子表）
            if delete_chunks is not None:
                if delete_chunks == "all":
                    await delete_records(
                        [row[0] for row in chunk_rows], "knowledge_chunks"
                    )
                else:
                    await delete_records(delete_chunks, "knowledge_chunks")

            # 再删除文档
            if delete_docs is not None:
                if delete_docs == "all":
                    await delete_records(
                        [row[0] for row in doc_rows], "knowledge_documents"
                    )
                else:
                    await delete_records(delete_docs, "knowledge_documents")
        else:
            # 否则显示交互式界面
            print("此工具将查找包含Unicode转义序列的记录，并显示原始内容\n")
            await interactive_cleanup()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
