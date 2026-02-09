#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将 shop_config.py 中的商品数据迁移到 PostgreSQL 的 shop.shop_items 表。
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.database.database import AsyncSessionLocal
from src.database.models import ShopItem
from src.chat.config.shop_config import SHOP_ITEMS


async def migrate_shop_items():
    """将商品数据从配置迁移到 PostgreSQL。"""

    print("开始迁移商店商品数据...")

    # 统计信息
    total_items = len(SHOP_ITEMS)
    success_count = 0
    skip_count = 0

    async with AsyncSessionLocal() as session:
        for item_data in SHOP_ITEMS:
            # 解包商品数据
            # 格式: (name, description, price, category, target, effect_id)
            name, description, price, category, target, effect_id = item_data

            # 检查商品是否已存在
            existing_item = await session.execute(
                select(ShopItem).where(ShopItem.name == name)
            )
            existing = existing_item.scalar_one_or_none()

            if existing:
                print(f"  [跳过] 商品 '{name}' 已存在")
                skip_count += 1
                continue

            # 创建新商品
            new_item = ShopItem(
                name=name,
                description=description,
                price=price,
                category=category,
                target=target,
                effect_id=effect_id,
                cg_url=None,  # CG图片URL暂时为空，后续手动添加
                is_available=1,
            )

            session.add(new_item)
            print(f"  [添加] 商品 '{name}' (价格: {price}, 类别: {category})")
            success_count += 1

        # 提交所有更改
        await session.commit()
        print("\n迁移完成！")
        print(f"  总商品数: {total_items}")
        print(f"  成功添加: {success_count}")
        print(f"  跳过已存在: {skip_count}")


async def main():
    """主函数。"""
    try:
        await migrate_shop_items()
    except Exception as e:
        print(f"迁移失败: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
