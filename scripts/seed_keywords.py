#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将硬编码的关键词 (CONTENT_FILTER_BASE_KEYWORDS) 和 SQLite 中已有的自定义关键词
迁移到 PostgreSQL 的 content_filter.content_filter_keywords 表。
幂等：ON CONFLICT DO NOTHING，可重复运行。
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.database.database import AsyncSessionLocal
from src.database.models import ContentFilterKeyword
from src.chat.config.chat_config import CONTENT_FILTER_BASE_KEYWORDS
from src.chat.utils.database import chat_db_manager


async def seed():
    print("=" * 60)
    print("关键词种子脚本：迁移到 PostgreSQL")
    print("=" * 60)

    all_keywords = set()

    # 1. 硬编码关键词
    for kw in CONTENT_FILTER_BASE_KEYWORDS:
        all_keywords.add(kw.strip().lower())
    print(f"\n[1] 硬编码关键词: {len(CONTENT_FILTER_BASE_KEYWORDS)} 个")

    # 2. SQLite 中已有的自定义关键词
    try:
        await chat_db_manager.init_async()
        raw = await chat_db_manager.get_global_setting("content_filter_keywords")
        if raw:
            custom = json.loads(raw)
            before = len(all_keywords)
            for kw in custom:
                all_keywords.add(kw.strip().lower())
            print(f"[2] SQLite 自定义关键词: {len(custom)} 个 (去重后新增 {len(all_keywords) - before} 个)")
        else:
            print("[2] SQLite 自定义关键词: 无")
    except Exception as e:
        print(f"[2] 读取 SQLite 失败 (跳过): {e}")

    # 3. 批量写入 PG
    print(f"\n合计去重后关键词: {len(all_keywords)} 个")
    print("开始写入 PostgreSQL...")

    async with AsyncSessionLocal() as session:
        inserted = 0
        skipped = 0
        for kw in sorted(all_keywords):
            exists = await session.execute(
                select(ContentFilterKeyword).where(
                    ContentFilterKeyword.keyword == kw
                )
            )
            if exists.scalar_one_or_none():
                skipped += 1
                continue

            session.add(ContentFilterKeyword(keyword=kw, is_ignored=0))
            inserted += 1

        await session.commit()

    print(f"\n完成！新增: {inserted} 个, 已存在跳过: {skipped} 个")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
