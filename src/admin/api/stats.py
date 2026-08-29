import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import text

from src.admin.auth import require_admin
from src.chat.features.ab_test.services.ab_test_service import ab_test_service
from src.chat.utils.database import chat_db_manager
from src.database.database import AsyncSessionLocal

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])


async def _sqlite_exec(query: str, params: tuple = (), fetch: str = "none"):
    return await chat_db_manager._execute(
        chat_db_manager._db_transaction, query, params, fetch=fetch
    )


@router.get("/api/stats/daily")
async def get_daily_stats(days: int = 7):
    days = max(1, min(days, 90))
    models = [dict(row) for row in await chat_db_manager.get_model_usage_counts()]
    beijing_now = datetime.now(timezone(timedelta(hours=8)))
    cutoff = (beijing_now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    daily_rows = await _sqlite_exec(
        "SELECT model_name, usage_date, usage_count, provider_name FROM daily_model_usage WHERE usage_date >= ? ORDER BY usage_date DESC, usage_count DESC",
        (cutoff,),
        fetch="all",
    )
    daily = [dict(row) for row in daily_rows]
    window_total = sum(row["usage_count"] or 0 for row in daily)
    all_time_total = sum(row["usage_count"] or 0 for row in models)
    return {
        "days": days,
        "models": models,
        "daily": daily,
        "totals": {
            "window_calls": window_total,
            "all_time_calls": all_time_total,
        },
    }


@router.get("/api/stats/overview")
async def get_overview():
    experiments = await ab_test_service.list_experiments()
    active_experiment = next(
        (
            {"id": e.get("id"), "name": e.get("name")}
            for e in experiments
            if e.get("enabled")
        ),
        None,
    )
    blacklist_row = await _sqlite_exec(
        "SELECT (SELECT COUNT(*) FROM blacklisted_users WHERE expires_at > datetime('now')) + (SELECT COUNT(*) FROM globally_blacklisted_users WHERE expires_at > datetime('now')) AS c",
        fetch="one",
    )
    async with AsyncSessionLocal() as session:
        shop_items_count = (
            await session.execute(text("SELECT COUNT(*) FROM shop.shop_items"))
        ).scalar() or 0
        member_count = (
            await session.execute(text("SELECT COUNT(*) FROM community.member_profiles"))
        ).scalar() or 0
    return {
        "ab_experiments_count": len(experiments),
        "active_experiment": active_experiment,
        "shop_items_count": shop_items_count,
        "blacklist_count": blacklist_row["c"] if blacklist_row else 0,
        "member_count": member_count,
    }
