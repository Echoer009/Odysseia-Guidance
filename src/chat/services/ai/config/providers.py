# -*- coding: utf-8 -*-
"""
AI Provider 配置模块

优先从 PostgreSQL 数据库读取 Provider/Model 配置，
数据库为空时回退到环境变量（向后兼容）。
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Literal, Any, cast

log = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """
    Provider 配置数据类

    Attributes:
        name: Provider 名称（唯一标识）
        type: Provider 类型 (gemini, deepseek, openai_compatible, custom)
        api_key: API 密钥（支持环境变量引用 ${VAR_NAME}）
        base_url: API 基础 URL（可选）
        models: 支持的模型列表
        default_model: 默认模型
        extra: 额外配置参数
        enabled: 是否启用
    """

    name: str
    type: Literal["gemini", "deepseek", "openai_compatible", "custom"]
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    models: List[str] = field(default_factory=list)
    default_model: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def __post_init__(self):
        """处理环境变量引用"""
        self.api_key = self._resolve_env_var(self.api_key)
        self.base_url = self._resolve_env_var(self.base_url)

    @staticmethod
    def _resolve_env_var(value: Optional[str]) -> Optional[str]:
        """解析环境变量引用 ${VAR_NAME}"""
        if not value:
            return None
        if value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            return os.getenv(env_var)
        return value

    def is_available(self) -> bool:
        """检查配置是否可用（已启用且有 API 密钥）"""
        return self.enabled and bool(self.api_key)


async def get_provider_configs_from_db() -> Dict[str, ProviderConfig]:
    """
    从 PostgreSQL 数据库加载 Provider 配置。

    Returns:
        Dict[str, ProviderConfig]: Provider 名称到配置的映射
    """
    configs = {}
    try:
        from src.database.database import AsyncSessionLocal
        from src.database.services.ai_config_service import ai_config_service

        async with AsyncSessionLocal() as session:
            providers = await ai_config_service.get_all_providers(
                session, enabled_only=True
            )

            for provider in providers:
                api_key = provider.api_key_encrypted

                model_names = [m.model_name for m in provider.models if m.enabled]
                if not model_names:
                    default_model = None
                else:
                    default_model = model_names[0]

                provider_type = cast(
                    Literal["gemini", "deepseek", "openai_compatible", "custom"],
                    provider.provider_type,
                )
                extra = dict(provider.extra) if provider.extra else {}

                if provider_type == "gemini_custom":
                    provider_type = "custom"
                    extra["original_provider"] = "gemini"

                from typing import cast as _cast
                valid_types = ("gemini", "deepseek", "openai_compatible", "custom")
                ptype = provider_type if provider_type in valid_types else "custom"
                configs[provider.name] = ProviderConfig(
                    name=provider.name,
                    type=_cast(Literal["gemini", "deepseek", "openai_compatible", "custom"], ptype),
                    api_key=api_key,
                    base_url=provider.base_url,
                    models=model_names,
                    default_model=default_model,
                    extra=extra,
                )
                log.info(
                    f"[DB] 已加载 Provider '{provider.name}'，"
                    f"类型: {provider_type}，模型: {model_names}"
                )

    except Exception as e:
        log.warning(f"从数据库加载 Provider 配置失败: {e}")

    return configs


def _parse_custom_gemini_endpoints() -> Dict[str, ProviderConfig]:
    """
    从环境变量解析自定义 Gemini 端点配置（回退用）
    """
    configs = {}

    for key, value in os.environ.items():
        if key.startswith("CUSTOM_GEMINI_URL_") and key != "CUSTOM_GEMINI_URL":
            endpoint_name = key[len("CUSTOM_GEMINI_URL_") :].lower()
            provider_name = f"gemini_custom_{endpoint_name}"

            api_key = os.getenv(f"CUSTOM_GEMINI_API_KEY_{endpoint_name.upper()}")
            if not api_key:
                api_key = os.getenv(f"CUSTOM_GEMINI_API_KEY_{endpoint_name}")

            if api_key and value:
                models = _get_models_for_provider(provider_name)

                if not models:
                    default_model = f"gemini-{endpoint_name.replace('_', '-')}-custom"
                    models = [default_model]
                else:
                    default_model = models[0]

                configs[provider_name] = ProviderConfig(
                    name=provider_name,
                    type="custom",
                    api_key=api_key,
                    base_url=value,
                    models=models,
                    default_model=default_model,
                    extra={"original_provider": "gemini"},
                )
                log.info(
                    f"[ENV] 已加载自定义 Gemini 端点: {provider_name}，支持模型: {models}"
                )

    return configs


def _get_models_for_provider(provider_name: str) -> List[str]:
    """
    从数据库缓存获取指定 provider 的所有模型（回退用）。
    缓存未初始化时返回空列表，由调用方自行处理默认值。
    """
    try:
        from .models import get_model_configs

        model_configs = get_model_configs()

        models = []
        for model_name, config in model_configs.items():
            if config.provider == provider_name:
                models.append(model_name)

        return models
    except Exception as e:
        log.warning(f"获取 {provider_name} 的模型列表失败: {e}")
        return []


def _get_provider_configs_from_env() -> Dict[str, ProviderConfig]:
    """
    从环境变量加载 Provider 配置（回退方法）
    """
    configs = {}

    google_api_keys = os.getenv("GOOGLE_API_KEYS_LIST", "")
    if google_api_keys:
        configs["gemini_official"] = ProviderConfig(
            name="gemini_official",
            type="gemini",
            api_key=google_api_keys.split(",")[0].strip(),
            base_url=os.getenv("GEMINI_API_BASE_URL"),
            models=[
                "gemini-2.5-flash",
                "gemini-flash-latest",
            ],
            default_model="gemini-2.5-flash",
        )

    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if deepseek_key:
        configs["deepseek"] = ProviderConfig(
            name="deepseek",
            type="deepseek",
            api_key=deepseek_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            models=[
                "deepseek-chat",
                "deepseek-reasoner",
                "deepseek-v4-flash",
                "deepseek-v4-pro",
            ],
            default_model="deepseek-chat",
        )

    openai_key = os.getenv("OPENAI_COMPATIBLE_API_KEY")
    openai_url = os.getenv("OPENAI_COMPATIBLE_URL")
    if openai_key and openai_url:
        configs["openai_compatible"] = ProviderConfig(
            name="openai_compatible",
            type="openai_compatible",
            api_key=openai_key,
            base_url=openai_url,
            models=[
                "gpt-4",
                "gpt-4o",
                "claude-3-opus",
            ],
            default_model="gpt-4o",
        )

    custom_endpoints = _parse_custom_gemini_endpoints()
    configs.update(custom_endpoints)

    return configs


async def get_provider_configs() -> Dict[str, ProviderConfig]:
    """
    获取所有 Provider 配置。

    优先从 PG 数据库读取；如果数据库中无任何 Provider 配置，
    则回退到环境变量（向后兼容旧部署）。

    Returns:
        Dict[str, ProviderConfig]: Provider 名称到配置的映射
    """
    db_configs = await get_provider_configs_from_db()
    if db_configs:
        log.info(f"使用数据库 Provider 配置，共 {len(db_configs)} 个")
        return db_configs

    log.info("数据库中无 Provider 配置，回退到环境变量")
    return _get_provider_configs_from_env()


def get_provider_config(provider_name: str) -> Optional[ProviderConfig]:
    """
    同步获取指定 Provider 的配置（仅从环境变量，用于向后兼容）。
    新代码应使用 get_provider_configs() 异步版本。
    """
    configs = _get_provider_configs_from_env()
    return configs.get(provider_name)
