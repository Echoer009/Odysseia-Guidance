import json
import logging
import os
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


class EventFileUpdate(BaseModel):
    content: str


class FactionSelect(BaseModel):
    event_id: str
    faction_id: str


def _event_dir(event_id: str) -> Path:
    path = EVENTS_DIR / event_id
    if not event_id or not path.is_dir():
        raise HTTPException(status_code=404, detail=f"未找到该活动: {event_id}")
    return path


def _list_files(event_dir: Path) -> List[str]:
    return sorted(p.name for p in event_dir.iterdir() if p.is_file())


def _event_file(event_id: str, name: str) -> Path:
    event_dir = _event_dir(event_id)
    if name not in _list_files(event_dir):
        raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
    path = (event_dir / name).resolve()
    if path.parent != event_dir.resolve() or not path.is_file():
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
                "start_date": manifest.get("start_date"),
                "end_date": manifest.get("end_date"),
                "event_name": manifest.get("event_name"),
                "files": _list_files(event_dir),
            }
        )
    return result


@router.get("/api/events/{event_id}/file/{file_name}")
async def get_event_file(event_id: str, file_name: str):
    path = _event_file(event_id, file_name)
    return {"name": file_name, "content": path.read_text(encoding="utf-8")}


@router.put("/api/events/{event_id}/file/{file_name}")
async def update_event_file(
    event_id: str,
    file_name: str,
    body: EventFileUpdate,
    user_id: int = Depends(require_admin),
):
    path = _event_file(event_id, file_name)
    if file_name.endswith(".json"):
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
        f"{event_id}/{file_name}",
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
