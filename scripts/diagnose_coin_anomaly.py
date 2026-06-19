# -*- coding: utf-8 -*-
"""
类脑币流水异常诊断与清理脚本。

数据模型说明（重要）：
- economy.user_coins.balance 是「当前余额」，独立存储，不是从流水累加得到的。
- 每次 add_coins / remove_coins 都会同时做两件事：
    ① 修改 user_coins.balance
    ② 插入一条 coin_transactions 流水（amount 带正负号）
- 因此删除一条异常流水时，必须同时把 balance 回滚 (balance -= tx.amount)，
  否则余额仍会偏高。本脚本默认 dry-run，必须加 --execute 才会真正写库。

用法：
    # 1) 诊断：列出 |amount| 最大的若干条流水，并标出超过阈值的异常项
    python -m scripts.diagnose_coin_anomaly diagnose
    python -m scripts.diagnose_coin_anomaly diagnose --threshold 500000 --limit 30
    python -m scripts.diagnose_coin_anomaly diagnose --user 123456789

    # 2) 删除单条流水（先 dry-run 预览，确认后加 --execute）
    python -m scripts.diagnose_coin_anomaly delete --id 12345
    python -m scripts.diagnose_coin_anomaly delete --id 12345 --execute

    # 3) 批量删除某用户 |amount| >= 阈值 的所有流水
    python -m scripts.diagnose_coin_anomaly delete-above --user 123456789 --min-amount 1000000
    python -m scripts.diagnose_coin_anomaly delete-above --user 123456789 --min-amount 1000000 --execute

    # 4) 校验：找出 balance 与 流水累加值 不一致的用户（定位受影响的人）
    python -m scripts.diagnose_coin_anomaly verify
"""

import argparse
import asyncio
import os
import sys
from collections import defaultdict

# 确保能导入项目模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from sqlalchemy import select, func, desc

from src.database.database import AsyncSessionLocal
from src.database.models import UserCoins, CoinTransaction

load_dotenv()


def fmt(n) -> str:
    """带千分位的整数格式化。"""
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n)


