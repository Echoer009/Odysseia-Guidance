import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])

DEFAULT_BAN_MINUTES = 365 * 24 * 60
DEFAULT_MUTE_MINUTES = 60


async def _sqlite_exec(query: str, params: tuple = (), fetch: str = "none", commit: bool = False):
    return await chat_db_manager._execute(
        chat_db_manager._db_transaction, query, params, fetch=fetch, commit=commit
    )


class BlacklistAdd(BaseModel):
    user_id: int
    scope: str
    guild_id: Optional[int] = None
    reason: Optional[str] = None
    duration_minutes: Optional[int] = None


class MutedChannelAdd(BaseModel):
    channel_id: int
    duration_minutes: int = DEFAULT_MUTE_MINUTES


@router.get("/api/moderation/blacklist")
async def get_blacklist():
    guild_rows = await _sqlite_exec(
        "SELECT user_id, guild_id, expires_at FROM blacklisted_users WHERE expires_at > datetime('now') ORDER BY user_id",
        fetch="all",
    )
    global_rows = await _sqlite_exec(
        "SELECT user_id, expires_at FROM globally_blacklisted_users WHERE expires_at > datetime('now') ORDER BY user_id",
        fetch="all",
    )
    return {
        "guild": [
            {
                "user_id": str(row["user_id"]),
                "guild_id": str(row["guild_id"]),
                "expires_at": row["expires_at"],
            }
            for row in guild_rows
        ],
        "global": [
            {"user_id": str(row["user_id"]), "expires_at": row["expires_at"]}
            for row in global_rows
        ],
    }


@router.post("/api/moderation/blacklist")
async def add_blacklist(body: BlacklistAdd, user_id: int = Depends(require_admin)):
    if body.scope not in ("guild", "global"):
        raise HTTPException(status_code=400, detail="scope 必须是 guild 或 global")
    duration = body.duration_minutes or DEFAULT_BAN_MINUTES
    if duration <= 0:
        raise HTTPException(status_code=400, detail="封禁时长必须为正数")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=duration)
    if body.scope == "guild":
        if body.guild_id is None:
            raise HTTPException(status_code=400, detail="服务器黑名单必须指定 guild_id")
        await chat_db_manager.add_to_blacklist(body.user_id, body.guild_id, expires_at)
    else:
        await chat_db_manager.add_to_global_blacklist(body.user_id, expires_at)
    await audit_log_service.log(
        user_id,
        "ban",
        "blacklist",
        str(body.user_id),
        {
            "scope": body.scope,
            "guild_id": body.guild_id,
            "reason": body.reason,
            "duration_minutes": duration,
        },
    )
    return {"success": True, "expires_at": expires_at.isoformat()}


@router.delete("/api/moderation/blacklist/{target_user_id}")
async def remove_blacklist(
    target_user_id: int,
    scope: str,
    guild_id: Optional[int] = None,
    user_id: int = Depends(require_admin),
):
    if scope not in ("guild", "global"):
        raise HTTPException(status_code=400, detail="scope 必须是 guild 或 global")
    if scope == "guild":
        if guild_id is None:
            raise HTTPException(status_code=400, detail="服务器黑名单必须指定 guild_id")
        row = await _sqlite_exec(
            "SELECT user_id FROM blacklisted_users WHERE user_id = ? AND guild_id = ?",
            (target_user_id, guild_id),
            fetch="one",
        )
        if row is None:
            raise HTTPException(status_code=404, detail="该用户不在服务器黑名单中")
        await chat_db_manager.remove_from_blacklist(target_user_id, guild_id)
    else:
        row = await _sqlite_exec(
            "SELECT user_id FROM globally_blacklisted_users WHERE user_id = ?",
            (target_user_id,),
            fetch="one",
        )
        if row is None:
            raise HTTPException(status_code=404, detail="该用户不在全局黑名单中")
        await chat_db_manager.remove_from_global_blacklist(target_user_id)
    await audit_log_service.log(
        user_id,
        "unban",
        "blacklist",
        str(target_user_id),
        {"scope": scope, "guild_id": guild_id},
    )
    return {"success": True}


@router.get("/api/moderation/muted")
async def get_muted_channels() -> List[Dict[str, Any]]:
    rows = await _sqlite_exec(
        "SELECT channel_id, muted_at, muted_until FROM muted_channels ORDER BY channel_id",
        fetch="all",
    )
    return [
        {
            "channel_id": str(row["channel_id"]),
            "muted_at": row["muted_at"],
            "muted_until": row["muted_until"],
        }
        for row in rows
    ]


@router.post("/api/moderation/muted")
async def add_muted_channel(
    body: MutedChannelAdd, user_id: int = Depends(require_admin)
):
    if body.duration_minutes <= 0:
        raise HTTPException(status_code=400, detail="禁言时长必须为正数")
    await chat_db_manager.add_muted_channel(body.channel_id, body.duration_minutes)
    await audit_log_service.log(
        user_id,
        "mute",
        "muted_channel",
        str(body.channel_id),
        {"duration_minutes": body.duration_minutes},
    )
    return {"success": True}


@router.delete("/api/moderation/muted/{channel_id}")
async def remove_muted_channel(channel_id: int, user_id: int = Depends(require_admin)):
    row = await _sqlite_exec(
        "SELECT channel_id FROM muted_channels WHERE channel_id = ?",
        (channel_id,),
        fetch="one",
    )
    if row is None:
        raise HTTPException(status_code=404, detail="该频道不在禁言列表中")
    await chat_db_manager.remove_muted_channel(channel_id)
    await audit_log_service.log(user_id, "unmute", "muted_channel", str(channel_id), None)
    return {"success": True}
