import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service
from src.chat.config import chat_config
from src.chat.config.prompts import PROMPT_CONFIG, PERSONA_VARIANTS
from src.chat.services.config_override_service import config_override_service
from src.chat.services.config_registry import CONFIG_REGISTRY
from src.config import (
    BOT_NAME,
    BOT_SELF_INTRODUCTION,
    COMMUNITY_NAME,
    COMMUNITY_TYPE,
    CURRENCY_NAME,
    MASCOT_TITLE,
    NICKNAME,
)

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_admin)])

_PROMPT_FIELD_NAMES = {
    "system_prompt": "SYSTEM_PROMPT",
    "jailbreak_user_prompt": "JAILBREAK_USER_PROMPT",
    "jailbreak_model_response": "JAILBREAK_MODEL_RESPONSE",
    "jailbreak_final_instruction": "JAILBREAK_FINAL_INSTRUCTION",
}

_PROMPT_FIELD_LABELS = {
    "system_prompt": "系统提示词",
    "jailbreak_user_prompt": "越狱用户提示词",
    "jailbreak_model_response": "越狱模型响应",
    "jailbreak_final_instruction": "最终指令",
}

_IDENTITY_DEFAULTS = {
    "identity.bot_name": ("Bot 名称", BOT_NAME),
    "identity.community_name": ("社区名称", COMMUNITY_NAME),
    "identity.currency_name": ("货币名称", CURRENCY_NAME),
    "identity.mascot_title": ("看板娘称号", MASCOT_TITLE),
    "identity.nickname": ("爱称", NICKNAME),
    "identity.community_type": ("社区类型", COMMUNITY_TYPE),
    "identity.bot_self_introduction": ("自我介绍", BOT_SELF_INTRODUCTION),
}

_FEATURE_PROMPT_DEFAULTS = {
    "feature.tool_router_prompt": (
        "工具路由提示词",
        chat_config.TOOL_ROUTER_SYSTEM_PROMPT,
    ),
    "feature.feeding_prompt": (
        "投喂评价提示词",
        chat_config.PROMPT_CONFIG.get("feeding_prompt", ""),
    ),
    "feature.gift_system_prompt": (
        "礼物系统提示词",
        chat_config.GIFT_SYSTEM_PROMPT,
    ),
    "feature.gift_prompt": ("礼物感谢提示词", chat_config.GIFT_PROMPT),
    "feature.confession_persona_injection": (
        "忏悔人设注入",
        chat_config.CONFESSION_PERSONA_INJECTION,
    ),
    "feature.confession_prompt": ("忏悔提示词", chat_config.CONFESSION_PROMPT),
    "feature.warmup_messages": ("暖贴消息集合", chat_config.WARMUP_MESSAGES),
}


class OverrideUpdate(BaseModel):
    value: Any


class PersonaUpdate(BaseModel):
    value: Any


def _registry_entry(key: str) -> Optional[Dict[str, Any]]:
    for entry in CONFIG_REGISTRY:
        if entry["key"] == key:
            return entry
    return None


def _code_prompt_default(model_name: str, suffix: str) -> Optional[str]:
    field = _PROMPT_FIELD_NAMES[suffix]
    model_config = PROMPT_CONFIG.get(model_name) or {}
    value = model_config.get(field)
    if value is None and model_name != "default":
        value = PROMPT_CONFIG.get("default", {}).get(field)
    return value


def _persona_text_specs() -> List[Dict[str, Any]]:
    specs = []
    for model_name in PROMPT_CONFIG:
        for suffix, field_label in _PROMPT_FIELD_LABELS.items():
            specs.append(
                {
                    "key": f"persona.{model_name}.{suffix}",
                    "label": f"{model_name} · {field_label}",
                    "group": "人设与身份",
                    "default": _code_prompt_default(model_name, suffix),
                }
            )
    for style, variants in PERSONA_VARIANTS.items():
        for model_name, model_config in variants.items():
            specs.append(
                {
                    "key": f"persona.variant.{style}.{model_name}.system_prompt",
                    "label": f"{style} · {model_name} · 系统提示词",
                    "group": "人设风格变体",
                    "default": model_config.get("SYSTEM_PROMPT"),
                }
            )
    for key, (label, default) in _FEATURE_PROMPT_DEFAULTS.items():
        specs.append(
            {
                "key": key,
                "label": label,
                "group": "功能提示词",
                "default": default,
            }
        )
    return specs


