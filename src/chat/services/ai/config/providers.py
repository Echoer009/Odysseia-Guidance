# -*- coding: utf-8 -*-
"""
AI Provider 配置模块

定义各种 AI 服务提供者的配置
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Literal, Any

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


def _parse_custom_gemini_endpoints() -> Dict[str, ProviderConfig]:
    """
    从环境变量解析自定义 Gemini 端点配置

    环境变量格式：
    - CUSTOM_GEMINI_URL_<NAME>=https://...          (必填) 端点 URL
    - CUSTOM_GEMINI_API_KEY_<NAME>=key              (必填) API 密钥

    模型列表从 models_config.json 中读取，查找所有使用 gemini_custom_<name> provider 的模型。

    示例：
    - CUSTOM_GEMINI_URL_GG=https://api.example.com
    - CUSTOM_GEMINI_API_KEY_GG=sk-xxx
    - models_config.json 中的模型 provider 设为 "gemini_custom_gg"
    """
    configs = {}

    # 遍历环境变量查找自定义端点
    for key, value in os.environ.items():
        if key.startswith("CUSTOM_GEMINI_URL_") and key != "CUSTOM_GEMINI_URL":
            endpoint_name = key[len("CUSTOM_GEMINI_URL_") :].lower()
            provider_name = f"gemini_custom_{endpoint_name}"

            # 查找对应的 API 密钥
            api_key = os.getenv(f"CUSTOM_GEMINI_API_KEY_{endpoint_name.upper()}")
            if not api_key:
                api_key = os.getenv(f"CUSTOM_GEMINI_API_KEY_{endpoint_name}")

            if api_key and value:
                # 从 models_config.json 读取该 provider 支持的模型
                models = _get_models_for_provider(provider_name)

                # 如果没有配置模型，使用默认模型名
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
                    f"已加载自定义 Gemini 端点: {provider_name}，支持模型: {models}"
                )

    return configs


def _get_models_for_provider(provider_name: str) -> List[str]:
    """
    从 models_config.json 获取指定 provider 的所有模型

    Args:
        provider_name: Provider 名称

    Returns:
        List[str]: 模型名称列表
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
        log.warning(f"读取 models_config.json 中的 {provider_name} 模型失败: {e}")
        return []


def get_provider_configs() -> Dict[str, ProviderConfig]:
    """
    获取所有 Provider 配置

    Returns:
        Dict[str, ProviderConfig]: Provider 名称到配置的映射
    """
    configs = {}

    # 1. Gemini 官方 API
    google_api_keys = os.getenv("GOOGLE_API_KEYS_LIST", "")
    if google_api_keys:
        configs["gemini_official"] = ProviderConfig(
            name="gemini_official",
            type="gemini",
            api_key=google_api_keys.split(",")[0].strip(),  # 使用第一个密钥
            base_url=os.getenv("GEMINI_API_BASE_URL"),
            models=[
                "gemini-2.5-flash",
                "gemini-flash-latest",
            ],
            default_model="gemini-2.5-flash",
        )

    # 2. DeepSeek API
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

    # 3. OpenAI 兼容端点
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

    # 4. 自定义 Gemini 端点（从环境变量加载）
    custom_endpoints = _parse_custom_gemini_endpoints()
    configs.update(custom_endpoints)

    return configs


def get_provider_config(provider_name: str) -> Optional[ProviderConfig]:
    """
    获取指定 Provider 的配置

    Args:
        provider_name: Provider 名称

    Returns:
        Optional[ProviderConfig]: Provider 配置，如果不存在则返回 None
    """
    configs = get_provider_configs()
    return configs.get(provider_name)
