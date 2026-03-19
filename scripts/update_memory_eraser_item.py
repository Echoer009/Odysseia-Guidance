#!/usr/bin/env python3
"""
更新"黑衣人的记忆消除器"商品的effect_id
从 'clear_personal_memory' 更新为 'manage_conversation_blocks'

这样购买后会显示对话块管理面板，而不是直接清除所有记忆。
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import update
from src.database.database import AsyncSessionLocal
from src.database.models import ShopItem
from src.chat.features.odysseia_coin.service.coin_service import (
    CLEAR_PERSONAL_MEMORY_ITEM_EFFECT_ID,
    MANAGE_CONVERSATION_BLOCKS_EFFECT_ID,
)


async def update_memory_eraser_item():
    """更新黑衣人的记忆消除器商品的effect_id"""
    async with AsyncSessionLocal() as session:
        # 查找商品
        from sqlalchemy import select

        result = await session.execute(
            select(ShopItem).where(ShopItem.name == "黑衣人的记忆消除器")
        )
        item = result.scalar_one_or_none()

        if not item:
            print("❌ 未找到商品 '黑衣人的记忆消除器'")
            return False

        print(f"找到商品:")
        print(f"  ID: {item.id}")
        print(f"  名称: {item.name}")
        print(f"  当前 effect_id: {item.effect_id}")
        print(f"  价格: {item.price}")

        if item.effect_id == MANAGE_CONVERSATION_BLOCKS_EFFECT_ID:
            print("✅ 商品已经是正确的 effect_id，无需更新")
            return True

        # 更新 effect_id
        item.effect_id = MANAGE_CONVERSATION_BLOCKS_EFFECT_ID
        await session.commit()

        print(f"\n✅ 已更新 effect_id 为: {MANAGE_CONVERSATION_BLOCKS_EFFECT_ID}")
        print("现在购买该商品后会显示对话块管理面板，而不是直接清除记忆")
        return True


async def main():
    print("=" * 50)
    print("更新 '黑衣人的记忆消除器' 商品配置")
    print("=" * 50)
    print()

    await update_memory_eraser_item()


if __name__ == "__main__":
    asyncio.run(main())