async def get_balance(session, user_id: str) -> int | None:
    result = await session.execute(
        select(UserCoins.balance).where(UserCoins.user_id == user_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# 1. 诊断
# ---------------------------------------------------------------------------
async def diagnose(threshold: int, limit: int, user_id: int | None):
    print(f"\n🔍 诊断类脑币流水异常（阈值 |amount| >= {fmt(threshold)}，取最大的 {limit} 条）\n")
    async with AsyncSessionLocal() as session:
        q = (
            select(CoinTransaction)
            .order_by(desc(func.abs(CoinTransaction.amount)))
            .limit(limit)
        )
        if user_id is not None:
            q = q.where(CoinTransaction.user_id == str(user_id))
            print(f"   （仅查用户 {user_id}）\n")
        rows = (await session.execute(q)).scalars().all()

        if not rows:
            print("（没有流水记录）")
            return

        print(f"{'ID':<12} {'用户ID':<20} {'金额':>16}  {'原因':<24} {'时间':<20} {'标记'}")
        print("-" * 110)
        anomaly_count = 0
        for tx in rows:
            is_anomaly = abs(tx.amount) >= threshold
            if is_anomaly:
                anomaly_count += 1
            mark = "‼️ 异常" if is_anomaly else ""
            ts = tx.timestamp.strftime("%Y-%m-%d %H:%M:%S") if tx.timestamp else "?"
            reason = (tx.reason or "")[:22]
            print(
                f"{tx.id:<12} {tx.user_id:<20} {fmt(tx.amount):>16}  {reason:<24} {ts:<20} {mark}"
            )

        # 汇总受影响用户的当前余额
        affected_users = {tx.user_id for tx in rows if abs(tx.amount) >= threshold}
        if affected_users:
            print("\n📈 异常项涉及用户的当前余额：")
            for uid in affected_users:
                bal = await get_balance(session, uid)
                print(f"   用户 {uid}: 余额 = {fmt(bal) if bal is not None else '（无 user_coins 记录）'}")
            print(f"\n共 {anomaly_count} 条异常流水，涉及 {len(affected_users)} 个用户。")
            print("👉 用 `delete --id <ID>` 逐条核对删除（先不加 --execute 预览）。")
        else:
            print(f"\n没有 |amount| >= {fmt(threshold)} 的异常流水。可调低 --threshold 再看。")


# ---------------------------------------------------------------------------
# 2. 删除单条流水 + 回滚余额
# ---------------------------------------------------------------------------
async def delete_one(tx_id: int, execute: bool):
    mode = "🔧 执行" if execute else "👁️ DRY-RUN（未写库，加 --execute 真正执行）"
    print(f"\n{mode}：删除流水 ID = {tx_id}\n")

    async with AsyncSessionLocal() as session:
        tx = await session.get(CoinTransaction, tx_id)
        if not tx:
            print(f"❌ 找不到 ID = {tx_id} 的流水。")
            return

        bal = await get_balance(session, tx.user_id)
        new_bal = (bal or 0) - tx.amount  # 回滚：减去该流水当初带来的影响

        ts = tx.timestamp.strftime("%Y-%m-%d %H:%M:%S") if tx.timestamp else "?"
        print(f"  流水 ID:   {tx.id}")
        print(f"  用户ID:    {tx.user_id}")
        print(f"  金额:      {fmt(tx.amount)}")
        print(f"  原因:      {tx.reason}")
        print(f"  时间:      {ts}")
        print(f"  当前余额:  {fmt(bal) if bal is not None else '（无 user_coins 记录）'}")
        print(f"  回滚后余额: {fmt(new_bal)}")
        if bal is None:
            print("  ⚠️ 该用户没有 user_coins 记录，无法回滚余额（仅删除流水）。")

        if not execute:
            print("\n（这是预览。确认无误后加 --execute 真正删除并回滚余额。）")
            return

        async with session.begin():
            # 重新在事务内锁定并读取，避免脏写
            tx = await session.get(CoinTransaction, tx_id)
            if not tx:
                print("❌ 事务内找不到该流水，可能已被删除，已取消。")
                return
            uc_row = (
                await session.execute(
                    select(UserCoins)
                    .where(UserCoins.user_id == tx.user_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if uc_row is None:
                print("⚠️ 该用户没有 user_coins 记录，仅删除流水，不调整余额。")
            else:
                uc_row.balance -= tx.amount
                print(f"✅ 已回滚余额：{fmt(uc_row.balance + tx.amount)} -> {fmt(uc_row.balance)}")
            await session.delete(tx)
        print(f"✅ 已删除流水 ID = {tx_id}")


# ---------------------------------------------------------------------------
# 3. 批量删除某用户 |amount| >= min_amount 的流水
# ---------------------------------------------------------------------------
async def delete_above(user_id: int, min_amount: int, execute: bool):
    mode = "🔧 执行" if execute else "👁️ DRY-RUN（未写库，加 --execute 真正执行）"
    print(f"\n{mode}：删除用户 {user_id} 所有 |amount| >= {fmt(min_amount)} 的流水\n")

    async with AsyncSessionLocal() as session:
        q = (
            select(CoinTransaction)
            .where(CoinTransaction.user_id == str(user_id))
            .where(func.abs(CoinTransaction.amount) >= min_amount)
            .order_by(desc(func.abs(CoinTransaction.amount)))
        )
        rows = (await session.execute(q)).scalars().all()

        if not rows:
            print("（没有符合条件的流水）")
            return

        total_amount = sum(tx.amount for tx in rows)
        bal = await get_balance(session, str(user_id))
        new_bal = (bal or 0) - total_amount

        print(f"  命中 {len(rows)} 条流水，合计金额 = {fmt(total_amount)}")
        print(f"  当前余额:   {fmt(bal) if bal is not None else '（无 user_coins 记录）'}")
        print(f"  回滚后余额: {fmt(new_bal)}\n")
        print(f"{'ID':<12} {'金额':>16}  {'原因':<24} {'时间'}")
        print("-" * 80)
        for tx in rows:
            ts = tx.timestamp.strftime("%Y-%m-%d %H:%M:%S") if tx.timestamp else "?"
            print(f"{tx.id:<12} {fmt(tx.amount):>16}  {(tx.reason or '')[:22]:<24} {ts}")

        if not execute:
            print("\n（这是预览。确认无误后加 --execute 真正删除并回滚余额。）")
            return

        async with session.begin():
            uc_row = (
                await session.execute(
                    select(UserCoins)
                    .where(UserCoins.user_id == str(user_id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if uc_row is None:
                print("⚠️ 该用户没有 user_coins 记录，仅删除流水，不调整余额。")
            else:
                before = uc_row.balance
                uc_row.balance -= total_amount
                print(f"✅ 已回滚余额：{fmt(before)} -> {fmt(uc_row.balance)}")
            for tx in rows:
                await session.delete(tx)
        print(f"✅ 已删除 {len(rows)} 条流水")


# ---------------------------------------------------------------------------
# 4. 校验 balance 与流水累加的一致性
# ---------------------------------------------------------------------------
async def verify(limit: int):
    print(f"\n🩺 校验 user_coins.balance 与 coin_transactions 累加值（显示差异最大的 {limit} 个用户）\n")
    async with AsyncSessionLocal() as session:
        sums = (
            await session.execute(
                select(
                    CoinTransaction.user_id,
                    func.sum(CoinTransaction.amount).label("total"),
                    func.count().label("cnt"),
                )
                .where(CoinTransaction.user_id.in_(
                    select(UserCoins.user_id)
                ))
                .group_by(CoinTransaction.user_id)
            )
        ).all()

        if not sums:
            print("（没有数据）")
            return

        diffs = []
        for uid, total, cnt in sums:
            bal = await get_balance(session, uid)
            b = bal or 0
            diff = b - int(total or 0)
            diffs.append((uid, b, int(total or 0), diff, int(cnt)))

        # 只看有不一致的，按 |diff| 降序
        mismatches = [d for d in diffs if d[3] != 0]
        mismatches.sort(key=lambda x: abs(x[3]), reverse=True)

        if not mismatches:
            print(f"✅ 全部 {len(diffs)} 个用户的余额与流水累加值一致，无异常。")
            return

        print(f"⚠️ 发现 {len(mismatches)} 个用户余额与流水累加不一致（共检查 {len(diffs)} 人）：\n")
        print(f"{'用户ID':<20} {'当前余额':>16} {'流水累加':>16} {'差额(余额-流水)':>18} {'流水数':>8}")
        print("-" * 90)
        for uid, bal, total, diff, cnt in mismatches[:limit]:
            print(f"{uid:<20} {fmt(bal):>16} {fmt(total):>16} {fmt(diff):>18} {fmt(cnt):>8}")
        print("\n差额为正 → 余额比流水多（可能曾被直接加余额 / 有流水被单独删过）。")
        print("差额为负 → 余额比流水少。结合 `diagnose` 找具体的大额流水。")


def main():
    parser = argparse.ArgumentParser(
        description="类脑币流水异常诊断与清理（默认 dry-run，删除需 --execute）。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_d = sub.add_parser("diagnose", help="列出金额异常大的流水")
    p_d.add_argument("--threshold", type=int, default=100000, help="异常阈值，|amount| 超过此值视为异常（默认 100000）")
    p_d.add_argument("--limit", type=int, default=30, help="最多显示多少条（默认 30）")
    p_d.add_argument("--user", type=int, default=None, help="只看指定用户")

    p_del = sub.add_parser("delete", help="删除单条流水并回滚余额")
    p_del.add_argument("--id", type=int, required=True, help="流水 ID")
    p_del.add_argument("--execute", action="store_true", help="真正写库（默认 dry-run）")

    p_da = sub.add_parser("delete-above", help="批量删除某用户 |amount|>=阈值 的流水")
    p_da.add_argument("--user", type=int, required=True, help="用户 ID")
    p_da.add_argument("--min-amount", type=int, required=True, help="|amount| 下限")
    p_da.add_argument("--execute", action="store_true", help="真正写库（默认 dry-run）")

    p_v = sub.add_parser("verify", help="校验余额与流水累加是否一致")
    p_v.add_argument("--limit", type=int, default=30, help="最多显示多少个不一致用户（默认 30）")

    args = parser.parse_args()

    if args.command == "diagnose":
        asyncio.run(diagnose(args.threshold, args.limit, args.user))
    elif args.command == "delete":
        asyncio.run(delete_one(args.id, args.execute))
    elif args.command == "delete-above":
        asyncio.run(delete_above(args.user, args.min_amount, args.execute))
    elif args.command == "verify":
        asyncio.run(verify(args.limit))


if __name__ == "__main__":
    main()
