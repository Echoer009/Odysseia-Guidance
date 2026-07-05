# -*- coding: utf-8 -*-
"""
用户好感度管理脚本。

把某个用户的好感度直接设置为指定数值，或增减、查询。
默认 dry-run（只预览），加 --execute 才会真正写库。

表：user.user_affection
字段：user_id(str)、affection_points(int)、daily_affection_gain、
      last_update_date、last_interaction_date、last_gift_date

用法：
    # 1) 查询某用户当前好感度
    python -m scripts.manage_user_affection show --user 123456789

    # 2) 把好感度设为指定数值（先 dry-run 预览）
    python -m scripts.manage_user_affection set --user 123456789 --points 80
    python -m scripts.manage_user_affection set --user 123456789 --points 80 --execute

    # 3) 在当前基础上增减（可正可负）
    python -m scripts.manage_user_affection add --user 123456789 --delta 10
    python -m scripts.manage_user_affection add --user 123456789 --delta -5 --execute
"""

import argparse
import asyncio
import os
import sys

import yaml

# 确保能导入项目模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from sqlalchemy import select

from src.database.database import AsyncSessionLocal
from src.database.models import UserAffection

load_dotenv()

AFFECTION_LEVELS_PATH = os.path.join(
    "src", "chat", "features", "affection", "data", "affection_levels.yml"
)


