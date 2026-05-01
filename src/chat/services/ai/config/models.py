# -*- coding: utf-8 -*-
"""
AI 模型配置模块

定义支持的模型及其配置
所有模型配置从 JSON 配置文件动态加载，不在代码中硬编码任何模型
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any
from pathlib import Path
from enum import Enum

log = logging.getLogger(__name__)

# JSON 配置文件路径
MODELS_CONFIG_PATH = Path(__file__).parent / "models_config.json"


class SupportedParam(Enum):
    """模型支持的参数类型"""

    TEMPERATURE = "temperature"
    TOP_P = "top_p"
    TOP_K = "top_k"
    MAX_OUTPUT_TOKENS = "max_output_tokens"
    PRESENCE_PENALTY = "presence_penalty"
    FREQUENCY_PENALTY = "frequency_penalty"
    THINKING_BUDGET_TOKENS = "thinking_budget_tokens"  # Gemini 专用


# 不同模型提供商支持的参数
# DeepSeek: temperature, top_p, presence_penalty, frequency_penalty, max_tokens
# Gemini: temperature, top_p, top_k, max_output_tokens, thinking_budget_tokens
# OpenAI: temperature, top_p, presence_penalty, frequency_penalty, max_tokens
# Gemini 提供商支持的参数列表（包括官方和自定义）
_GEMINI_PARAMS = [
    SupportedParam.TEMPERATURE,
    SupportedParam.TOP_P,
    SupportedParam.TOP_K,
    SupportedParam.MAX_OUTPUT_TOKENS,
    SupportedParam.THINKING_BUDGET_TOKENS,
]

PROVIDER_SUPPORTED_PARAMS: Dict[str, List[SupportedParam]] = {
    "deepseek": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.MAX_OUTPUT_TOKENS,
        SupportedParam.PRESENCE_PENALTY,
        SupportedParam.FREQUENCY_PENALTY,
    ],
    "gemini": _GEMINI_PARAMS,
    "gemini_official": _GEMINI_PARAMS,
    "gemini_custom_gg": _GEMINI_PARAMS,
    "openai": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.MAX_OUTPUT_TOKENS,
        SupportedParam.PRESENCE_PENALTY,
        SupportedParam.FREQUENCY_PENALTY,
    ],
    "anthropic": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.TOP_K,
        SupportedParam.MAX_OUTPUT_TOKENS,
    ],
    "default": [
        SupportedParam.TEMPERATURE,
        SupportedParam.TOP_P,
        SupportedParam.MAX_OUTPUT_TOKENS,
    ],
}


def get_supported_params_for_provider(provider: str) -> List[SupportedParam]:
    """
    获取指定提供商支持的参数列表

    Args:
        provider: 提供商名称

    Returns:
        List[SupportedParam]: 支持的参数列表
    """
    return PROVIDER_SUPPORTED_PARAMS.get(provider, PROVIDER_SUPPORTED_PARAMS["default"])


@dataclass
class PromptConfig:
    """
    提示词配置数据类

    Attributes:
        system_prompt: 系统提示词
        jailbreak_user_prompt: 越狱用户提示词
        jailbreak_model_response: 越狱模型响应
        jailbreak_final_instruction: 最终指令
        use_cache_optimized_build: 是否使用缓存优化的构建顺序
    """

    system_prompt: Optional[str] = None
    jailbreak_user_prompt: Optional[str] = None
    jailbreak_model_response: Optional[str] = None
    jailbreak_final_instruction: Optional[str] = None
    use_cache_optimized_build: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptConfig":
        """从字典创建 PromptConfig 实例"""
        return cls(
            system_prompt=data.get("system_prompt"),
            jailbreak_user_prompt=data.get("jailbreak_user_prompt"),
            jailbreak_model_response=data.get("jailbreak_model_response"),
            jailbreak_final_instruction=data.get("jailbreak_final_instruction"),
            use_cache_optimized_build=data.get("use_cache_optimized_build"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，只包含非 None 的值"""
        result = {}
        if self.system_prompt is not None:
            result["system_prompt"] = self.system_prompt
        if self.jailbreak_user_prompt is not None:
            result["jailbreak_user_prompt"] = self.jailbreak_user_prompt
        if self.jailbreak_model_response is not None:
            result["jailbreak_model_response"] = self.jailbreak_model_response
        if self.jailbreak_final_instruction is not None:
            result["jailbreak_final_instruction"] = self.jailbreak_final_instruction
        if self.use_cache_optimized_build is not None:
            result["use_cache_optimized_build"] = self.use_cache_optimized_build
        return result


