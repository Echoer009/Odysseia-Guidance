# -*- coding: utf-8 -*-
"""
类脑娘的日记 - 数据采集 + 结构化构建。
采集逻辑与 scripts/diary_community_stats.py 共用本模块。
纯社区视角，不含个人数据，不出现任何模型名。
所有数字均来自数据库实时查询，不存在任何硬编码数值。
"""

import asyncio
from datetime import datetime, date, timezone, timedelta
from typing import Any, Optional

from sqlalchemy import select, func, case

from src.database.database import AsyncSessionLocal
from src.database.models import (
    CommunityMemberProfile,
    InteractionLog,
    ForumThread,
    CoinTransaction,
    CoinLoan,
    UserAffection,
)
from src.chat.utils.database import chat_db_manager
from src.config import BOT_NAME, CURRENCY_NAME
from src.diary.data.diary_script import DIARY_SCRIPT

# 类脑娘的生日：第一次能与人对话的日子
BOT_BIRTH_DATE = date(2025, 9, 14)

BEIJING_TZ = timezone(timedelta(hours=8))


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _fmt_dt(dt: Any) -> str:
    if not dt:
        return "无记录"
    if isinstance(dt, datetime):
        return dt.strftime("%Y年%m月%d日")
    return str(dt)


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _days_alive() -> int:
    return (date.today() - BOT_BIRTH_DATE).days


# ---------------------------------------------------------------------------
# 数据采集 (与原 CLI 脚本一致，全部实时取数)
# ---------------------------------------------------------------------------

async def collect_namecard_stats() -> dict:
    stats: dict = {"namecard_total": 0, "first_namecard_at": None}
    try:
        async with AsyncSessionLocal() as session:
            stats["namecard_total"] = (
                await session.execute(
                    select(func.count()).select_from(CommunityMemberProfile)
                )
            ).scalar() or 0
            stats["first_namecard_at"] = (
                await session.execute(
                    select(func.min(CommunityMemberProfile.created_at))
                )
            ).scalar()
    except Exception as e:
        stats["error"] = f"{e}"
    return stats


async def collect_interaction_stats() -> dict:
    stats: dict = {"feeding_count": 0, "confession_count": 0}
    try:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(InteractionLog.interaction_type, func.count()).group_by(
                        InteractionLog.interaction_type
                    )
                )
            ).all()
            for itype, cnt in rows:
                if itype == "feeding":
                    stats["feeding_count"] = cnt
                elif itype == "confession":
                    stats["confession_count"] = cnt
    except Exception as e:
        stats["error"] = f"{e}"
    return stats


async def collect_forum_stats() -> dict:
    stats: dict = {"thread_count": 0, "first_thread_at": None}
    try:
        async with AsyncSessionLocal() as session:
            stats["thread_count"] = (
                await session.execute(select(func.count()).select_from(ForumThread))
            ).scalar() or 0
            stats["first_thread_at"] = (
                await session.execute(select(func.min(ForumThread.created_at)))
            ).scalar()
    except Exception as e:
        stats["error"] = f"{e}"
    return stats


async def collect_coin_stats() -> dict:
    stats: dict = {
        "total_earned": 0,
        "total_spent": 0,
        "net_circulation": 0,
        "work_count": 0,
        "sell_body_count": 0,
        "blackjack_net": 0,
        "top_purchases": [],
    }
    try:
        async with AsyncSessionLocal() as session:
            earned_spent = (
                await session.execute(
                    select(
                        func.sum(
                            case(
                                (CoinTransaction.amount > 0, CoinTransaction.amount),
                                else_=0,
                            )
                        ),
                        func.sum(
                            case(
                                (
                                    CoinTransaction.amount < 0,
                                    func.abs(CoinTransaction.amount),
                                ),
                                else_=0,
                            )
                        ),
                    )
                )
            ).one()
            stats["total_earned"] = _safe_int(earned_spent[0])
            stats["total_spent"] = _safe_int(earned_spent[1])
            stats["net_circulation"] = stats["total_earned"] - stats["total_spent"]

            stats["work_count"] = (
                await session.execute(
                    select(func.count()).where(CoinTransaction.reason == "打工奖励")
                )
            ).scalar() or 0

            stats["sell_body_count"] = (
                await session.execute(
                    select(func.count()).where(CoinTransaction.reason == "卖屁股奖励")
                )
            ).scalar() or 0

            bj_net = (
                await session.execute(
                    select(func.sum(CoinTransaction.amount)).where(
                        CoinTransaction.reason.like("21点%")
                    )
                )
            ).scalar()
            stats["blackjack_net"] = _safe_int(bj_net)

            purchase_rows = (
                await session.execute(
                    select(CoinTransaction.reason, func.count().label("c"))
                    .where(CoinTransaction.reason.like("购买%"))
                    .group_by(CoinTransaction.reason)
                    .order_by(func.count().desc())
                    .limit(5)
                )
            ).all()
            stats["top_purchases"] = [(r.reason, r.c) for r in purchase_rows]
    except Exception as e:
        stats["error"] = f"{e}"
    return stats


