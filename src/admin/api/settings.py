import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.admin.api.providers_models import list_available_models
from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service
from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)
router = APIRouter()


def _guild_ids() -> List[int]:
    ids = []
    for part in os.getenv("GUILD_ID", "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


def _primary_guild_id() -> int:
    ids = _guild_ids()
    return ids[0] if ids else 0


async def _read_global_settings() -> Dict[str, Any]:
    settings = await chat_settings_service.get_guild_settings(_primary_guild_id())
    global_settings = settings["global"]
    return {
        "chat_enabled": global_settings["chat_enabled"],
        "two_stage_enabled": global_settings["two_stage_enabled"],
        "api_fallback_enabled": global_settings["api_fallback_enabled"],
        "feeding_image_enabled": global_settings["feeding_image_enabled"],
        "feeding_command_enabled": global_settings["feeding_command_enabled"],
        "warm_up_enabled": global_settings["warm_up_enabled"],
        "reply_delay_seconds": global_settings["reply_delay_seconds"],
    }


class GlobalSettingsUpdate(BaseModel):
    chat_enabled: Optional[bool] = None
    two_stage_enabled: Optional[bool] = None
    api_fallback_enabled: Optional[bool] = None
    feeding_image_enabled: Optional[bool] = None
    feeding_command_enabled: Optional[bool] = None
    warm_up_enabled: Optional[bool] = None
    reply_delay_seconds: Optional[float] = None


@router.get("/api/settings/global")
async def get_global_settings():
    return await _read_global_settings()


@router.put("/api/settings/global")
async def update_global_settings(
    body: GlobalSettingsUpdate, user_id: int = Depends(require_admin)
):
    changed = body.model_dump(exclude_none=True)
    if body.chat_enabled is not None:
        await chat_db_manager.set_global_setting(
            "chat_enabled", str(body.chat_enabled).lower()
        )
    if body.two_stage_enabled is not None:
        await chat_settings_service.set_two_stage_enabled(body.two_stage_enabled)
    if body.api_fallback_enabled is not None:
        await chat_db_manager.set_global_setting(
            "api_fallback_enabled", str(body.api_fallback_enabled).lower()
        )
    if body.feeding_image_enabled is not None:
        await chat_db_manager.set_global_setting(
            "feeding_image_enabled", str(body.feeding_image_enabled).lower()
        )
    if body.feeding_command_enabled is not None:
        await chat_settings_service.set_feeding_command_enabled(
            body.feeding_command_enabled
        )
    if body.warm_up_enabled is not None:
        await chat_settings_service.db_manager.update_global_chat_config(
            _primary_guild_id(), warm_up_enabled=body.warm_up_enabled
        )
    if body.reply_delay_seconds is not None:
        await chat_settings_service.set_reply_delay(
            int(max(0.0, min(60.0, body.reply_delay_seconds)))
        )
    await audit_log_service.log(
        user_id, "update", "global_settings", "global", changed
    )
    return await _read_global_settings()


async def _read_model_selection() -> Dict[str, Any]:
    return {
        "ai_model": await chat_settings_service.get_current_ai_model(),
        "tool_model": await chat_settings_service.get_tool_model(),
        "writer_model": await chat_settings_service.get_writer_model(),
        "available": await list_available_models(),
    }


class ModelsSelectionUpdate(BaseModel):
    ai_model: Optional[str] = None
    tool_model: Optional[str] = None
    writer_model: Optional[str] = None


@router.get("/api/settings/models")
async def get_model_selection():
    return await _read_model_selection()


@router.put("/api/settings/models")
async def update_model_selection(
    body: ModelsSelectionUpdate, user_id: int = Depends(require_admin)
):
    available = await list_available_models()
    valid_ids = {model["full_id"] for model in available}
    selected = {
        "ai_model": body.ai_model,
        "tool_model": body.tool_model,
        "writer_model": body.writer_model,
    }
    if body.ai_model is not None:
        if body.ai_model not in valid_ids:
            raise HTTPException(status_code=400, detail=f"无效的模型: {body.ai_model}")
        await chat_settings_service.set_ai_model(body.ai_model)
    if body.tool_model is not None:
        if body.tool_model not in valid_ids:
            raise HTTPException(status_code=400, detail=f"无效的模型: {body.tool_model}")
        await chat_settings_service.set_tool_model(body.tool_model)
    if body.writer_model is not None:
        if body.writer_model not in valid_ids:
            raise HTTPException(
                status_code=400, detail=f"无效的模型: {body.writer_model}"
            )
        await chat_settings_service.set_writer_model(body.writer_model)
    await audit_log_service.log(
        user_id,
        "update",
        "model_selection",
        "selection",
        {k: v for k, v in selected.items() if v is not None},
    )
    return await _read_model_selection()


async def _read_embedding_settings() -> Dict[str, Any]:
    return {
        "embedding_model": await chat_settings_service.get_current_embedding_model(),
        "disabled_embedding_models": await chat_settings_service.get_disabled_embedding_models(),
        "available": chat_settings_service.get_available_embedding_models(),
    }


class EmbeddingUpdate(BaseModel):
    embedding_model: Optional[str] = None
    disabled_embedding_models: Optional[List[str]] = None


@router.get("/api/settings/embedding")
async def get_embedding_settings():
    return await _read_embedding_settings()


@router.put("/api/settings/embedding")
async def update_embedding_settings(
    body: EmbeddingUpdate, user_id: int = Depends(require_admin)
):
    try:
        if body.embedding_model is not None:
            await chat_settings_service.set_embedding_model(body.embedding_model)
        if body.disabled_embedding_models is not None:
            await chat_settings_service.set_disabled_embedding_models(
                body.disabled_embedding_models
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await audit_log_service.log(
        user_id,
        "update",
        "embedding_settings",
        "embedding",
        {
            "embedding_model": body.embedding_model,
            "disabled_embedding_models": body.disabled_embedding_models,
        },
    )
    return await _read_embedding_settings()


async def _read_channel_configs() -> List[Dict[str, Any]]:
    result = []
    for guild_id in _guild_ids() or [_primary_guild_id()]:
        settings = await chat_settings_service.get_guild_settings(guild_id)
        for entity_id, config in settings["channels"].items():
            frequency = None
            if (
                config.get("cooldown_duration") is not None
                or config.get("cooldown_limit") is not None
            ):
                frequency = {
                    "duration": config.get("cooldown_duration"),
                    "limit": config.get("cooldown_limit"),
                }
            result.append(
                {
                    "guild_id": guild_id,
                    "entity_id": entity_id,
                    "entity_type": config.get("entity_type"),
                    "chat_enabled": config.get("is_chat_enabled"),
                    "fixed_cooldown": config.get("cooldown_seconds"),
                    "frequency_cooldown": frequency,
                }
            )
    return result


class FrequencyCooldown(BaseModel):
    duration: int
    limit: int


class ChannelCooldownUpsert(BaseModel):
    guild_id: int
    entity_id: int
    chat_enabled: bool
    fixed_cooldown: int
    frequency_cooldown: Optional[FrequencyCooldown] = None


@router.get("/api/cooldown/channels")
async def get_channel_cooldowns():
    return await _read_channel_configs()


@router.put("/api/cooldown/channels")
async def upsert_channel_cooldown(
    body: ChannelCooldownUpsert, user_id: int = Depends(require_admin)
):
    if body.fixed_cooldown < 0:
        raise HTTPException(status_code=400, detail="固定冷却时间不能为负数")
    frequency = body.frequency_cooldown
    if frequency is not None and (frequency.duration <= 0 or frequency.limit <= 0):
        raise HTTPException(status_code=400, detail="频率冷却的时长与次数必须为正数")
    await chat_settings_service.set_entity_settings(
        guild_id=body.guild_id,
        entity_id=body.entity_id,
        entity_type="channel",
        is_chat_enabled=body.chat_enabled,
        cooldown_seconds=body.fixed_cooldown,
        cooldown_duration=frequency.duration if frequency else None,
        cooldown_limit=frequency.limit if frequency else None,
    )
    await audit_log_service.log(
        user_id,
        "update",
        "channel_cooldown",
        str(body.entity_id),
        {
            "guild_id": body.guild_id,
            "chat_enabled": body.chat_enabled,
            "fixed_cooldown": body.fixed_cooldown,
            "frequency_cooldown": frequency.model_dump() if frequency else None,
        },
    )
    return await _read_channel_configs()


async def _read_warmup_channels() -> List[int]:
    channels: List[int] = []
    for guild_id in _guild_ids() or [_primary_guild_id()]:
        channels.extend(await chat_settings_service.get_warm_up_channels(guild_id))
    return channels


class WarmupChannelsUpdate(BaseModel):
    channel_ids: List[int]


@router.get("/api/warmup/channels")
async def get_warmup_channels():
    return await _read_warmup_channels()


@router.put("/api/warmup/channels")
async def update_warmup_channels(
    body: WarmupChannelsUpdate, user_id: int = Depends(require_admin)
):
    guild_id = _primary_guild_id()
    current = await chat_settings_service.get_warm_up_channels(guild_id)
    wanted = list(dict.fromkeys(body.channel_ids))
    for channel_id in wanted:
        if channel_id not in current:
            await chat_settings_service.add_warm_up_channel(guild_id, channel_id)
    for channel_id in current:
        if channel_id not in wanted:
            await chat_settings_service.remove_warm_up_channel(guild_id, channel_id)
    await audit_log_service.log(
        user_id,
        "update",
        "warmup_channels",
        str(guild_id),
        {"channel_ids": wanted},
    )
    return await _read_warmup_channels()
