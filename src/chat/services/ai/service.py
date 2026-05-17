# -*- coding: utf-8 -*-
"""
AI Service 统一入口

提供统一的 AI 服务接口，支持：
- 多种 AI Provider（Gemini、DeepSeek、OpenAI 兼容等）
- 自动故障转移
- 工具调用支持
- Token 统计
"""

import asyncio
import json
import os
import logging
from typing import Optional, Dict, Any, List

from .providers.base import (
    BaseProvider,
    GenerationConfig,
    GenerationResult,
    GenerationError,
    ModelNotSupportedError,
)
from .providers import (
    GeminiProvider,
    GeminiCustomProvider,
    DeepSeekProvider,
    OpenAICompatibleProvider,
)
from .config.providers import get_provider_configs, ProviderConfig, _get_provider_configs_from_env
from .config.models import get_fallback_providers, get_model_config
from src.chat.config.chat_config import PROVIDER_RETRY_CONFIG

log = logging.getLogger(__name__)


class AIService:
    """
    AI 服务统一入口

    提供：
    - 统一的生成接口
    - 自动 Provider 选择和故障转移
    - 工具调用支持
    - Token 统计集成
    """

    def __init__(self):
        """初始化 AI 服务"""
        self._providers: Dict[str, BaseProvider] = {}
        self._model_to_provider: Dict[str, str] = {}
        self._default_provider: Optional[str] = None

        # Bot 实例（用于工具调用等）
        self.bot: Optional[Any] = None

        # 工具服务（延迟初始化）
        self._tool_service = None
        self._available_tools: List[Any] = []
        self._tool_map: Dict[str, Any] = {}

        self._initialized = False

    async def initialize(self):
        """异步初始化：优先从 PG 数据库加载 Provider，回退到环境变量。"""
        if self._initialized:
            return
        await self._initialize_providers_async()
        from .config.models import get_model_configs_async
        await get_model_configs_async()
        self._initialized = True

    def _initialize_providers(self):
        """同步初始化 Provider（从环境变量回退，向后兼容）"""
        provider_configs = _get_provider_configs_from_env()

        for provider_name, config in provider_configs.items():
            if not config.is_available():
                log.info(f"Provider '{provider_name}' 不可用，跳过初始化")
                continue

            try:
                provider = self._create_provider(config)
                if provider:
                    self._providers[provider_name] = provider

                    for model_name in config.models:
                        self._model_to_provider[model_name] = config.name

                    if self._default_provider is None:
                        self._default_provider = provider_name

                    log.info(
                        f"成功初始化 Provider '{provider_name}'，支持模型: {config.models}"
                    )

            except Exception as e:
                log.error(f"初始化 Provider '{provider_name}' 失败: {e}", exc_info=True)

        log.info(f"AIService 初始化完成，共 {len(self._providers)} 个 Provider")

    async def _initialize_providers_async(self):
        """异步初始化 Provider（优先 PG 数据库）"""
        provider_configs = await get_provider_configs()

        if not provider_configs:
            log.info("异步初始化未获得 Provider 配置，尝试同步回退")
            self._initialize_providers()
            return

        for provider_name, config in provider_configs.items():
            if not config.is_available():
                log.info(f"Provider '{provider_name}' 不可用，跳过初始化")
                continue

            try:
                provider = self._create_provider(config)
                if provider:
                    self._providers[provider_name] = provider

                    for model_name in config.models:
                        self._model_to_provider[model_name] = config.name

                    if self._default_provider is None:
                        self._default_provider = provider_name

                    log.info(
                        f"[Async] 成功初始化 Provider '{provider_name}'，支持模型: {config.models}"
                    )

            except Exception as e:
                log.error(f"初始化 Provider '{provider_name}' 失败: {e}", exc_info=True)

        log.info(f"AIService 异步初始化完成，共 {len(self._providers)} 个 Provider")

    async def reload_providers(self):
        """重新加载 Provider 配置（用于运行时通过 Discord UI 添加/删除后刷新）"""
        self._providers.clear()
        self._model_to_provider.clear()
        self._default_provider = None
        self._initialized = False
        await self.initialize()

    def _create_provider(self, config: ProviderConfig) -> Optional[BaseProvider]:
        """
        根据配置创建 Provider 实例

        Args:
            config: Provider 配置

        Returns:
            Optional[BaseProvider]: Provider 实例
        """
        if config.type == "gemini":
            # Gemini 官方 API
            api_keys_str = os.getenv("GOOGLE_API_KEYS_LIST", "")
            api_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]

            return GeminiProvider(
                api_key=config.api_key,
                base_url=config.base_url,
                use_key_rotation=bool(api_keys),
                api_keys_list=api_keys if api_keys else None,
                provider_name=config.name,
            )

        elif config.type == "deepseek":
            return DeepSeekProvider(
                api_key=config.api_key,
                base_url=config.base_url,
                provider_name=config.name,
            )

        elif config.type == "openai_compatible":
            return OpenAICompatibleProvider(
                api_key=config.api_key,
                base_url=config.base_url,
                provider_name=config.name,
                models=config.models,
                default_model=config.default_model,
            )

        elif config.type == "custom":
            # 自定义 Gemini 端点
            extra = config.extra or {}
            api_key = config.api_key or ""
            base_url = config.base_url or ""
            if extra.get("original_provider") == "gemini":
                return GeminiCustomProvider(
                    api_key=api_key,
                    base_url=base_url,
                    provider_name=config.name,
                    models=config.models,
                )
            else:
                # 其他自定义端点使用 OpenAI 兼容格式
                return OpenAICompatibleProvider(
                    api_key=api_key,
                    base_url=base_url,
                    provider_name=config.name,
                    models=config.models,
                    default_model=config.default_model,
                )

        else:
            log.warning(f"未知的 Provider 类型: {config.type}")
            return None

    def set_bot(self, bot: Any):
        """
        设置 Discord Bot 实例

        Args:
            bot: Discord Bot 实例
        """
        self.bot = bot
        log.info("Discord Bot 实例已注入 AIService")

        # 同时注入到工具服务
        if self._tool_service:
            self._tool_service.bot = bot
            log.info("Discord Bot 实例已注入 ToolService")

    def set_tools(
        self, available_tools: List[Any], tool_map: Dict[str, Any], tool_service: Any
    ):
        """
        设置工具配置

        Args:
            available_tools: 可用工具列表
            tool_map: 工具名称到函数的映射
            tool_service: 工具服务实例
        """
        self._available_tools = available_tools
        self._tool_map = tool_map
        self._tool_service = tool_service
        log.info(f"AIService 已设置 {len(available_tools)} 个工具")

    @property
    def tool_service(self) -> Any:
        """获取工具服务"""
        return self._tool_service

    def register_provider(self, name: str, provider: BaseProvider):
        """
        手动注册一个 Provider

        Args:
            name: Provider 名称
            provider: Provider 实例
        """
        self._providers[name] = provider
        for model in provider.supported_models:
            self._model_to_provider[model] = name

    def get_provider(self, name: str) -> Optional[BaseProvider]:
        """
        获取指定名称的 Provider

        Args:
            name: Provider 名称

        Returns:
            Optional[BaseProvider]: Provider 实例
        """
        return self._providers.get(name)

    def parse_model_id(self, model_id: str) -> tuple[str, Optional[str]]:
        """
        解析模型 ID，支持 "provider:model" 格式和旧格式。

        Args:
            model_id: 模型 ID，可以是 "provider:model" 或纯模型名

        Returns:
            (model_name, provider_name) 元组
            - 如果是新格式，返回解析后的 (model, provider)
            - 如果是旧格式，返回 (model, None)，需要后续查找 provider
        """
        if not model_id:
            return model_id, None

        if ":" in model_id:
            parts = model_id.split(":", 1)
            return parts[1], parts[0]

        return model_id, None

    def get_provider_for_model(
        self, model_name: str, provider_name: Optional[str] = None
    ) -> Optional[BaseProvider]:
        """
        获取支持指定模型的 Provider

        Args:
            model_name: 模型名称
            provider_name: 可选的 Provider 名称（用于新格式）

        Returns:
            Optional[BaseProvider]: Provider 实例
        """
        # 如果指定了 provider，直接使用
        if provider_name:
            return self._providers.get(provider_name)

        # 否则从映射表查找
        provider_name = self._model_to_provider.get(model_name)
        if provider_name:
            return self._providers.get(provider_name)
        return None

    def get_actual_model_name(self, model_name: str) -> str:
        """
        获取模型的实际调用名称（actual_model）

        Args:
            model_name: 模型显示名称（如 gemini-2.5-pro-custom）

        Returns:
            str: 实际调用的模型名称（如 gemini-2.5-pro）
        """
        model_config = get_model_config(model_name)
        if model_config and model_config.actual_model:
            return model_config.actual_model
        # 如果没有配置或没有 actual_model，返回原始名称
        return model_name

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        model: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        fallback: bool = True,
        **kwargs,
    ) -> GenerationResult:
        """
        使用指定模型生成回复

        Args:
            messages: 对话消息列表
            config: 生成配置
            model: 模型 ID，支持 "provider:model" 格式或纯模型名
            tools: 工具列表
            fallback: 是否启用故障转移
            **kwargs: 其他参数

        Returns:
            GenerationResult: 生成结果
        """
        config = config or GenerationConfig()
        model_id = model or self._get_default_model()

        # 解析模型 ID（支持 "provider:model" 格式）
        model_name, explicit_provider = self.parse_model_id(model_id)

        # 获取 Provider
        provider = self.get_provider_for_model(model_name, explicit_provider)
        if not provider:
            raise ModelNotSupportedError(f"不支持的模型: {model_id}")

        # 确定 provider_name（优先使用显式指定的，否则从映射表查找）
        if explicit_provider:
            provider_name = explicit_provider
        else:
            provider_name = self._model_to_provider.get(model_name, "")

        # 获取实际调用的模型名称（actual_model）
        actual_model = self.get_actual_model_name(model_name)
        log.info(
            f"[AIService] 使用模型: {model_name} (实际: {actual_model}), Provider: {provider_name}"
        )

        # 预处理消息：对于不支持视觉的 Provider，将图片转换为文字描述
        messages = await self._preprocess_messages_for_vision(
            messages, provider, **kwargs
        )

        # 记录完整上下文日志（如果启用）
        self._log_full_context_if_enabled(messages, tools, model_name)

        try:
            return await self._retry_generate(
                provider=provider,
                messages=messages,
                config=config,
                tools=tools,
                model=actual_model,
                provider_name=provider_name,
                **kwargs,
            )
        except GenerationError as e:
            if fallback:
                return await self._fallback_generate(
                    messages=messages,
                    config=config,
                    tools=tools,
                    failed_provider=provider_name,
                    original_error=e,
                    model=model_name,
                    **kwargs,
                )
            raise
        except Exception as e:
            if fallback:
                return await self._fallback_generate(
                    messages=messages,
                    config=config,
                    tools=tools,
                    failed_provider=provider_name,
                    original_error=e,
                    model=model_name,
                    **kwargs,
                )
            raise GenerationError(
                f"生成失败: {e}",
                provider_type=provider_name,
                original_error=e,
            )

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        model: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        tool_executor: Optional[Any] = None,
        max_iterations: int = 5,
        fallback: bool = True,
        user_id_for_settings: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        带工具调用支持的生成方法

        Args:
            messages: 对话消息列表
            config: 生成配置
            model: 模型 ID，支持 "provider:model" 格式或纯模型名
            tools: 工具列表
            tool_executor: 工具执行函数
            max_iterations: 最大迭代次数
            fallback: 是否启用故障转移
            user_id_for_settings: 用于获取工具设置的用户 ID（故障转移时需要重新获取工具）
            **kwargs: 其他参数

        Returns:
            GenerationResult: 最终生成结果
        """
        config = config or GenerationConfig()
        model_id = model or self._get_default_model()

        # 解析模型 ID（支持 "provider:model" 格式）
        model_name, explicit_provider = self.parse_model_id(model_id)

        provider = self.get_provider_for_model(model_name, explicit_provider)
        if not provider:
            raise ModelNotSupportedError(f"不支持的模型: {model_id}")

        # 确定 provider_name（优先使用显式指定的，否则从映射表查找）
        if explicit_provider:
            provider_name = explicit_provider
        else:
            provider_name = self._model_to_provider.get(model_name, "")

        # 获取实际调用的模型名称（actual_model）
        actual_model = self.get_actual_model_name(model_name)
        log.info(
            f"[AIService] 使用模型: {model_name} (实际: {actual_model}), Provider: {provider_name} (with tools)"
        )

        # 预处理消息：对于不支持视觉的 Provider，将图片转换为文字描述
        messages = await self._preprocess_messages_for_vision(
            messages, provider, **kwargs
        )

        # 记录完整上下文日志（如果启用）
        self._log_full_context_if_enabled(messages, tools, model_name)

        try:
            return await self._retry_generate_with_tools(
                provider=provider,
                messages=messages,
                config=config,
                tools=tools,
                model=actual_model,
                provider_name=provider_name,
                tool_executor=tool_executor,
                max_iterations=max_iterations,
                **kwargs,
            )
        except GenerationError as e:
            if fallback:
                return await self._fallback_generate(
                    messages=messages,
                    config=config,
                    tools=tools,
                    failed_provider=provider_name,
                    original_error=e,
                    model=model_name,
                    tool_executor=tool_executor,
                    max_iterations=max_iterations,
                    user_id_for_settings=user_id_for_settings,
                    **kwargs,
                )
            raise
        except Exception as e:
            if fallback:
                return await self._fallback_generate(
                    messages=messages,
                    config=config,
                    tools=tools,
                    failed_provider=provider_name,
                    original_error=e,
                    model=model_name,
                    tool_executor=tool_executor,
                    max_iterations=max_iterations,
                    user_id_for_settings=user_id_for_settings,
                    **kwargs,
                )
            raise GenerationError(
                f"工具调用生成失败: {e}",
                provider_type=provider_name,
                original_error=e,
            )

    async def _retry_generate(
        self,
        provider: BaseProvider,
        messages: List[Dict[str, Any]],
        config: GenerationConfig,
        tools: Optional[List[Any]],
        model: str,
        provider_name: str,
        **kwargs,
    ) -> GenerationResult:
        """
        带重试逻辑的生成方法

        在故障转移前，先对同一 Provider 重试指定次数。

        Args:
            provider: Provider 实例
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表
            model: 实际模型名称
            provider_name: Provider 名称（用于日志）
            **kwargs: 其他参数

        Returns:
            GenerationResult: 生成结果

        Raises:
            GenerationError: 所有重试均失败时抛出
            Exception: 其他未预期的异常
        """
        max_retries = PROVIDER_RETRY_CONFIG["MAX_RETRIES"]
        retry_delay = PROVIDER_RETRY_CONFIG["RETRY_DELAY_SECONDS"]
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                result = await provider.generate(
                    messages=messages,
                    config=config,
                    tools=tools,
                    model=model,
                    **kwargs,
                )
                if not result.content:
                    raise GenerationError(
                        "空响应", provider_type=provider_name
                    )
                return result
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    log.warning(
                        f"Provider '{provider_name}' 第 {attempt + 1}/{max_retries + 1} 次请求失败: {e}，"
                        f"将在 {retry_delay}s 后重试..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    log.warning(
                        f"Provider '{provider_name}' 经过 {max_retries + 1} 次尝试后仍然失败，准备故障转移"
                    )

        # 所有重试均失败，抛出最后一个错误
        if isinstance(last_error, GenerationError):
            raise last_error
        raise GenerationError(
            f"重试 {max_retries} 次后仍然失败: {last_error}",
            provider_type=provider_name,
            original_error=last_error,
        )

    async def _retry_generate_with_tools(
        self,
        provider: BaseProvider,
        messages: List[Dict[str, Any]],
        config: GenerationConfig,
        tools: Optional[List[Any]],
        model: str,
        provider_name: str,
        tool_executor: Optional[Any] = None,
        max_iterations: int = 5,
        **kwargs,
    ) -> GenerationResult:
        """
        带重试逻辑的工具调用生成方法

        在故障转移前，先对同一 Provider 重试指定次数。

        Args:
            provider: Provider 实例
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表
            model: 实际模型名称
            provider_name: Provider 名称（用于日志）
            tool_executor: 工具执行函数
            max_iterations: 最大迭代次数
            **kwargs: 其他参数

        Returns:
            GenerationResult: 生成结果

        Raises:
            GenerationError: 所有重试均失败时抛出
            Exception: 其他未预期的异常
        """
        max_retries = PROVIDER_RETRY_CONFIG["MAX_RETRIES"]
        retry_delay = PROVIDER_RETRY_CONFIG["RETRY_DELAY_SECONDS"]
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                result = await provider.generate_with_tools(
                    messages=messages,
                    config=config,
                    tools=tools,
                    tool_executor=tool_executor,
                    max_iterations=max_iterations,
                    model=model,
                    **kwargs,
                )
                if not result.content:
                    raise GenerationError(
                        "空响应", provider_type=provider_name
                    )
                return result
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    log.warning(
                        f"Provider '{provider_name}' 第 {attempt + 1}/{max_retries + 1} 次工具调用请求失败: {e}，"
                        f"将在 {retry_delay}s 后重试..."
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    log.warning(
                        f"Provider '{provider_name}' 经过 {max_retries + 1} 次尝试后仍然失败，准备故障转移"
                    )

        # 所有重试均失败，抛出最后一个错误
        if isinstance(last_error, GenerationError):
            raise last_error
        raise GenerationError(
            f"重试 {max_retries} 次后仍然失败: {last_error}",
            provider_type=provider_name,
            original_error=last_error,
        )

    async def _fallback_generate(
        self,
        messages: List[Dict[str, Any]],
        config: GenerationConfig,
        tools: Optional[List[Any]],
        failed_provider: str,
        original_error: Exception,
        model: Optional[str] = None,
        tool_executor: Optional[Any] = None,
        max_iterations: int = 5,
        user_id_for_settings: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        故障转移生成

        Args:
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表（原始格式，可能不兼容故障转移 Provider）
            failed_provider: 失败的 Provider 名称
            original_error: 原始错误
            model: 原始模型名称
            tool_executor: 工具执行函数
            max_iterations: 最大迭代次数
            user_id_for_settings: 用于重新获取工具的用户 ID
            **kwargs: 其他参数

        Returns:
            GenerationResult: 生成结果
        """
        fallback_providers = get_fallback_providers(failed_provider)

        if not fallback_providers:
            log.warning(f"Provider '{failed_provider}' 没有配置故障转移选项")
            raise GenerationError(
                f"生成失败且无可用故障转移: {original_error}",
                provider_type=failed_provider,
                original_error=original_error,
            )

        tried_providers = {failed_provider}
        last_error = original_error

        for fallback_name in fallback_providers:
            if fallback_name in tried_providers:
                continue

            if fallback_name not in self._providers:
                continue

            provider = self._providers[fallback_name]

            # 检查 Provider 是否可用
            if not await provider.is_available():
                log.warning(f"故障转移 Provider '{fallback_name}' 不可用")
                continue

            tried_providers.add(fallback_name)

            log.info(f"尝试故障转移到 Provider '{fallback_name}'")

            # 故障转移时需要重新预处理图片（不同 Provider 可能需要不同处理）
            fallback_messages = await self._preprocess_messages_for_vision(
                messages, provider, **kwargs
            )

            try:
                # 使用故障转移 Provider 的默认模型
                fallback_model = (
                    provider.supported_models[0] if provider.supported_models else None
                )

                # 根据 fallback provider 类型重新获取工具（解决格式不兼容问题）
                fallback_tools = None
                log.debug(
                    f"故障转移工具检查: tool_executor={tool_executor is not None}, "
                    f"tool_service={self._tool_service is not None}, "
                    f"user_id={user_id_for_settings}"
                )
                # 注意：user_id_for_settings 可以为 None，此时 get_dynamic_tools_for_context
                # 会返回默认工具集（只应用全局设置，不过滤用户特定设置）
                if tool_executor and self._tool_service:
                    try:
                        fallback_provider_type = provider.provider_type
                        fallback_tools = (
                            await self._tool_service.get_dynamic_tools_for_context(
                                user_id_for_settings, provider_type=fallback_provider_type
                            )
                        )
                        log.info(
                            f"故障转移时为 Provider '{fallback_name}' 重新获取了 {len(fallback_tools)} 个工具 "
                            f"(user_id={user_id_for_settings or '默认'})"
                        )
                    except Exception as tool_error:
                        log.warning(
                            f"故障转移时获取工具失败，将不使用工具: {tool_error}"
                        )
                        fallback_tools = None
                else:
                    log.info(
                        f"故障转移时不使用工具: tool_executor={tool_executor is not None}, "
                        f"tool_service={self._tool_service is not None}"
                    )

                if tool_executor and fallback_tools:
                    # 使用重新获取的工具调用 generate_with_tools
                    result = await provider.generate_with_tools(
                        messages=fallback_messages,
                        config=config,
                        tools=fallback_tools,
                        tool_executor=tool_executor,
                        max_iterations=max_iterations,
                        model=fallback_model,
                        **kwargs,
                    )
                else:
                    # 没有工具或工具获取失败，直接生成
                    result = await provider.generate(
                        messages=fallback_messages,
                        config=config,
                        tools=None,
                        model=fallback_model,
                        **kwargs,
                    )

                if not result.content:
                    raise GenerationError(
                        "故障转移后仍为空响应", provider_type=fallback_name
                    )

                log.info(f"故障转移到 Provider '{fallback_name}' 成功")
                return result

            except Exception as e:
                log.warning(f"故障转移 Provider '{fallback_name}' 失败: {e}")
                last_error = e
                continue

        # 所有故障转移都失败
        raise GenerationError(
            f"所有 Provider 均失败。最后错误: {last_error}",
            provider_type=failed_provider,
            original_error=last_error,
        )

    async def generate_embedding(
        self, text: str, model: Optional[str] = None, **kwargs
    ) -> Optional[List[float]]:
        """
        生成文本的向量嵌入

        Args:
            text: 要嵌入的文本
            model: 模型名称（可选）
            **kwargs: 其他参数

        Returns:
            Optional[List[float]]: 嵌入向量
        """
        # 优先使用 Gemini Provider 生成嵌入
        gemini_provider = self._providers.get("gemini_official")
        if gemini_provider and await gemini_provider.is_available():
            return await gemini_provider.generate_embedding(text, **kwargs)

        # 尝试其他 Provider
        for provider_name, provider in self._providers.items():
            if await provider.is_available():
                result = await provider.generate_embedding(text, **kwargs)
                if result is not None:
                    return result

        log.warning("没有可用的 Provider 生成嵌入")
        return None

    async def _preprocess_messages_for_vision(
        self,
        messages: List[Dict[str, Any]],
        provider: BaseProvider,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        预处理消息中的图片内容

        对于不支持视觉的 Provider：
        - 如果 enable_vision=True（如投喂功能）：使用 Ollama Vision 将图片转换为文字描述
        - 如果 enable_vision=False（如普通对话）：直接用占位符替换图片，不进行视觉转译

        Args:
            messages: 对话消息列表
            provider: 目标 Provider
            **kwargs: 其他参数
                - enable_vision: 是否启用视觉转译（默认 False，仅投喂等特殊功能需要启用）
                - vision_prompt: 自定义图片描述提示词

        Returns:
            处理后的消息列表
        """
        # 如果 Provider 支持视觉，直接返回原消息
        if getattr(provider, "supports_vision", False):
            return messages

        # 获取是否启用视觉转译参数（默认关闭以节省内存）
        enable_vision = kwargs.get("enable_vision", False)

        # 检查消息中是否有图片内容
        # 支持两种格式：
        # 1. 内部格式: {"type": "image", "image_bytes": ..., "mime_type": ...}
        # 2. OpenAI 格式: {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
        has_image = False
        for message in messages:
            content = message.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "image":
                            has_image = True
                            break
                        elif part.get("type") == "image_url":
                            has_image = True
                            break
            if has_image:
                break

        # 如果没有图片，直接返回
        if not has_image:
            return messages

        # 根据 enable_vision 参数决定处理方式
        if enable_vision:
            log.info(
                "[AIService] 检测到图片内容，Provider 不支持视觉，使用 Ollama Vision 转换"
            )
            from src.chat.services.ollama_vision_service import ollama_vision_service as _ollama_vision_service
        else:
            _ollama_vision_service = None
            log.info(
                "[AIService] 检测到图片内容，Provider 不支持视觉，使用占位符替换（节省内存）"
            )

        # 处理每条消息
        processed_messages = []
        for message in messages:
            content = message.get("content")
            role = message.get("role", "user")

            if isinstance(content, list):
                # 处理多部分内容
                text_parts = []
                image_descriptions = []

                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            text_parts.append(part.get("text", ""))
                        elif part.get("type") == "image":
                            # 内部格式：直接使用 image_bytes
                            source = part.get("source", "unknown")

                            if enable_vision:
                                assert _ollama_vision_service is not None
                                image_bytes = part.get("image_bytes")
                                mime_type = part.get("mime_type", "image/png")

                                if image_bytes:
                                    # 获取自定义提示词或使用默认
                                    vision_prompt = kwargs.get("vision_prompt")
                                    try:
                                        if vision_prompt:
                                            description = await _ollama_vision_service.describe_image(
                                                image_bytes, vision_prompt, mime_type
                                            )
                                        else:
                                            description = await _ollama_vision_service.describe_image(
                                                image_bytes,
                                                "请用中文描述这张图片的内容。",
                                                mime_type,
                                            )

                                        if description:
                                            image_descriptions.append(
                                                f"[图片内容: {description}]"
                                            )
                                            log.debug(
                                                f"图片描述: {description[:100]}..."
                                            )
                                        else:
                                            image_descriptions.append(
                                                "[图片内容: 无法识别]"
                                            )
                                    except Exception as e:
                                        log.error(f"Ollama Vision 处理图片失败: {e}")
                                        image_descriptions.append(
                                            "[图片内容: 处理失败]"
                                        )
                            else:
                                # 不启用视觉转译时，根据 source 进行不同处理
                                if source == "emoji":
                                    # 表情包：直接过滤，不添加任何占位符
                                    pass
                                elif source == "sticker":
                                    # 贴纸：直接过滤，不添加任何占位符
                                    pass
                                else:
                                    # 附件图片：替换为占位符
                                    image_descriptions.append(
                                        "[图片: 当前类脑娘无法识别]"
                                    )

                        elif part.get("type") == "image_url":
                            # OpenAI 格式：从 data URL 中提取 base64 图片
                            source = part.get("source", "unknown")

                            if enable_vision:
                                assert _ollama_vision_service is not None
                                import base64

                                image_url_data = part.get("image_url", {})
                                url = image_url_data.get("url", "")

                                if url.startswith("data:"):
                                    # 解析 data URL: data:image/png;base64,xxxxx
                                    try:
                                        # 提取 MIME 类型和 base64 数据
                                        header, base64_data = url.split(",", 1)
                                        # header 格式: data:image/png;base64
                                        mime_match = header.split(":")[1].split(";")[0]
                                        mime_type = (
                                            mime_match
                                            if mime_match.startswith("image/")
                                            else "image/png"
                                        )

                                        # 解码 base64
                                        image_bytes = base64.b64decode(base64_data)

                                        # 获取自定义提示词或使用默认
                                        vision_prompt = kwargs.get("vision_prompt")
                                        if vision_prompt:
                                            description = await _ollama_vision_service.describe_image(
                                                image_bytes, vision_prompt, mime_type
                                            )
                                        else:
                                            description = await _ollama_vision_service.describe_image(
                                                image_bytes,
                                                "请用中文描述这张图片的内容。",
                                                mime_type,
                                            )

                                        if description:
                                            image_descriptions.append(
                                                f"[图片内容: {description}]"
                                            )
                                            log.debug(
                                                f"图片描述: {description[:100]}..."
                                            )
                                        else:
                                            image_descriptions.append(
                                                "[图片内容: 无法识别]"
                                            )
                                    except Exception as e:
                                        log.error(
                                            f"解析或处理 OpenAI 格式图片失败: {e}"
                                        )
                                        image_descriptions.append(
                                            "[图片内容: 处理失败]"
                                        )
                            else:
                                # 不启用视觉转译时，根据 source 进行不同处理
                                if source == "emoji":
                                    # 表情包：直接过滤，不添加任何占位符
                                    pass
                                elif source == "sticker":
                                    # 贴纸：直接过滤，不添加任何占位符
                                    pass
                                else:
                                    # 附件图片：替换为占位符
                                    image_descriptions.append(
                                        "[图片: 当前类脑娘无法识别]"
                                    )

                # 合并文本和图片描述
                final_text = "\n".join(text_parts)
                if image_descriptions:
                    final_text += "\n" + "\n".join(image_descriptions)

                processed_messages.append(
                    {
                        "role": role,
                        "content": final_text,
                    }
                )
            else:
                # 非多部分内容，直接保留
                processed_messages.append(message)

        return processed_messages

    def _get_default_model(self) -> str:
        """获取默认模型名称"""
        if self._default_provider:
            provider = self._providers.get(self._default_provider)
            if provider and provider.supported_models:
                return provider.supported_models[0]
        return "gemini-2.5-flash"

    def _log_full_context_if_enabled(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]],
        model_name: str,
    ) -> None:
        """
        如果启用了 LOG_AI_FULL_CONTEXT，则记录完整的 AI 上下文日志

        Args:
            messages: 对话消息列表
            tools: 工具列表
            model_name: 模型名称
        """
        # 检查是否启用完整上下文日志
        log_full_context = os.getenv("LOG_AI_FULL_CONTEXT", "False").lower() == "true"
        if not log_full_context:
            return

        log.info(f"--- AI 完整上下文 (模型: {model_name}) ---")

        # 记录消息
        log.info("Messages:")
        log.info(
            json.dumps(
                self._serialize_for_logging(messages), ensure_ascii=False, indent=2
            )
        )

        # 记录工具（如果有）- 只显示工具名称，不显示完整定义
        if tools:
            tool_names = []
            for tool in tools:
                # Gemini 格式: types.Tool 有 function_declarations 属性
                if hasattr(tool, "function_declarations"):
                    for decl in tool.function_declarations:
                        tool_names.append(decl.name)
                # OpenAI 格式: dict 有 type 和 function
                elif isinstance(tool, dict):
                    if tool.get("type") == "function" and "function" in tool:
                        tool_names.append(tool["function"].get("name", "unknown"))
                    elif "name" in tool:
                        tool_names.append(tool["name"])
                # 其他格式：尝试获取 name 属性
                elif hasattr(tool, "name"):
                    tool_names.append(tool.name)

            log.info(f"Tools ({len(tool_names)} 个): {', '.join(tool_names)}")

        log.info("------------------------------------")

    @staticmethod
    def _serialize_for_logging(obj: Any, _seen: Optional[set] = None) -> Any:
        """
        递归序列化对象用于日志输出，防止循环引用

        Args:
            obj: 要序列化的对象
            _seen: 已处理对象 ID 集合（用于防止循环引用）

        Returns:
            可 JSON 序列化的对象
        """
        if _seen is None:
            _seen = set()

        # 防止循环引用
        obj_id = id(obj)
        if obj_id in _seen:
            return "<circular reference>"

        # 处理基本类型（直接可 JSON 序列化）
        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj

        # 处理函数/方法/类等不可序列化的对象
        if callable(obj):
            return f"<{type(obj).__name__}: {getattr(obj, '__name__', str(obj))}>"

        if isinstance(obj, dict):
            _seen.add(obj_id)
            return {
                k: AIService._serialize_for_logging(v, _seen) for k, v in obj.items()
            }
        elif isinstance(obj, (list, tuple)):
            _seen.add(obj_id)
            return [AIService._serialize_for_logging(item, _seen) for item in obj]
        elif isinstance(obj, bytes):
            return f"<bytes: {len(obj)} bytes>"
        elif hasattr(obj, "__dict__"):
            # 特殊处理 PIL Image 对象，只显示摘要信息
            try:
                from PIL import Image as PILImage

                if isinstance(obj, PILImage.Image):
                    return f"<PIL.Image: {obj.size[0]}x{obj.size[1]} {obj.mode} {obj.format or 'unknown'}>"
            except ImportError:
                pass

            _seen.add(obj_id)
            return {
                k: AIService._serialize_for_logging(v, _seen)
                for k, v in vars(obj).items()
            }
        else:
            # 其他类型转为字符串
            return f"<{type(obj).__name__}: {str(obj)}>"

    def is_available(self) -> bool:
        """检查是否有可用的 Provider"""
        return len(self._providers) > 0

    def get_available_models(self) -> List[str]:
        """获取所有可用的模型列表"""
        return list(self._model_to_provider.keys())

    def get_available_providers(self) -> List[str]:
        """获取所有可用的 Provider 列表"""
        return list(self._providers.keys())

    async def close(self):
        """关闭所有 Provider"""
        for provider in self._providers.values():
            await provider.close()


# 全局实例
ai_service = AIService()