async def collect_loan_stats() -> dict:
    stats: dict = {"active_loans": 0, "active_amount": 0, "repaid_loans": 0}
    try:
        async with AsyncSessionLocal() as session:
            rows = (
                await session.execute(
                    select(
                        CoinLoan.status, func.count(), func.sum(CoinLoan.amount)
                    ).group_by(CoinLoan.status)
                )
            ).all()
            for status, cnt, amt in rows:
                if status == "active":
                    stats["active_loans"] = _safe_int(cnt)
                    stats["active_amount"] = _safe_int(amt)
                else:
                    stats["repaid_loans"] += _safe_int(cnt)
    except Exception as e:
        stats["error"] = f"{e}"
    return stats


async def collect_affection_stats() -> dict:
    stats: dict = {"total_affection_points": 0}
    try:
        async with AsyncSessionLocal() as session:
            total = (
                await session.execute(select(func.sum(UserAffection.affection_points)))
            ).scalar()
            stats["total_affection_points"] = _safe_int(total)
    except Exception as e:
        stats["error"] = f"{e}"
    return stats


async def collect_tarot_stats() -> dict:
    stats: dict = {"tarot_total": 0}
    try:
        result = await chat_db_manager._execute(
            chat_db_manager._db_transaction,
            "SELECT SUM(tarot_reading_count) as total FROM daily_stats",
            fetch="one",
        )
        stats["tarot_total"] = _safe_int(result["total"]) if result else 0
    except Exception as e:
        stats["error"] = f"{e}"
    return stats


async def collect_reply_stats() -> dict:
    """仅统计总回复次数，不出现任何模型名"""
    stats: dict = {"total_replies": 0}
    try:
        total_row = await chat_db_manager._execute(
            chat_db_manager._db_transaction,
            "SELECT SUM(usage_count) as total FROM daily_model_usage",
            fetch="one",
        )
        stats["total_replies"] = _safe_int(total_row["total"]) if total_row else 0
    except Exception as e:
        stats["error"] = f"{e}"
    return stats


async def collect_all() -> dict:
    """并发采集所有维度，返回原始 stats 字典（供 CLI 打印和结构化构建共用）。"""
    await chat_db_manager.init_async()

    pg_tasks = {
        "namecard": collect_namecard_stats(),
        "interaction": collect_interaction_stats(),
        "forum": collect_forum_stats(),
        "coin": collect_coin_stats(),
        "loan": collect_loan_stats(),
        "affection": collect_affection_stats(),
    }
    sqlite_tasks = {
        "tarot": collect_tarot_stats(),
        "reply": collect_reply_stats(),
    }

    pg_keys = list(pg_tasks.keys())
    sqlite_keys = list(sqlite_tasks.keys())
    pg_results = await asyncio.gather(*[pg_tasks[k] for k in pg_keys])
    sqlite_results = await asyncio.gather(*[sqlite_tasks[k] for k in sqlite_keys])
    data = dict(zip(pg_keys, pg_results))
    data.update(dict(zip(sqlite_keys, sqlite_results)))
    return data


# ---------------------------------------------------------------------------
# 结构化构建 (供 Web 前端消费；所有数字由实时 stats 注入)
# 页面序列与文案在 src/diary/data/diary_script.py，本模块只做「注入数据」。
# ---------------------------------------------------------------------------