def _persona_identity_specs() -> List[Dict[str, Any]]:
    return [
        {
            "key": key,
            "label": label,
            "group": "身份字段",
            "default": default,
        }
        for key, (label, default) in _IDENTITY_DEFAULTS.items()
    ]


def _find_spec(specs: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
    for spec in specs:
        if spec["key"] == key:
            return spec
    return None


@router.get("/api/config/overrides")
async def list_config_overrides():
    registry_keys = {entry["key"] for entry in CONFIG_REGISTRY}
    overrides = {
        item["key"]: item for item in await config_override_service.list_overrides()
    }
    items = []
    for entry in CONFIG_REGISTRY:
        override = overrides.get(entry["key"])
        value = override["value"] if override else None
        items.append(
            {
                "key": entry["key"],
                "group": entry["group"],
                "label": entry["label"],
                "description": entry["description"],
                "default": entry["default"],
                "value": value,
                "effective": value if value is not None else entry["default"],
            }
        )
    extra = [item for key, item in overrides.items() if key not in registry_keys]
    return {"items": items, "extra": extra}


@router.put("/api/config/overrides/{key}")
async def update_config_override(
    key: str, body: OverrideUpdate, user_id: int = Depends(require_admin)
):
    entry = _registry_entry(key)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"未注册的配置键: {key}")
    await config_override_service.set(key, body.value)
    await audit_log_service.log(
        user_id, "update", "config_override", key, {"value": body.value}
    )
    return {"success": True, "key": key, "value": body.value}


@router.delete("/api/config/overrides/{key}")
async def delete_config_override(key: str, user_id: int = Depends(require_admin)):
    entry = _registry_entry(key)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"未注册的配置键: {key}")
    deleted = await config_override_service.delete(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"该配置键没有覆盖值: {key}")
    await audit_log_service.log(
        user_id, "delete", "config_override", key, {"reverted_to": entry["default"]}
    )
    return {"success": True}


@router.get("/api/persona")
async def list_persona_texts():
    text_specs = _persona_text_specs()
    identity_specs = _persona_identity_specs()
    overrides = {
        item["key"]: item for item in await config_override_service.list_overrides()
    }

    def _with_value(spec: Dict[str, Any]) -> Dict[str, Any]:
        override = overrides.get(spec["key"])
        spec["value"] = override["value"] if override else spec["default"]
        return spec

    return {
        "texts": [_with_value(dict(spec)) for spec in text_specs],
        "identity": [_with_value(dict(spec)) for spec in identity_specs],
    }


@router.put("/api/persona/{key}")
async def update_persona_text(
    key: str, body: PersonaUpdate, user_id: int = Depends(require_admin)
):
    spec = _find_spec(_persona_text_specs() + _persona_identity_specs(), key)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"未注册的人设键: {key}")
    if key in _IDENTITY_DEFAULTS and not isinstance(body.value, str):
        raise HTTPException(status_code=400, detail="身份字段的值必须是字符串")
    if key == "feature.warmup_messages" and not isinstance(body.value, dict):
        raise HTTPException(status_code=400, detail="暖贴消息集合的值必须是 JSON 对象")
    await config_override_service.set(key, body.value)
    await audit_log_service.log(
        user_id, "update", "persona", key, None
    )
    return {"success": True, "key": key, "value": body.value}


@router.delete("/api/persona/{key}")
async def delete_persona_text(key: str, user_id: int = Depends(require_admin)):
    spec = _find_spec(_persona_text_specs() + _persona_identity_specs(), key)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"未注册的人设键: {key}")
    deleted = await config_override_service.delete(key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"该人设键没有覆盖值: {key}")
    await audit_log_service.log(
        user_id, "delete", "persona", key, {"reverted_to": spec["default"]}
    )
    return {"success": True}