@dataclass
class GenerationConfigParams:
    """
    生成参数配置数据类

    Attributes:
        temperature: 温度参数
        top_p: Top-p 采样
        top_k: Top-k 采样（仅部分 Provider 支持）
        max_output_tokens: 最大输出 token 数
        presence_penalty: 存在惩罚（仅部分 Provider 支持）
        frequency_penalty: 频率惩罚（仅部分 Provider 支持）
        thinking_budget_tokens: 思考链 token 预算（仅 Gemini 支持）
    """

    temperature: float = 1.0
    top_p: float = 0.95
    top_k: Optional[int] = None
    max_output_tokens: int = 8192
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    thinking_budget_tokens: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GenerationConfigParams":
        """从字典创建 GenerationConfigParams 实例"""
        return cls(
            temperature=data.get("temperature", 1.0),
            top_p=data.get("top_p", 0.95),
            top_k=data.get("top_k"),
            max_output_tokens=data.get("max_output_tokens", 8192),
            presence_penalty=data.get("presence_penalty"),
            frequency_penalty=data.get("frequency_penalty"),
            thinking_budget_tokens=data.get("thinking_budget_tokens"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，只包含非 None 的值"""
        result = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens,
        }
        if self.top_k is not None:
            result["top_k"] = self.top_k
        if self.presence_penalty is not None:
            result["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            result["frequency_penalty"] = self.frequency_penalty
        if self.thinking_budget_tokens is not None:
            result["thinking_budget_tokens"] = self.thinking_budget_tokens
        return result


@dataclass
class ModelConfig:
    """
    模型配置数据类

    Attributes:
        display_name: 显示名称
        provider: 所属 Provider 名称
        actual_model: 实际调用的模型名（可能与显示名不同）
        generation_config: 生成配置参数
        prompt_config: 提示词配置
        supports_vision: 是否支持视觉/图片
        supports_tools: 是否支持工具调用
        supports_thinking: 是否支持思考链
        max_output_tokens: 最大输出 token 数
        description: 模型描述
    """

    display_name: str
    provider: str
    actual_model: str
    generation_config: GenerationConfigParams = field(
        default_factory=GenerationConfigParams
    )
    prompt_config: PromptConfig = field(default_factory=PromptConfig)
    supports_vision: bool = False
    supports_tools: bool = True
    supports_thinking: bool = False
    max_output_tokens: int = 6000
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        """
        从字典创建 ModelConfig 实例

        Args:
            data: 包含模型配置的字典

        Returns:
            ModelConfig 实例
        """
        gen_config_data = data.get("generation_config", {})
        prompt_config_data = data.get("prompt_config", {})

        return cls(
            display_name=data.get("display_name", ""),
            provider=data.get("provider", ""),
            actual_model=data.get("actual_model", ""),
            generation_config=GenerationConfigParams.from_dict(gen_config_data),
            prompt_config=PromptConfig.from_dict(prompt_config_data),
            supports_vision=data.get("supports_vision", False),
            supports_tools=data.get("supports_tools", True),
            supports_thinking=data.get("supports_thinking", False),
            max_output_tokens=data.get("max_output_tokens", 6000),
            description=data.get("description", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于保存到 JSON"""
        result = {
            "display_name": self.display_name,
            "provider": self.provider,
            "actual_model": self.actual_model,
            "supports_vision": self.supports_vision,
            "supports_tools": self.supports_tools,
            "supports_thinking": self.supports_thinking,
            "max_output_tokens": self.max_output_tokens,
            "description": self.description,
            "generation_config": self.generation_config.to_dict(),
            "prompt_config": self.prompt_config.to_dict(),
        }
        return result


# 模型配置缓存
_model_configs_cache: Optional[Dict[str, ModelConfig]] = None


def _load_models_from_json() -> Dict[str, ModelConfig]:
    """
    从 JSON 配置文件加载模型配置（回退用）

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    configs = {}

    if not MODELS_CONFIG_PATH.exists():
        log.warning(f"模型配置文件不存在: {MODELS_CONFIG_PATH}，将只使用环境变量配置")
        return configs

    try:
        with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        for model_name, model_data in config_data.items():
            configs[model_name] = ModelConfig.from_dict(model_data)

        log.info(f"已从 {MODELS_CONFIG_PATH} 加载 {len(configs)} 个模型配置")

    except Exception as e:
        log.error(f"加载模型配置文件失败: {e}")

    return configs


async def _load_models_from_db() -> Dict[str, ModelConfig]:
    """
    从 PostgreSQL 数据库加载模型配置。

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    configs = {}
    try:
        from src.database.database import AsyncSessionLocal
        from src.database.services.ai_config_service import ai_config_service

        async with AsyncSessionLocal() as session:
            models = await ai_config_service.get_all_models(session, enabled_only=True)
            for m in models:
                gen_dict = m.generation_config or {}
                prompt_dict = m.prompt_config or {}

                gen_config = GenerationConfigParams(
                    temperature=gen_dict.get("temperature", 1.0),
                    top_p=gen_dict.get("top_p", 0.95),
                    top_k=gen_dict.get("top_k"),
                    max_output_tokens=gen_dict.get("max_output_tokens", m.max_output_tokens),
                    presence_penalty=gen_dict.get("presence_penalty", 0.0),
                    frequency_penalty=gen_dict.get("frequency_penalty", 0.0),
                    thinking_budget_tokens=gen_dict.get("thinking_budget_tokens"),
                )

                prompt_config = PromptConfig(
                    system_prompt=prompt_dict.get("system_prompt"),
                    jailbreak_user_prompt=prompt_dict.get("jailbreak_user_prompt"),
                    jailbreak_model_response=prompt_dict.get("jailbreak_model_response"),
                    jailbreak_final_instruction=prompt_dict.get("jailbreak_final_instruction"),
                    use_cache_optimized_build=prompt_dict.get("use_cache_optimized_build"),
                )

                provider_name = m.provider.name if m.provider else "unknown"

                configs[m.model_name] = ModelConfig(
                    display_name=m.display_name,
                    provider=provider_name,
                    actual_model=m.actual_model,
                    description=m.description or "",
                    supports_vision=bool(m.supports_vision),
                    supports_tools=bool(m.supports_tools),
                    supports_thinking=bool(m.supports_thinking),
                    max_output_tokens=m.max_output_tokens,
                    generation_config=gen_config,
                    prompt_config=prompt_config,
                )

        if configs:
            log.info(f"[DB] 已从数据库加载 {len(configs)} 个模型配置")

    except Exception as e:
        log.warning(f"从数据库加载模型配置失败: {e}")

    return configs


async def get_model_configs_async() -> Dict[str, ModelConfig]:
    """
    异步获取所有模型配置。优先从 PG 数据库读取，数据库为空时回退到 JSON 文件。

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    global _model_configs_cache

    if _model_configs_cache is not None:
        return _model_configs_cache

    db_configs = await _load_models_from_db()
    if db_configs:
        _model_configs_cache = db_configs
        return db_configs

    log.info("数据库中无模型配置，回退到 JSON 文件")
    configs = _load_models_from_json()
    _model_configs_cache = configs
    return configs


def get_model_configs() -> Dict[str, ModelConfig]:
    """
    同步获取所有模型配置。
    优先返回缓存；无缓存时从 JSON 文件加载（向后兼容）。
    新代码应使用 get_model_configs_async() 异步版本。

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    global _model_configs_cache

    if _model_configs_cache is not None:
        return _model_configs_cache

    configs = _load_models_from_json()
    _model_configs_cache = configs
    return configs


def reload_model_configs() -> Dict[str, ModelConfig]:
    """
    重新加载模型配置（清除缓存）

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    global _model_configs_cache
    _model_configs_cache = None
    return get_model_configs()


async def reload_model_configs_async() -> Dict[str, ModelConfig]:
    """
    异步重新加载模型配置（清除缓存，从数据库重新读取）

    Returns:
        Dict[str, ModelConfig]: 模型名称到配置的映射
    """
    global _model_configs_cache
    _model_configs_cache = None
    return await get_model_configs_async()


def get_model_config(model_name: str) -> Optional[ModelConfig]:
    """
    获取指定模型的配置

    Args:
        model_name: 模型名称

    Returns:
        Optional[ModelConfig]: 模型配置，如果不存在则返回 None
    """
    configs = get_model_configs()
    return configs.get(model_name)


def get_available_models() -> List[str]:
    """
    获取所有可用的模型名称列表

    Returns:
        List[str]: 模型名称列表
    """
    return list(get_model_configs().keys())


# 故障转移优先级配置
# 这个配置保留在代码中，因为它是系统行为配置，不是模型定义
# 注意：gemini_official 需要有效的 Google API 密钥，如果没有配置请从列表中移除
FALLBACK_PRIORITY: Dict[str, List[str]] = {
    # 当使用 Gemini 自定义端点失败时
    "gemini_custom": [
        "deepseek",  # 首选 DeepSeek
        "openai_compatible",  # 其次 OpenAI 兼容端点
        # "gemini_official",  # 已禁用：需要有效的 Google API 密钥
    ],
    # 当使用 DeepSeek 失败时
    "deepseek": [
        "gemini_custom",
        "openai_compatible",
        # "gemini_official",  # 已禁用：需要有效的 Google API 密钥
    ],
    # 当使用 OpenAI 兼容端点失败时
    "openai_compatible": [
        "deepseek",
        "gemini_custom",
        # "gemini_official",  # 已禁用：需要有效的 Google API 密钥
    ],
    # 当使用 Gemini 官方失败时
    "gemini_official": [
        "gemini_custom",
        "deepseek",
        "openai_compatible",
    ],
}


def get_fallback_providers(provider_type: str) -> List[str]:
    """
    获取指定 Provider 类型的故障转移优先级列表

    Args:
        provider_type: Provider 类型

    Returns:
        List[str]: 故障转移 Provider 列表
    """
    # 标准化 provider_type
    normalized = provider_type.lower()

    # 检查是否是自定义 Gemini 端点
    if normalized.startswith("gemini_custom") or "custom" in normalized:
        return FALLBACK_PRIORITY.get("gemini_custom", [])

    return FALLBACK_PRIORITY.get(normalized, [])


def save_model_config(model_name: str, config: ModelConfig) -> bool:
    """
    保存单个模型的配置到 JSON 文件

    Args:
        model_name: 模型名称
        config: 模型配置

    Returns:
        bool: 是否保存成功
    """
    try:
        # 读取现有配置
        config_data = {}
        if MODELS_CONFIG_PATH.exists():
            with open(MODELS_CONFIG_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)

        # 更新指定模型的配置
        config_data[model_name] = config.to_dict()

        # 保存到文件
        with open(MODELS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)

        # 清除缓存以强制重新加载
        global _model_configs_cache
        _model_configs_cache = None

        log.info(f"已保存模型 {model_name} 的配置到 {MODELS_CONFIG_PATH}")
        return True

    except Exception as e:
        log.error(f"保存模型配置失败: {e}")
        return False


def save_all_model_configs(configs: Dict[str, ModelConfig]) -> bool:
    """
    保存所有模型配置到 JSON 文件

    Args:
        configs: 模型名称到配置的映射

    Returns:
        bool: 是否保存成功
    """
    try:
        config_data = {name: config.to_dict() for name, config in configs.items()}

        with open(MODELS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)

        # 清除缓存以强制重新加载
        global _model_configs_cache
        _model_configs_cache = None

        log.info(f"已保存所有模型配置到 {MODELS_CONFIG_PATH}")
        return True

    except Exception as e:
        log.error(f"保存所有模型配置失败: {e}")
        return False


def get_generation_config(model_name: str) -> GenerationConfigParams:
    """
    获取指定模型的生成参数配置

    Args:
        model_name: 模型名称

    Returns:
        GenerationConfigParams: 生成参数配置，如果模型不存在则返回默认配置
    """
    config = get_model_config(model_name)
    if config:
        return config.generation_config
    return GenerationConfigParams()


def get_prompt_config(model_name: str) -> PromptConfig:
    """
    获取指定模型的提示词配置

    Args:
        model_name: 模型名称

    Returns:
        PromptConfig: 提示词配置，如果模型不存在则返回默认配置
    """
    config = get_model_config(model_name)
    if config:
        return config.prompt_config
    return PromptConfig()


# 原始配置备份路径
_ORIGINAL_CONFIG_BACKUP_PATH = Path(__file__).parent / "models_config_original.json"


def _get_original_configs() -> Dict[str, ModelConfig]:
    """
    获取原始模型配置（用于重置）

    如果备份文件不存在，则从当前配置文件复制一份作为备份

    Returns:
        Dict[str, ModelConfig]: 原始模型配置
    """
    if _ORIGINAL_CONFIG_BACKUP_PATH.exists():
        try:
            with open(_ORIGINAL_CONFIG_BACKUP_PATH, "r", encoding="utf-8") as f:
                config_data = json.load(f)
            return {
                name: ModelConfig.from_dict(data) for name, data in config_data.items()
            }
        except Exception as e:
            log.warning(f"读取原始配置备份失败: {e}，将使用当前配置")

    # 如果没有备份，返回当前配置
    return get_model_configs()


def reset_model_to_original(model_name: str) -> bool:
    """
    将指定模型的配置重置为原始值

    Args:
        model_name: 模型名称

    Returns:
        bool: 是否成功重置
    """
    try:
        original_configs = _get_original_configs()

        if model_name not in original_configs:
            log.warning(f"模型 {model_name} 不存在于原始配置中")
            return False

        # 保存原始配置到当前配置
        save_model_config(model_name, original_configs[model_name])
        log.info(f"已重置模型 {model_name} 的配置到原始值")
        return True

    except Exception as e:
        log.error(f"重置模型配置失败: {e}")
        return False


def update_model_generation_config(
    model_name: str,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    max_output_tokens: Optional[int] = None,
    presence_penalty: Optional[float] = None,
    frequency_penalty: Optional[float] = None,
    thinking_budget_tokens: Optional[int] = None,
) -> bool:
    """
    更新指定模型的生成参数配置

    Args:
        model_name: 模型名称
        temperature: 温度参数
        top_p: Top-p 采样
        top_k: Top-k 采样
        max_output_tokens: 最大输出 token 数
        presence_penalty: 存在惩罚
        frequency_penalty: 频率惩罚
        thinking_budget_tokens: 思考链 token 预算

    Returns:
        bool: 是否成功更新
    """
    config = get_model_config(model_name)
    if config is None:
        log.warning(f"模型 {model_name} 不存在")
        return False

    # 更新生成参数
    gen_config = config.generation_config
    if temperature is not None:
        gen_config.temperature = temperature
    if top_p is not None:
        gen_config.top_p = top_p
    if top_k is not None:
        gen_config.top_k = top_k
    if max_output_tokens is not None:
        gen_config.max_output_tokens = max_output_tokens
    if presence_penalty is not None:
        gen_config.presence_penalty = presence_penalty
    if frequency_penalty is not None:
        gen_config.frequency_penalty = frequency_penalty
    if thinking_budget_tokens is not None:
        gen_config.thinking_budget_tokens = thinking_budget_tokens

    # 保存更新后的配置
    return save_model_config(model_name, config)


def update_model_prompt_config(
    model_name: str,
    system_prompt: Optional[str] = None,
    jailbreak_user_prompt: Optional[str] = None,
    jailbreak_model_response: Optional[str] = None,
    jailbreak_final_instruction: Optional[str] = None,
    use_cache_optimized_build: Optional[bool] = None,
) -> bool:
    """
    更新指定模型的提示词配置

    Args:
        model_name: 模型名称
        system_prompt: 系统提示词
        jailbreak_user_prompt: 越狱用户提示词
        jailbreak_model_response: 越狱模型响应
        jailbreak_final_instruction: 最终指令
        use_cache_optimized_build: 是否使用缓存优化的构建顺序

    Returns:
        bool: 是否成功更新
    """
    config = get_model_config(model_name)
    if config is None:
        log.warning(f"模型 {model_name} 不存在")
        return False

    # 更新提示词配置
    prompt_config = config.prompt_config
    if system_prompt is not None:
        prompt_config.system_prompt = system_prompt
    if jailbreak_user_prompt is not None:
        prompt_config.jailbreak_user_prompt = jailbreak_user_prompt
    if jailbreak_model_response is not None:
        prompt_config.jailbreak_model_response = jailbreak_model_response
    if jailbreak_final_instruction is not None:
        prompt_config.jailbreak_final_instruction = jailbreak_final_instruction
    if use_cache_optimized_build is not None:
        prompt_config.use_cache_optimized_build = use_cache_optimized_build

    # 保存更新后的配置
    return save_model_config(model_name, config)
