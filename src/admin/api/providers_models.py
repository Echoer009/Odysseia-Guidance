import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from src.admin.auth import require_admin
from src.admin.services.audit_log_service import audit_log_service
from src.chat.utils.database import chat_db_manager
from src.database.database import AsyncSessionLocal
from src.database.services.ai_config_service import ai_config_service

log = logging.getLogger(__name__)
router = APIRouter()


async def flag_ai_reload() -> None:
    await chat_db_manager.set_global_setting("ai_reload_pending", "1")


def provider_dict(provider) -> Dict[str, Any]:
    return {
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "display_name": provider.display_name,
        "base_url": provider.base_url,
        "enabled": bool(provider.enabled),
        "has_api_key": bool(provider.api_key_encrypted),
    }


def model_dict(model) -> Dict[str, Any]:
    return {
        "id": model.id,
        "model_name": model.model_name,
        "display_name": model.display_name,
        "provider_id": model.provider_id,
        "actual_model": model.actual_model,
        "description": model.description,
        "supports_vision": bool(model.supports_vision),
        "supports_tools": bool(model.supports_tools),
        "supports_thinking": bool(model.supports_thinking),
        "max_output_tokens": model.max_output_tokens,
        "generation_config": model.generation_config,
        "prompt_config": model.prompt_config,
        "enabled": bool(model.enabled),
        "capabilities": {
            "supports_vision": bool(model.supports_vision),
            "supports_tools": bool(model.supports_tools),
            "supports_thinking": bool(model.supports_thinking),
        },
    }


async def list_available_models() -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        models = await ai_config_service.get_all_models(session)
    result = []
    for model in models:
        provider_name = model.provider.name if model.provider else "unknown"
        result.append(
            {
                "full_id": f"{provider_name}:{model.model_name}",
                "display_name": model.display_name,
                "provider_name": provider_name,
                "enabled": bool(model.enabled),
                "supports_vision": bool(model.supports_vision),
                "supports_tools": bool(model.supports_tools),
                "supports_thinking": bool(model.supports_thinking),
            }
        )
    return result


class ProviderCreate(BaseModel):
    name: str
    provider_type: str
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    display_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    enabled: Optional[bool] = None


class ModelCreate(BaseModel):
    model_name: str
    display_name: Optional[str] = None
    provider_id: int
    actual_model: Optional[str] = None
    description: Optional[str] = None
    supports_vision: bool = False
    supports_tools: bool = True
    supports_thinking: bool = False
    max_output_tokens: int = 8192
    generation_config: Optional[Dict[str, Any]] = None
    prompt_config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


class ModelUpdate(BaseModel):
    model_name: Optional[str] = None
    display_name: Optional[str] = None
    provider_id: Optional[int] = None
    actual_model: Optional[str] = None
    description: Optional[str] = None
    supports_vision: Optional[bool] = None
    supports_tools: Optional[bool] = None
    supports_thinking: Optional[bool] = None
    max_output_tokens: Optional[int] = None
    generation_config: Optional[Dict[str, Any]] = None
    prompt_config: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


@router.get("/api/providers")
async def list_providers():
    async with AsyncSessionLocal() as session:
        providers = await ai_config_service.get_all_providers(session)
    return [provider_dict(provider) for provider in providers]


@router.post("/api/providers")
async def create_provider(body: ProviderCreate, user_id: int = Depends(require_admin)):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Provider 名称不能为空")
    if not body.provider_type.strip():
        raise HTTPException(status_code=400, detail="Provider 类型不能为空")
    async with AsyncSessionLocal() as session:
        try:
            provider = await ai_config_service.create_provider(
                session,
                name=name,
                provider_type=body.provider_type.strip(),
                display_name=body.display_name or name,
                api_key=body.api_key or "",
                base_url=body.base_url,
            )
            if body.enabled is False:
                provider = await ai_config_service.update_provider(
                    session, provider.id, enabled=0
                )
        except IntegrityError:
            raise HTTPException(status_code=400, detail=f"Provider 名称已存在: {name}")
    await flag_ai_reload()
    await audit_log_service.log(
        user_id,
        "create",
        "ai_provider",
        name,
        {"provider_type": body.provider_type.strip(), "base_url": body.base_url},
    )
    return provider_dict(provider)


