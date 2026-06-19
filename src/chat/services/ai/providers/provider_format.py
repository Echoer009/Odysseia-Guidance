# -*- coding: utf-8 -*-
"""
Provider 格式常量 - 统一管理不同 Provider 的消息/工具格式

这个模块解决了 Provider 类型字符串散落在多处的问题，
提供统一的格式判断和转换入口。
"""

from enum import Enum
from typing import Dict, Set


class MessageFormat(Enum):
    """消息格式类型"""

    GEMINI = "gemini"  # Gemini 原生格式 (parts, role: model)
    OPENAI = "openai"  # OpenAI 兼容格式 (content, role: assistant)


class ProviderFormat:
    """
    Provider 格式映射工具类

    统一管理 Provider 类型到消息格式、工具格式的映射，
    避免在代码中散落硬编码的 Provider 类型判断。

    使用示例:
        # 获取 Provider 的消息格式
        format = ProviderFormat.get_message_format("deepseek")
        if format == MessageFormat.OPENAI:
            # 使用 OpenAI 格式构建消息
            ...

        # 检查是否是 Gemini Provider
        if ProviderFormat.is_gemini_provider(provider_type):
            ...
    """

    # Provider 类型到消息格式的映射
    _MESSAGE_FORMAT_MAP = {
        # Gemini 系列 - 使用 Gemini 原生格式
        "gemini_official": MessageFormat.GEMINI,
        "gemini_custom": MessageFormat.GEMINI,
        # OpenAI 兼容系列 - 使用 OpenAI 格式
        "deepseek": MessageFormat.OPENAI,
        "openai_compatible": MessageFormat.OPENAI,
        "grok": MessageFormat.OPENAI,  # Grok (xAI) 走 OpenAI 兼容格式
    }

    # Gemini Provider 类型集合
    _GEMINI_PROVIDERS: Set[str] = {
        "gemini_official",
        "gemini_custom",
        "gemini",  # 通用标识
    }

    # OpenAI 兼容 Provider 类型集合
    _OPENAI_COMPATIBLE_PROVIDERS: Set[str] = {
        "deepseek",
        "openai_compatible",
        "openai",  # 通用标识
        "grok",
    }

    # 特定 Provider 需要排除的工具名集合（平台兼容性限制等）
    # 例：grok console 平台对名为 web_search 的外部工具直接返回 400，
    #     因为 grok 自身有内置 web search，禁止外部工具占用该名称
    _EXCLUDED_TOOLS_MAP: Dict[str, Set[str]] = {
        "grok": {"web_search"},
    }

    @classmethod
    def get_message_format(cls, provider_type: str) -> MessageFormat:
        """
        获取指定 Provider 的消息格式

        Args:
            provider_type: Provider 类型标识符

        Returns:
            MessageFormat: 消息格式类型，未知 Provider 默认返回 OPENAI 格式
        """
        # 首先检查是否在已知映射中
        if provider_type in cls._MESSAGE_FORMAT_MAP:
            return cls._MESSAGE_FORMAT_MAP[provider_type]
        # 然后检查是否以 gemini_ 开头（支持动态注册的自定义端点）
        if provider_type.startswith("gemini_"):
            return MessageFormat.GEMINI
        # 默认返回 OpenAI 格式
        return MessageFormat.OPENAI

    @classmethod
    def is_gemini_provider(cls, provider_type: str) -> bool:
        """
        检查是否是 Gemini 系列 Provider

        Args:
            provider_type: Provider 类型标识符

        Returns:
            bool: 是否是 Gemini Provider
        """
        # 首先检查是否在已知集合中
        if provider_type in cls._GEMINI_PROVIDERS:
            return True
        # 然后检查是否以 gemini_ 开头（支持动态注册的自定义端点）
        if provider_type.startswith("gemini_"):
            return True
        return False

    @classmethod
    def is_openai_compatible_provider(cls, provider_type: str) -> bool:
        """
        检查是否是 OpenAI 兼容系列 Provider

        Args:
            provider_type: Provider 类型标识符

        Returns:
            bool: 是否是 OpenAI 兼容 Provider
        """
        return provider_type in cls._OPENAI_COMPATIBLE_PROVIDERS

    @classmethod
    def is_grok_provider(cls, provider_type: str) -> bool:
        """
        检查是否是 Grok (xAI) 系列 Provider

        Args:
            provider_type: Provider 类型标识符

        Returns:
            bool: 是否是 Grok Provider
        """
        return provider_type.lower() == "grok"

    @classmethod
    def get_excluded_tools(cls, provider_type: str) -> Set[str]:
        """
        获取指定 Provider 需要排除（不传给 AI）的工具名集合。

        某些平台对特定工具名/功能有限制（如 grok console 对 web_search 拦截），
        调用方应在构建工具列表时据此过滤。

        Args:
            provider_type: Provider 类型标识符

        Returns:
            Set[str]: 需要排除的工具名集合，无限制时返回空集合
        """
        return cls._EXCLUDED_TOOLS_MAP.get(provider_type.lower(), set())

    @classmethod
    def register_provider(
        cls, provider_type: str, message_format: MessageFormat
    ) -> None:
        """
        注册新的 Provider 类型

        用于动态添加新的 Provider，支持扩展

        Args:
            provider_type: Provider 类型标识符
            message_format: 消息格式类型
        """
        cls._MESSAGE_FORMAT_MAP[provider_type] = message_format

        if message_format == MessageFormat.GEMINI:
            cls._GEMINI_PROVIDERS.add(provider_type)
        elif message_format == MessageFormat.OPENAI:
            cls._OPENAI_COMPATIBLE_PROVIDERS.add(provider_type)

    @classmethod
    def get_all_gemini_providers(cls) -> Set[str]:
        """获取所有 Gemini Provider 类型"""
        return cls._GEMINI_PROVIDERS.copy()

    @classmethod
    def get_all_openai_compatible_providers(cls) -> Set[str]:
        """获取所有 OpenAI 兼容 Provider 类型"""
        return cls._OPENAI_COMPATIBLE_PROVIDERS.copy()