def load_affection_levels() -> list:
    try:
        with open(AFFECTION_LEVELS_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or []
    except FileNotFoundError:
        print(f"⚠️ 好感度等级配置文件 {AFFECTION_LEVELS_PATH} 未找到，等级信息将不可用。")
        return []


def get_level_info(levels: list, points: int) -> dict | None:
    if not levels:
        return None
    sorted_levels = sorted(levels, key=lambda x: x["min_affection"])
    for level in reversed(sorted_levels):
        if points >= level["min_affection"]:
            return level
    return sorted_levels[0]


def print_status(user_id: str, points: int, daily_gain: int | None, levels: list):
    info = get_level_info(levels, points)
    level_name = info["level_name"] if info else "?"
    level_id = info["id"] if info else "?"
    print(f"  用户ID:      {user_id}")
    print(f"  好感度点数:  {points}")
    print(f"  好感度等级:  {level_name}（{level_id}）")
    if daily_gain is not None:
        print(f"  今日已获:    {daily_gain}")


# ---------------------------------------------------------------------------
# 1. 查询
# ---------------------------------------------------------------------------
async def show(user_id: int):
    uid = str(user_id)
    levels = load_affection_levels()
    print(f"\n🔍 查询用户 {uid} 的好感度\n")
    async with AsyncSessionLocal() as session:
        record = (
            await session.execute(
                select(UserAffection).where(UserAffection.user_id == uid)
            )
        ).scalar_one_or_none()

        if not record:
            print("（该用户尚无好感度记录）")
            return

        print_status(record.user_id, record.affection_points, record.daily_affection_gain, levels)


# ---------------------------------------------------------------------------
# 2. 设置为绝对值
# ---------------------------------------------------------------------------
async def set_points(user_id: int, points: int, execute: bool):
    uid = str(user_id)
    levels = load_affection_levels()
    mode = "🔧 执行" if execute else "👁️ DRY-RUN（未写库，加 --execute 真正执行）"
    print(f"\n{mode}：把用户 {uid} 的好感度设为 {points}\n")

    # --- 预览（只读，独立 session）---
    async with AsyncSessionLocal() as session:
        record = (
            await session.execute(
                select(UserAffection).where(UserAffection.user_id == uid)
            )
        ).scalar_one_or_none()

        if record:
            old_points = record.affection_points
            print("【修改前】")
            print_status(uid, old_points, record.daily_affection_gain, levels)
            print("\n【修改后】")
            print_status(uid, points, record.daily_affection_gain, levels)
            delta = points - old_points
            sign = "+" if delta >= 0 else ""
            print(f"\n  变化量:      {sign}{delta}")
        else:
            print("（该用户尚无好感度记录，将新建一条记录）")
            print("\n【将创建】")
            print_status(uid, points, 0, levels)

        if not execute:
            print("\n（这是预览。确认无误后加 --execute 真正写入。）")
            return

    # --- 执行（新 session，写操作整体放在 begin 事务内）---
    async with AsyncSessionLocal() as session:
        async with session.begin():
            record = (
                await session.execute(
                    select(UserAffection)
                    .where(UserAffection.user_id == uid)
                    .with_for_update()
                )
            ).scalar_one_or_none()

            if record:
                record.affection_points = points
            else:
                session.add(
                    UserAffection(
                        user_id=uid,
                        affection_points=points,
                        daily_affection_gain=0,
                        last_update_date=None,
                        last_interaction_date=None,
                        last_gift_date=None,
                    )
                )
        print(f"\n✅ 已将用户 {uid} 的好感度设为 {points}")


# ---------------------------------------------------------------------------
# 3. 增减
# ---------------------------------------------------------------------------
async def add_points(user_id: int, delta: int, execute: bool):
    uid = str(user_id)
    levels = load_affection_levels()
    mode = "🔧 执行" if execute else "👁️ DRY-RUN（未写库，加 --execute 真正执行）"
    sign = "+" if delta >= 0 else ""
    print(f"\n{mode}：用户 {uid} 的好感度 {sign}{delta}\n")

    # --- 预览 ---
    async with AsyncSessionLocal() as session:
        record = (
            await session.execute(
                select(UserAffection).where(UserAffection.user_id == uid)
            )
        ).scalar_one_or_none()

        if record:
            old_points = record.affection_points
            new_points = old_points + delta
            print("【修改前】")
            print_status(uid, old_points, record.daily_affection_gain, levels)
            print("\n【修改后】")
            print_status(uid, new_points, record.daily_affection_gain, levels)
        else:
            new_points = delta
            print("（该用户尚无好感度记录，将新建一条记录）")
            print("\n【将创建】")
            print_status(uid, new_points, 0, levels)

        if not execute:
            print("\n（这是预览。确认无误后加 --execute 真正写入。）")
            return

    # --- 执行 ---
    async with AsyncSessionLocal() as session:
        async with session.begin():
            record = (
                await session.execute(
                    select(UserAffection)
                    .where(UserAffection.user_id == uid)
                    .with_for_update()
                )
            ).scalar_one_or_none()

            if record:
                record.affection_points = record.affection_points + delta
            else:
                session.add(
                    UserAffection(
                        user_id=uid,
                        affection_points=delta,
                        daily_affection_gain=0,
                        last_update_date=None,
                        last_interaction_date=None,
                        last_gift_date=None,
                    )
                )
        print(f"\n✅ 已为用户 {uid} 的好感度 {sign}{delta}，现为 {new_points}")


def main():
    parser = argparse.ArgumentParser(
        description="用户好感度管理（默认 dry-run，写库需 --execute）。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_show = sub.add_parser("show", help="查询某用户当前好感度")
    p_show.add_argument("--user", type=int, required=True, help="用户 ID")

    p_set = sub.add_parser("set", help="把好感度设为指定数值（绝对值）")
    p_set.add_argument("--user", type=int, required=True, help="用户 ID")
    p_set.add_argument("--points", type=int, required=True, help="目标好感度点数（例如 80）")
    p_set.add_argument("--execute", action="store_true", help="真正写库（默认 dry-run）")

    p_add = sub.add_parser("add", help="在当前好感度基础上增减")
    p_add.add_argument("--user", type=int, required=True, help="用户 ID")
    p_add.add_argument("--delta", type=int, required=True, help="增减量（可正可负，例如 10 或 -5）")
    p_add.add_argument("--execute", action="store_true", help="真正写库（默认 dry-run）")

    args = parser.parse_args()

    if args.command == "show":
        asyncio.run(show(args.user))
    elif args.command == "set":
        asyncio.run(set_points(args.user, args.points, args.execute))
    elif args.command == "add":
        asyncio.run(add_points(args.user, args.delta, args.execute))


if __name__ == "__main__":
    main()
