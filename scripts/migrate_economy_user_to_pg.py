#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
将 SQLite 中的类脑币经济系统和用户相关表迁移到 ParadeDB。
优化版本：预加载已有 ID 到 set，批量插入，关闭引擎日志。
"""

import asyncio
import sys
import os
import logging
import aiosqlite
from datetime import datetime, timezone
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from sqlalchemy import select, text, func  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402
from src.database.database import AsyncSessionLocal, engine  # noqa: E402

engine.echo = False
from src.database.models import (  # noqa: E402
    UserAffection,
    UserWarningRecord,
    UserCoins,
    CoinTransaction,
    CoinLoan,
    InteractionLog,
)
from sqlalchemy.engine import CursorResult  # noqa: E402

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

TOTAL_STEPS = 7


@dataclass
class StepResult:
    source_table: str
    target_table: str
    source_count: int = 0
    migrated: int = 0
    skipped_existing: int = 0
    failed: int = 0
    skipped_no_table: bool = False
    error_msg: str = ""


migration_results: list[StepResult] = []


def to_naive_utc(dt):
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def get_sqlite_path():
    env_path = os.getenv("CHAT_DATABASE_PATH", "")
    if env_path and os.path.exists(env_path):
        return env_path
    default = os.path.join(_PROJECT_ROOT, "data", "chat.db")
    if os.path.exists(default):
        return default
    return None


async def _load_existing(session, model, *unique_cols) -> set:
    cols = [getattr(model, c) for c in unique_cols]
    result = await session.execute(select(*cols))
    if len(unique_cols) == 1:
        return {row[0] for row in result}
    return {tuple(row) for row in result}


async def _bulk_insert(session, model, rows: list[dict], batch_size=3000):
    col_count = len(rows[0]) if rows else 1
    safe_batch = max(1, min(batch_size, 32000 // col_count))
    total = 0
    for i in range(0, len(rows), safe_batch):
        batch = rows[i : i + safe_batch]
        stmt = pg_insert(model.__table__).values(batch).on_conflict_do_nothing()
        result: CursorResult = await session.execute(stmt)
        total += result.rowcount
        await session.commit()
    return total


async def migrate_user_affection(db):
    r = StepResult("ai_affection", "user.user_affection")
    migration_results.append(r)
    print(f"[1/{TOTAL_STEPS}] user_affection ...", end=" ", flush=True)

    try:
        async with AsyncSessionLocal() as session:
            cursor = await db.execute("SELECT COUNT(*) FROM ai_affection")
            r.source_count = (await cursor.fetchone())[0]
            if r.source_count == 0:
                print("跳过(无数据)")
                return

            existing = await _load_existing(session, UserAffection, "user_id")

            cursor = await db.execute(
                "SELECT user_id, affection_points, daily_affection_gain, "
                "last_update_date, last_interaction_date, last_gift_date FROM ai_affection"
            )
            rows = await cursor.fetchall()

            to_insert = []
            for row in rows:
                uid, points, daily_gain, last_update, last_interact, last_gift = row
                uid_str = str(uid)
                if uid_str in existing:
                    r.skipped_existing += 1
                    continue
                to_insert.append(
                    {
                        "user_id": uid_str,
                        "affection_points": points or 0,
                        "daily_affection_gain": daily_gain or 0,
                        "last_update_date": last_update,
                        "last_interaction_date": last_interact,
                        "last_gift_date": last_gift,
                    }
                )

            r.migrated = await _bulk_insert(session, UserAffection, to_insert)
            print(f"完成({r.migrated}/{r.source_count})")
    except Exception as e:
        r.failed = r.source_count - r.migrated - r.skipped_existing
        r.error_msg = str(e)
        print(f"失败({e})")


async def migrate_user_warnings(db):
    r = StepResult("user_warnings", "user.user_warnings")
    migration_results.append(r)
    print(f"[2/{TOTAL_STEPS}] user_warnings ...", end=" ", flush=True)

    try:
        async with AsyncSessionLocal() as session:
            cursor = await db.execute("SELECT COUNT(*) FROM user_warnings")
            r.source_count = (await cursor.fetchone())[0]
            if r.source_count == 0:
                print("跳过(无数据)")
                return

            existing = await _load_existing(
                session, UserWarningRecord, "user_id", "guild_id"
            )

            cursor = await db.execute(
                "SELECT user_id, guild_id, warning_count FROM user_warnings"
            )
            rows = await cursor.fetchall()

            to_insert = []
            for row in rows:
                uid, gid, count = row
                key = (str(uid), str(gid))
                if key in existing:
                    r.skipped_existing += 1
                    continue
                to_insert.append(
                    {
                        "user_id": key[0],
                        "guild_id": key[1],
                        "warning_count": count or 0,
                    }
                )

            r.migrated = await _bulk_insert(session, UserWarningRecord, to_insert)
            print(f"完成({r.migrated}/{r.source_count})")
    except Exception as e:
        r.failed = r.source_count - r.migrated - r.skipped_existing
        r.error_msg = str(e)
        print(f"失败({e})")


async def migrate_user_coins(db):
    r = StepResult("user_coins", "economy.user_coins")
    migration_results.append(r)
    print(f"[3/{TOTAL_STEPS}] user_coins ...", end=" ", flush=True)

    try:
        async with AsyncSessionLocal() as session:
            cursor = await db.execute("SELECT COUNT(*) FROM user_coins")
            r.source_count = (await cursor.fetchone())[0]
            if r.source_count == 0:
                print("跳过(无数据)")
                return

            existing = await _load_existing(session, UserCoins, "user_id")

            cursor = await db.execute(
                "SELECT user_id, balance, last_daily_message_date, last_red_envelope_date, "
                "coffee_effect_expires_at, has_withered_sunflower, blocks_thread_replies, "
                "thread_cooldown_seconds, thread_cooldown_duration, thread_cooldown_limit "
                "FROM user_coins"
            )
            rows = await cursor.fetchall()

            to_insert = []
            for row in rows:
                (
                    uid,
                    balance,
                    last_daily,
                    last_red,
                    coffee_expires,
                    withered,
                    blocks,
                    cd_seconds,
                    cd_duration,
                    cd_limit,
                ) = row
                uid_str = str(uid)
                if uid_str in existing:
                    r.skipped_existing += 1
                    continue
                to_insert.append(
                    {
                        "user_id": uid_str,
                        "balance": balance or 0,
                        "last_daily_message_date": last_daily,
                        "last_red_envelope_date": last_red,
                        "coffee_effect_expires_at": to_naive_utc(coffee_expires),
                        "has_withered_sunflower": withered,
                        "blocks_thread_replies": blocks or 0,
                        "thread_cooldown_seconds": cd_seconds,
                        "thread_cooldown_duration": cd_duration,
                        "thread_cooldown_limit": cd_limit,
                    }
                )

            r.migrated = await _bulk_insert(session, UserCoins, to_insert)
            print(f"完成({r.migrated}/{r.source_count})")
    except Exception as e:
        r.failed = r.source_count - r.migrated - r.skipped_existing
        r.error_msg = str(e)
        print(f"失败({e})")


async def ensure_column_types():
    async with AsyncSessionLocal() as session:
        await session.execute(
            text(
                "ALTER TABLE economy.coin_transactions ALTER COLUMN amount TYPE BIGINT"
            )
        )
        await session.commit()
    print("[准备] coin_transactions.amount → BIGINT")


async def migrate_coin_transactions(db):
    r = StepResult("coin_transactions", "economy.coin_transactions")
    migration_results.append(r)
    print(f"[4/{TOTAL_STEPS}] coin_transactions ...", end=" ", flush=True)

    try:
        await ensure_column_types()

        cursor = await db.execute("SELECT COUNT(*) FROM coin_transactions")
        r.source_count = (await cursor.fetchone())[0]
        if r.source_count == 0:
            print("跳过(无数据)")
            return

        async with AsyncSessionLocal() as session:
            pg_count = await session.execute(
                select(func.count()).select_from(CoinTransaction)
            )
            already_in_pg = pg_count.scalar() or 0
            if already_in_pg >= r.source_count:
                r.skipped_existing = already_in_pg
                print(f"跳过(已存在 {already_in_pg} 条)")
                return
            offset = 0

        batch_size = 1000

        while True:
            cursor = await db.execute(
                "SELECT user_id, amount, reason, timestamp FROM coin_transactions "
                f"LIMIT {batch_size} OFFSET {offset}"
            )
            rows = await cursor.fetchall()
            if not rows:
                break

            batch = []
            for uid, amount, reason, ts in rows:
                try:
                    batch.append(
                        {
                            "user_id": str(uid),
                            "amount": int(amount),
                            "reason": reason or "",
                            "timestamp": to_naive_utc(ts) or datetime.utcnow(),
                        }
                    )
                except Exception:
                    r.failed += 1

            async with AsyncSessionLocal() as session:
                stmt = (
                    pg_insert(CoinTransaction.__table__)
                    .values(batch)
                    .on_conflict_do_nothing()
                )
                await session.execute(stmt)
                await session.commit()
            r.migrated += len(batch) - (len(rows) - len(batch))
            offset += batch_size

            pct = min(offset, r.source_count) / r.source_count * 100
            print(
                f"\r[4/{TOTAL_STEPS}] coin_transactions ... {pct:.0f}% ({min(offset, r.source_count)}/{r.source_count})",
                end="",
                flush=True,
            )

        print(
            f"\r[4/{TOTAL_STEPS}] coin_transactions ... 完成({r.migrated}/{r.source_count})"
        )
    except Exception as e:
        r.failed = r.source_count - r.migrated - r.skipped_existing
        r.error_msg = str(e)
        print(f"失败({e})")


async def migrate_coin_loans(db):
    r = StepResult("coin_loans", "economy.coin_loans")
    migration_results.append(r)
    print(f"[5/{TOTAL_STEPS}] coin_loans ...", end=" ", flush=True)

    try:
        async with AsyncSessionLocal() as session:
            cursor = await db.execute("SELECT COUNT(*) FROM coin_loans")
            r.source_count = (await cursor.fetchone())[0]
            if r.source_count == 0:
                print("跳过(无数据)")
                return

            cursor = await db.execute(
                "SELECT user_id, amount, status, created_at, paid_at FROM coin_loans"
            )
            rows = await cursor.fetchall()

            to_insert = []
            for uid, amount, status, created, paid in rows:
                to_insert.append(
                    {
                        "user_id": str(uid),
                        "amount": amount,
                        "status": status or "active",
                        "created_at": to_naive_utc(created) or datetime.utcnow(),
                        "paid_at": to_naive_utc(paid),
                    }
                )

            r.migrated = await _bulk_insert(session, CoinLoan, to_insert)
            print(f"完成({r.migrated}/{r.source_count})")
    except Exception as e:
        r.failed = r.source_count - r.migrated - r.skipped_existing
        r.error_msg = str(e)
        print(f"失败({e})")


async def migrate_feeding_logs(db):
    r = StepResult("feeding_log", "economy.interaction_logs[feeding]")
    migration_results.append(r)
    print(f"[6/{TOTAL_STEPS}] feeding_logs ...", end=" ", flush=True)

    try:
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM feeding_log")
            r.source_count = (await cursor.fetchone())[0]
        except Exception:
            r.skipped_no_table = True
            print("跳过(表不存在)")
            return

        if r.source_count == 0:
            print("跳过(无数据)")
            return

        batch_size = 10000
        offset = 0

        async with AsyncSessionLocal() as session:
            while True:
                cursor = await db.execute(
                    f"SELECT user_id, timestamp FROM feeding_log LIMIT {batch_size} OFFSET {offset}"
                )
                rows = await cursor.fetchall()
                if not rows:
                    break

                batch = []
                for uid, ts in rows:
                    batch.append(
                        {
                            "user_id": str(uid),
                            "interaction_type": "feeding",
                            "timestamp": to_naive_utc(ts) or datetime.utcnow(),
                        }
                    )

                stmt = (
                    pg_insert(InteractionLog.__table__)
                    .values(batch)
                    .on_conflict_do_nothing()
                )
                await session.execute(stmt)
                r.migrated += len(batch)
                await session.commit()
                offset += batch_size

        print(f"完成({r.migrated}/{r.source_count})")
    except Exception as e:
        r.failed = r.source_count - r.migrated - r.skipped_existing
        r.error_msg = str(e)
        print(f"失败({e})")


async def migrate_confession_logs(db):
    r = StepResult("confession_log", "economy.interaction_logs[confession]")
    migration_results.append(r)
    print(f"[7/{TOTAL_STEPS}] confession_logs ...", end=" ", flush=True)

    try:
        try:
            cursor = await db.execute("SELECT COUNT(*) FROM confession_log")
            r.source_count = (await cursor.fetchone())[0]
        except Exception:
            r.skipped_no_table = True
            print("跳过(表不存在)")
            return

        if r.source_count == 0:
            print("跳过(无数据)")
            return

        batch_size = 10000
        offset = 0

        async with AsyncSessionLocal() as session:
            while True:
                cursor = await db.execute(
                    f"SELECT user_id, timestamp FROM confession_log LIMIT {batch_size} OFFSET {offset}"
                )
                rows = await cursor.fetchall()
                if not rows:
                    break

                batch = []
                for uid, ts in rows:
                    batch.append(
                        {
                            "user_id": str(uid),
                            "interaction_type": "confession",
                            "timestamp": to_naive_utc(ts) or datetime.utcnow(),
                        }
                    )

                stmt = (
                    pg_insert(InteractionLog.__table__)
                    .values(batch)
                    .on_conflict_do_nothing()
                )
                await session.execute(stmt)
                r.migrated += len(batch)
                await session.commit()
                offset += batch_size

        print(f"完成({r.migrated}/{r.source_count})")
    except Exception as e:
        r.failed = r.source_count - r.migrated - r.skipped_existing
        r.error_msg = str(e)
        print(f"失败({e})")


def print_report():
    print("\n" + "=" * 72)
    print("  迁移报告")
    print("=" * 72)
    print(
        f"  {'步骤':<8} {'源表':<20} {'目标表':<35} {'源数':>6} {'迁移':>6} "
        f"{'跳过':>6} {'失败':>6} {'状态':<8}"
    )
    print("-" * 72)

    total_source = 0
    total_migrated = 0
    total_skipped = 0
    total_failed = 0

    for i, r in enumerate(migration_results, 1):
        total_source += r.source_count
        total_migrated += r.migrated
        total_skipped += r.skipped_existing
        total_failed += r.failed

        if r.skipped_no_table:
            status = "无表"
        elif r.source_count == 0:
            status = "空"
        elif r.error_msg:
            status = "失败"
        elif r.migrated + r.skipped_existing >= r.source_count:
            status = "OK"
        else:
            status = "部分"

        print(
            f"  [{i}/{TOTAL_STEPS}]   {r.source_table:<20} {r.target_table:<35} "
            f"{r.source_count:>6} {r.migrated:>6} {r.skipped_existing:>6} {r.failed:>6} {status:<8}"
        )

        if r.error_msg:
            err_short = r.error_msg[:100] + ("..." if len(r.error_msg) > 100 else "")
            print(f"          错误: {err_short}")

    print("-" * 72)
    print(
        f"  {'合计':<64} "
        f"{total_source:>6} {total_migrated:>6} {total_skipped:>6} {total_failed:>6}"
    )
    print("=" * 72)

    if total_failed > 0:
        print(f"\n  !! 有 {total_failed} 条记录迁移失败，请检查错误信息")
    else:
        print("\n  所有步骤已完成，无失败记录")


async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="迁移 economy + user 数据从 SQLite 到 ParadeDB"
    )
    parser.add_argument("--verify-only", action="store_true", help="仅验证数据一致性")
    parser.add_argument(
        "--skip-transactions",
        action="store_true",
        help="跳过大量数据的 coin_transactions 表",
    )
    args = parser.parse_args()

    sqlite_path = get_sqlite_path()
    if not sqlite_path:
        print("错误: 找不到 SQLite 数据库文件", file=sys.stderr)
        sys.exit(1)

    print(f"SQLite: {sqlite_path}")
    print("开始迁移...\n")

    if args.verify_only:
        migration_results.clear()
        async with aiosqlite.connect(sqlite_path) as db:
            await migrate_user_affection(db)
            await migrate_user_warnings(db)
            await migrate_user_coins(db)
            await migrate_coin_transactions(db)
            await migrate_coin_loans(db)
            await migrate_feeding_logs(db)
            await migrate_confession_logs(db)
        print_report()
        return

    async with aiosqlite.connect(sqlite_path) as db:
        await migrate_user_affection(db)
        await migrate_user_warnings(db)
        await migrate_user_coins(db)

        if not args.skip_transactions:
            await migrate_coin_transactions(db)
        else:
            r = StepResult("coin_transactions", "economy.coin_transactions")
            r.skipped_no_table = True
            migration_results.append(r)
            print(f"[4/{TOTAL_STEPS}] coin_transactions ... 跳过(--skip-transactions)")

        await migrate_coin_loans(db)
        await migrate_feeding_logs(db)
        await migrate_confession_logs(db)

    print_report()


if __name__ == "__main__":
    asyncio.run(main())