def _resolve_stat(key: str, d: dict, cur: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """根据 stat 键从原始 stats 字典解析出 (label, value, secondary)。所有数字取自 d。"""
    nc = d.get("namecard", {})
    inter = d.get("interaction", {})
    forum = d.get("forum", {})
    coin = d.get("coin", {})
    loan = d.get("loan", {})
    aff = d.get("affection", {})
    tarot = d.get("tarot", {})
    reply = d.get("reply", {})

    feeding = _safe_int(inter.get("feeding_count"))
    confession = _safe_int(inter.get("confession_count"))
    work = _safe_int(coin.get("work_count"))
    sell_body = _safe_int(coin.get("sell_body_count"))
    bj = _safe_int(coin.get("blackjack_net"))
    earned = _safe_int(coin.get("total_earned"))
    spent = _safe_int(coin.get("total_spent"))
    net = _safe_int(coin.get("net_circulation"))
    active_loans = _safe_int(loan.get("active_loans"))
    active_amount = _safe_int(loan.get("active_amount"))
    repaid_loans = _safe_int(loan.get("repaid_loans"))
    namecard_total = _safe_int(nc.get("namecard_total"))
    tarot_total = _safe_int(tarot.get("tarot_total"))
    thread_count = _safe_int(forum.get("thread_count"))
    replies = _safe_int(reply.get("total_replies"))
    affection = _safe_int(aff.get("total_affection_points"))

    if key == "feeding":
        return ("投喂与忏悔", f"被投喂 {feeding:,} 次", f"听忏悔 {confession:,} 次")
    if key == "work":
        return ("打工与卖屁股", f"打工 {work:,} 次", f"「卖屁股」{sell_body:,} 次")
    if key == "blackjack":
        if bj >= 0:
            return ("21点", f"你们赢走了 {bj:,} 枚{cur}", None)
        return ("21点", f"你们输给了我 {abs(bj):,} 枚{cur}", None)
    if key == "loan":
        return ("借款", f"还有 {active_loans} 笔没还（{active_amount:,} 枚{cur}）", f"已还清 {repaid_loans} 笔")
    if key == "coin":
        return (cur, f"发出 {earned:,} · 花掉 {spent:,}", f"还剩 {net:,} 枚")
    if key == "namecard":
        return ("名片", f"有 {namecard_total} 个人把名片交给了我", f"第一张是 {_fmt_dt(nc.get('first_namecard_at'))} 收到的")
    if key == "tarot":
        return ("塔罗", f"翻开了 {tarot_total:,} 次塔罗牌", None)
    if key == "forum":
        return ("论坛", f"论坛里有 {thread_count:,} 篇帖子", f"最早的一篇在 {_fmt_dt(forum.get('first_thread_at'))}")
    if key == "reply":
        return ("回复", f"我回复了你们 {replies:,} 次", None)
    if key == "affection":
        return ("好感度", f"好感度加起来有 {affection:,} 点", None)
    return (None, None, None)


def build_diary(d: dict) -> dict:
    """读页面脚本 + 注入实时数据，输出扁平的 entries 列表。所有数字均取自 d。"""
    cur = CURRENCY_NAME
    days = _days_alive()
    entries: list[dict] = []

    for page in DIARY_SCRIPT:
        entry: dict = {
            "type": page.get("type", "text"),
            "date": page.get("date", ""),
            "mood": page.get("mood", "normal"),
            "expression": page.get("expression", "normal"),
            "text": page.get("text", ""),
        }

        if entry["type"] == "stat":
            label, value, secondary = _resolve_stat(page.get("stat", ""), d, cur)
            if label is not None:
                entry["data_label"] = label
            if value is not None:
                entry["data_value"] = value
            if secondary is not None:
                entry["data_secondary"] = secondary
        elif entry["type"] == "gallery":
            entry["gallery_category"] = page.get("category", "food")
            entry["gallery_items"] = page.get("items", [])

        entries.append(entry)

    return {
        "bot_name": BOT_NAME,
        "currency_name": cur,
        "birth_date": BOT_BIRTH_DATE.isoformat(),
        "days_alive": days,
        "entries": entries,
    }


async def get_diary() -> dict:
    """采集 + 构建一步到位，供 API 调用。"""
    data = await collect_all()
    return build_diary(data)
