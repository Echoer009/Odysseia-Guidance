import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])

EVENTS_DIR = Path(__file__).resolve().parents[3] / "src" / "chat" / "events"

EVENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

SETTLEMENT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS event_settlements (
    event_id TEXT PRIMARY KEY,
    winning_faction TEXT,
    total_points INTEGER,
    settled_at TIMESTAMP DEFAULT (datetime('now'))
);
"""


class EventFileUpdate(BaseModel):
    content: str


class FactionSelect(BaseModel):
    event_id: str
    faction_id: str


class EventCreate(BaseModel):
    event_id: str
    event_name: str
    start_date: str
    end_date: str
    description: str = ""
    theme: Optional[Dict[str, Any]] = None


class ManifestUpdate(BaseModel):
    event_name: Optional[str] = None
    is_active: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    theme: Optional[Dict[str, Any]] = None
    announcement_channel_id: Optional[int] = None
    entry_panel: Optional[Dict[str, Any]] = None


def _event_dir(event_id: str) -> Path:
    path = EVENTS_DIR / event_id
    if not event_id or not path.is_dir():
        raise HTTPException(status_code=404, detail=f"未找到该活动: {event_id}")
    return path


def _list_files(event_dir: Path) -> List[str]:
    return sorted(
        p.relative_to(event_dir).as_posix()
        for p in event_dir.rglob("*")
        if p.is_file() and p.suffix != ".tmp"
    )


def _event_file(event_id: str, name: str) -> Path:
    event_dir = _event_dir(event_id)
    if name not in _list_files(event_dir):
        raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
    path = (event_dir / name).resolve()
    if not path.is_relative_to(event_dir.resolve()) or not path.is_file():
        raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
    return path


def _load_manifest(event_dir: Path) -> Optional[Dict[str, Any]]:
    manifest_path = event_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, data: Any) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def _is_currently_active(manifest: Dict[str, Any]) -> bool:
    if not manifest.get("is_active"):
        return False
    try:
        now = datetime.now(timezone.utc)
        start = datetime.fromisoformat(str(manifest.get("start_date")).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(manifest.get("end_date")).replace("Z", "+00:00"))
        return start <= now < end
    except (ValueError, AttributeError):
        return False


def _parse_iso(value: Any, field: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"{field} 时间格式错误: {value}")


async def _fetch_all(query: str, params: tuple = ()) -> List[sqlite3.Row]:
    try:
        rows = await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, params, fetch="all"
        )
        return list(rows) if rows else []
    except sqlite3.OperationalError as e:
        log.warning(f"查询 chat.db 失败: {e} | Query: {query}")
        return []


async def _fetch_one(query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    try:
        return await chat_db_manager._execute(
            chat_db_manager._db_transaction, query, params, fetch="one"
        )
    except sqlite3.OperationalError as e:
        log.warning(f"查询 chat.db 失败: {e} | Query: {query}")
        return None


async def _ensure_settlement_table() -> None:
    try:
        await chat_db_manager._execute(
            chat_db_manager._db_transaction, SETTLEMENT_TABLE_SQL, (), commit=True
        )
    except sqlite3.Error as e:
        log.warning(f"确保 event_settlements 表存在时失败: {e}")


def _faction_map(event_id: str) -> Dict[str, Dict[str, Any]]:
    factions_path = _event_dir(event_id) / "factions.json"
    if not factions_path.is_file():
        return {}
    try:
        factions = json.loads(factions_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(factions, list):
        return {}
    return {str(f.get("faction_id")): f for f in factions if isinstance(f, dict)}


@router.get("/api/events")
async def list_events():
    if not EVENTS_DIR.is_dir():
        return []
    result = []
    for event_dir in sorted(p for p in EVENTS_DIR.iterdir() if p.is_dir()):
        manifest = _load_manifest(event_dir)
        if manifest is None:
            result.append(
                {
                    "id": event_dir.name,
                    "is_active": False,
                    "enabled": False,
                    "start_date": None,
                    "end_date": None,
                    "files": _list_files(event_dir),
                    "note": "缺少 manifest.json",
                }
            )
            continue
        result.append(
            {
                "id": event_dir.name,
                "is_active": _is_currently_active(manifest),
                "enabled": bool(manifest.get("is_active")),
                "start_date": manifest.get("start_date"),
                "end_date": manifest.get("end_date"),
                "event_name": manifest.get("event_name"),
                "description": manifest.get("description"),
                "announcement_channel_id": manifest.get("announcement_channel_id"),
                "theme": manifest.get("theme"),
                "files": _list_files(event_dir),
            }
        )
    return result


@router.post("/api/events")
async def create_event(body: EventCreate, user_id: int = Depends(require_admin)):
    event_id = body.event_id.strip()
    event_name = body.event_name.strip()
    if not EVENT_ID_RE.fullmatch(event_id):
        raise HTTPException(
            status_code=400,
            detail="event_id 不合法，仅允许小写字母、数字、下划线和连字符",
        )
    if not event_name:
        raise HTTPException(status_code=400, detail="event_name 不能为空")
    event_dir = EVENTS_DIR / event_id
    if event_dir.exists():
        raise HTTPException(status_code=409, detail=f"活动已存在: {event_id}")
    start = _parse_iso(body.start_date, "start_date")
    end = _parse_iso(body.end_date, "end_date")
    if start >= end:
        raise HTTPException(status_code=400, detail="start_date 必须早于 end_date")

    event_dir.mkdir(parents=True)
    (event_dir / "factions").mkdir()
    manifest: Dict[str, Any] = {
        "event_id": event_id,
        "event_name": event_name,
        "is_active": False,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "description": body.description,
    }
    if body.theme:
        manifest["theme"] = body.theme
    _write_json(event_dir / "manifest.json", manifest)
    _write_json(event_dir / "factions.json", [])
    _write_json(event_dir / "items.json", {})
    _write_json(event_dir / "prompts.json", {"system_prompt_faction_packs": {}})
    await audit_log_service.log(
        user_id, "create", "event", event_id, {"event_name": event_name}
    )
    return {"success": True, "event_id": event_id}


@router.patch("/api/events/{event_id}/manifest")
async def update_manifest(
    event_id: str, body: ManifestUpdate, user_id: int = Depends(require_admin)
):
    event_dir = _event_dir(event_id)
    manifest = _load_manifest(event_dir)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"该活动缺少 manifest.json: {event_id}")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return {"success": True, "updated": []}
    for field in ("start_date", "end_date"):
        if field in changes:
            _parse_iso(changes[field], field)
    if "event_name" in changes and not str(changes["event_name"]).strip():
        raise HTTPException(status_code=400, detail="event_name 不能为空")
    manifest.update(changes)
    _write_json(event_dir / "manifest.json", manifest)
    await chat_db_manager.set_global_setting("event_reload_pending", "1")
    await audit_log_service.log(
        user_id, "update", "event_manifest", event_id, {"fields": sorted(changes)}
    )
    return {"success": True, "updated": sorted(changes)}


@router.get("/api/events/{event_id}/file/{file_path:path}")
async def get_event_file(event_id: str, file_path: str):
    path = _event_file(event_id, file_path)
    return {"name": file_path, "content": path.read_text(encoding="utf-8")}


@router.put("/api/events/{event_id}/file/{file_path:path}")
async def update_event_file(
    event_id: str,
    file_path: str,
    body: EventFileUpdate,
    user_id: int = Depends(require_admin),
):
    path = _event_file(event_id, file_path)
    if file_path.endswith(".json"):
        try:
            json.loads(body.content)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"JSON 格式错误: {e}")
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(body.content, encoding="utf-8")
    os.replace(tmp_path, path)
    await chat_db_manager.set_global_setting("event_reload_pending", "1")
    await audit_log_service.log(
        user_id,
        "update",
        "event_file",
        f"{event_id}/{file_path}",
        {"length": len(body.content)},
    )
    return {"success": True}


@router.post("/api/events/{event_id}/reload")
async def reload_event(event_id: str, user_id: int = Depends(require_admin)):
    _event_dir(event_id)
    await chat_db_manager.set_global_setting("event_reload_pending", "1")
    await audit_log_service.log(
        user_id, "reload", "event", event_id, {"event_reload_pending": "1"}
    )
    return {"success": True}


@router.post("/api/events/select-faction")
async def select_faction(body: FactionSelect, user_id: int = Depends(require_admin)):
    event_dir = _event_dir(body.event_id)
    factions_path = event_dir / "factions.json"
    if not factions_path.is_file():
        raise HTTPException(status_code=404, detail=f"该活动没有派系配置: {body.event_id}")
    try:
        factions = json.loads(factions_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="factions.json 解析失败")
    if not any(f.get("faction_id") == body.faction_id for f in factions):
        raise HTTPException(status_code=404, detail=f"未找到该派系: {body.faction_id}")
    value = f"{body.event_id}:{body.faction_id}"
    await chat_db_manager.set_global_setting("event_selected_faction", value)
    await chat_db_manager.set_global_setting("event_reload_pending", "1")
    await audit_log_service.log(
        user_id, "select_faction", "event_faction", value, None
    )
    return {"success": True, "selected": value}


@router.get("/api/events/{event_id}/factions-summary")
async def factions_summary(event_id: str):
    event_dir = _event_dir(event_id)
    factions_path = event_dir / "factions.json"
    if not factions_path.is_file():
        raise HTTPException(status_code=404, detail=f"该活动没有派系配置: {event_id}")
    try:
        factions = json.loads(factions_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="factions.json 解析失败")
    selected = await chat_db_manager.get_global_setting("event_selected_faction")
    selected_faction = selected.split(":", 1)[1] if selected and ":" in selected else None
    return [
        {
            "id": f.get("faction_id"),
            "name": f.get("faction_name"),
            "icon": f.get("icon"),
            "selected": f.get("faction_id") == selected_faction,
        }
        for f in factions
    ]


@router.get("/api/events/{event_id}/leaderboard")
async def event_leaderboard(event_id: str):
    _event_dir(event_id)
    rows = await _fetch_all(
        "SELECT faction_id, total_points FROM event_faction_points "
        "WHERE event_id = ? ORDER BY total_points DESC",
        (event_id,),
    )
    factions = _faction_map(event_id)
    return [
        {
            "faction_id": row["faction_id"],
            "faction_name": factions.get(str(row["faction_id"]), {}).get(
                "faction_name", row["faction_id"]
            ),
            "icon": factions.get(str(row["faction_id"]), {}).get("icon"),
            "total_points": row["total_points"],
        }
        for row in rows
    ]


@router.get("/api/events/{event_id}/settlement")
async def get_settlement(event_id: str):
    _event_dir(event_id)
    await _ensure_settlement_table()
    row = await _fetch_one(
        "SELECT event_id, winning_faction, total_points, settled_at "
        "FROM event_settlements WHERE event_id = ?",
        (event_id,),
    )
    if row is None:
        return None
    return {
        "event_id": row["event_id"],
        "winning_faction": row["winning_faction"],
        "total_points": row["total_points"],
        "settled_at": row["settled_at"],
    }


@router.post("/api/events/{event_id}/settle")
async def settle_event(event_id: str, user_id: int = Depends(require_admin)):
    _event_dir(event_id)
    await _ensure_settlement_table()
    existing = await _fetch_one(
        "SELECT event_id FROM event_settlements WHERE event_id = ?", (event_id,)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="该活动已有结算记录")
    rows = await _fetch_all(
        "SELECT faction_id, total_points FROM event_faction_points "
        "WHERE event_id = ? ORDER BY total_points DESC LIMIT 1",
        (event_id,),
    )
    if not rows:
        raise HTTPException(status_code=400, detail="排行榜为空，无法结算")
    winner = rows[0]
    await chat_db_manager._execute(
        chat_db_manager._db_transaction,
        "INSERT INTO event_settlements (event_id, winning_faction, total_points) "
        "VALUES (?, ?, ?)",
        (event_id, winner["faction_id"], winner["total_points"]),
        commit=True,
    )
    await audit_log_service.log(
        user_id,
        "settle",
        "event",
        event_id,
        {"winning_faction": winner["faction_id"], "total_points": winner["total_points"]},
    )
    row = await _fetch_one(
        "SELECT settled_at FROM event_settlements WHERE event_id = ?", (event_id,)
    )
    faction = _faction_map(event_id).get(str(winner["faction_id"]), {})
    return {
        "success": True,
        "winning_faction": winner["faction_id"],
        "faction_name": faction.get("faction_name", winner["faction_id"]),
        "total_points": winner["total_points"],
        "settled_at": row["settled_at"] if row else None,
    }


@router.get("/api/events/{event_id}/stats")
async def event_stats(event_id: str):
    _event_dir(event_id)
    row = await _fetch_one(
        "SELECT COUNT(DISTINCT user_id) AS participants, "
        "COALESCE(SUM(points_contributed), 0) AS total_points, "
        "COUNT(*) AS entries "
        "FROM event_contribution_log WHERE event_id = ?",
        (event_id,),
    )
    if row is None:
        return {"participants": 0, "total_points": 0, "entries": 0}
    return {
        "participants": row["participants"],
        "total_points": row["total_points"],
        "entries": row["entries"],
    }
