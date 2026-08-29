import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.chat.features.content_filter.services import content_filter_service
from src.chat.features.tools.services.global_tool_settings_service import (
    global_tool_settings_service,
)
from src.chat.features.tools.tool_metadata import TOOL_METADATA
from src.database.database import AsyncSessionLocal
from src.database.services.token_usage_service import token_usage_service

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/tools")
async def get_tools():
    status = await global_tool_settings_service.get_all_tools_status()
    result = []
    for name, info in status.items():
        metadata = info.get("metadata", {})
        result.append(
            {
                "name": name,
                "description": metadata.get("description", ""),
                "enabled": not info.get("is_disabled", False),
                "protected": info.get("is_protected", False),
            }
        )
    return result


class ToolsUpdate(BaseModel):
    disabled_tools: List[str]


@router.put("/api/tools")
async def update_tools(body: ToolsUpdate):
    unknown = [t for t in body.disabled_tools if t not in TOOL_METADATA]
    if unknown:
        raise HTTPException(status_code=400, detail=f"未知的工具: {', '.join(unknown)}")
    protected = await global_tool_settings_service.get_protected_tools()
    conflict = [t for t in body.disabled_tools if t in protected]
    if conflict:
        raise HTTPException(
            status_code=400, detail=f"不能禁用系统保留工具: {', '.join(conflict)}"
        )
    await global_tool_settings_service.set_disabled_tools(body.disabled_tools)
    return await get_tools()


async def _read_keywords() -> Dict[str, List[str]]:
    rows = await content_filter_service.get_all_keywords_with_status()
    return {
        "keywords": [keyword for keyword, ignored in rows if not ignored],
        "ignore": [keyword for keyword, ignored in rows if ignored],
    }


@router.get("/api/filter/keywords")
async def get_keywords():
    return await _read_keywords()


class KeywordCreate(BaseModel):
    keyword: str
    ignore: Optional[bool] = None


@router.post("/api/filter/keywords")
async def create_keyword(body: KeywordCreate):
    keyword = body.keyword.strip().lower()
    if not keyword:
        raise HTTPException(status_code=400, detail="关键词不能为空")
    await content_filter_service.add_keyword(keyword)
    if body.ignore:
        await content_filter_service.ignore_keywords([keyword])
    return await _read_keywords()


@router.delete("/api/filter/keywords/{keyword}")
async def delete_keyword(keyword: str):
    removed = await content_filter_service.remove_keyword(keyword)
    if not removed:
        raise HTTPException(status_code=404, detail="关键词不存在")
    return await _read_keywords()


@router.get("/api/token-usage")
async def get_token_usage():
    today = date.today()
    async with AsyncSessionLocal() as session:
        usage = await token_usage_service.get_token_usage(session, today)
    if usage is None:
        return {
            "date": str(today),
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "call_count": 0,
        }
    usage_date = usage.date.date() if hasattr(usage.date, "date") else usage.date
    return {
        "date": str(usage_date),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "call_count": usage.call_count,
    }