@router.put("/api/providers/{provider_id}")
async def update_provider(
    provider_id: int, body: ProviderUpdate, user_id: int = Depends(require_admin)
):
    kwargs: Dict[str, Any] = {}
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Provider 名称不能为空")
        kwargs["name"] = name
    if body.provider_type is not None:
        kwargs["provider_type"] = body.provider_type
    if body.display_name is not None:
        kwargs["display_name"] = body.display_name
    if body.base_url is not None:
        kwargs["base_url"] = body.base_url
    if body.api_key:
        kwargs["api_key"] = body.api_key
    if body.enabled is not None:
        kwargs["enabled"] = 1 if body.enabled else 0
    async with AsyncSessionLocal() as session:
        try:
            provider = await ai_config_service.update_provider(
                session, provider_id, **kwargs
            )
        except IntegrityError:
            raise HTTPException(status_code=400, detail="Provider 名称已存在")
        if provider is None:
            raise HTTPException(status_code=404, detail="未找到该 Provider")
    await flag_ai_reload()
    await audit_log_service.log(
        user_id, "update", "ai_provider", str(provider_id), {"fields": sorted(kwargs)}
    )
    return provider_dict(provider)


@router.delete("/api/providers/{provider_id}")
async def delete_provider(provider_id: int, user_id: int = Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        deleted = await ai_config_service.delete_provider(session, provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到该 Provider")
    await flag_ai_reload()
    await audit_log_service.log(user_id, "delete", "ai_provider", str(provider_id))
    return {"success": True}


@router.get("/api/models")
async def list_models():
    async with AsyncSessionLocal() as session:
        models = await ai_config_service.get_all_models(session)
    return [model_dict(model) for model in models]


@router.post("/api/models")
async def create_model(body: ModelCreate, user_id: int = Depends(require_admin)):
    model_name = body.model_name.strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    async with AsyncSessionLocal() as session:
        providers = await ai_config_service.get_all_providers(session)
        if not any(p.id == body.provider_id for p in providers):
            raise HTTPException(status_code=400, detail="指定的 Provider 不存在")
        try:
            model = await ai_config_service.create_model(
                session,
                model_name=model_name,
                display_name=body.display_name or model_name,
                provider_id=body.provider_id,
                actual_model=body.actual_model or model_name,
                description=body.description,
                supports_vision=body.supports_vision,
                supports_tools=body.supports_tools,
                supports_thinking=body.supports_thinking,
                max_output_tokens=body.max_output_tokens,
                generation_config=body.generation_config,
                prompt_config=body.prompt_config,
            )
            if body.enabled is False:
                model = await ai_config_service.update_model(
                    session, model.id, enabled=0
                )
        except IntegrityError:
            raise HTTPException(status_code=400, detail=f"模型名称已存在: {model_name}")
    await flag_ai_reload()
    await audit_log_service.log(
        user_id,
        "create",
        "ai_model",
        model_name,
        {"provider_id": body.provider_id, "actual_model": body.actual_model},
    )
    return model_dict(model)


@router.put("/api/models/{model_id}")
async def update_model(
    model_id: int, body: ModelUpdate, user_id: int = Depends(require_admin)
):
    kwargs: Dict[str, Any] = {}
    if body.model_name is not None:
        model_name = body.model_name.strip()
        if not model_name:
            raise HTTPException(status_code=400, detail="模型名称不能为空")
        kwargs["model_name"] = model_name
    if body.display_name is not None:
        kwargs["display_name"] = body.display_name
    if body.provider_id is not None:
        kwargs["provider_id"] = body.provider_id
    if body.actual_model is not None:
        kwargs["actual_model"] = body.actual_model
    if body.description is not None:
        kwargs["description"] = body.description
    if body.supports_vision is not None:
        kwargs["supports_vision"] = body.supports_vision
    if body.supports_tools is not None:
        kwargs["supports_tools"] = body.supports_tools
    if body.supports_thinking is not None:
        kwargs["supports_thinking"] = body.supports_thinking
    if body.max_output_tokens is not None:
        kwargs["max_output_tokens"] = body.max_output_tokens
    if body.generation_config is not None:
        kwargs["generation_config"] = body.generation_config
    if body.prompt_config is not None:
        kwargs["prompt_config"] = body.prompt_config
    if body.enabled is not None:
        kwargs["enabled"] = 1 if body.enabled else 0
    async with AsyncSessionLocal() as session:
        if body.provider_id is not None:
            providers = await ai_config_service.get_all_providers(session)
            if not any(p.id == body.provider_id for p in providers):
                raise HTTPException(status_code=400, detail="指定的 Provider 不存在")
        try:
            model = await ai_config_service.update_model(session, model_id, **kwargs)
        except IntegrityError:
            raise HTTPException(status_code=400, detail="模型名称已存在")
        if model is None:
            raise HTTPException(status_code=404, detail="未找到该模型")
    await flag_ai_reload()
    await audit_log_service.log(
        user_id, "update", "ai_model", str(model_id), {"fields": sorted(kwargs)}
    )
    return model_dict(model)


@router.delete("/api/models/{model_id}")
async def delete_model(model_id: int, user_id: int = Depends(require_admin)):
    async with AsyncSessionLocal() as session:
        deleted = await ai_config_service.delete_model(session, model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="未找到该模型")
    await flag_ai_reload()
    await audit_log_service.log(user_id, "delete", "ai_model", str(model_id))
    return {"success": True}
