#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将 shop_config.py 中的商品数据迁移到 PostgreSQL 的 shop.shop_items 表。
支持更新商品的 cg_url 字段。
"""

import asyncio
import sys
import os
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database.database import AsyncSessionLocal
from src.database.models import ShopItem
from src.chat.config.shop_config import SHOP_ITEMS, BRAIN_GIRL_EATING_IMAGES


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

            # 从 BRAIN_GIRL_EATING_IMAGES 获取 cg_url
            cg_url = BRAIN_GIRL_EATING_IMAGES.get(name)

            # 创建新商品
            new_item = ShopItem(
                name=name,
                description=description,
                price=price,
                category=category,
                target=target,
                effect_id=effect_id,
                cg_url=cg_url,
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


async def update_existing_cg_urls():
    """更新已存在商品的 cg_url 字段"""

    print("开始更新已存在商品的 cg_url 字段...")

    success_count = 0
    not_found_count = 0

    async with AsyncSessionLocal() as session:
        for name, cg_url in BRAIN_GIRL_EATING_IMAGES.items():
            # 查找商品
            result = await session.execute(
                select(ShopItem).where(ShopItem.name == name)
            )
            item = result.scalar_one_or_none()

            if item:
                # 更新 cg_url
                item.cg_url = cg_url
                print(f"  [更新] 商品 '{name}' -> {cg_url}")
                success_count += 1
            else:
                print(f"  [未找到] 商品 '{name}' 不存在")
                not_found_count += 1

        # 提交所有更改
        await session.commit()

    print("\n更新完成！")
    print(f"  成功更新: {success_count}")
    print(f"  未找到: {not_found_count}")


async def main():
    """主函数。"""
    parser = argparse.ArgumentParser(description="迁移商店商品数据或更新 cg_url")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="更新已存在商品的 cg_url 字段（从 BRAIN_GIRL_EATING_IMAGES 读取）",
    )

    args = parser.parse_args()

    try:
        if args.update_existing:
            # 更新已存在商品的 cg_url
            await update_existing_cg_urls()
        else:
            # 迁移商品数据
            await migrate_shop_items()
    except Exception as e:
        print(f"操作失败: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
