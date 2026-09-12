# -*- coding: utf-8 -*-
"""
AI Provider 基类 - 定义所有 AI 服务提供者的统一接口
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


class FinishReason(Enum):
    """生成结束原因"""

    STOP = "stop"  # 正常结束
    MAX_TOKENS = "max_tokens"  # 达到最大 token 限制
    SAFETY = "safety"  # 被安全过滤器阻止
    TOOL_CALL = "tool_call"  # 需要工具调用
    MAX_ITERATIONS = "max_iterations"  # 达到最大迭代次数
    ERROR = "error"  # 发生错误
    UNKNOWN = "unknown"  # 未知原因


@dataclass
class GenerationResult:
    """
    AI 生成结果的标准数据类

    Attributes:
        content: 生成的文本内容
        model_used: 实际使用的模型名称
        tokens_used: 使用的 token 数量（可选）
        input_tokens: 输入 token 数量（可选）
        output_tokens: 输出 token 数量（可选）
        finish_reason: 生成结束原因
        tool_calls: 工具调用列表（如果有）
        thinking_content: 思考链内容（如果有）
        raw_response: 原始响应对象（用于调试）
    """

    content: str
    model_used: str
    tokens_used: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    finish_reason: FinishReason = FinishReason.STOP
    tool_calls: Optional[List[Dict[str, Any]]] = None
    thinking_content: Optional[str] = None
    raw_response: Optional[Any] = None

    @property
    def has_tool_calls(self) -> bool:
        """检查是否有工具调用"""
        return bool(self.tool_calls)


@dataclass
class GenerationConfig:
    """
    生成配置数据类

    Attributes:
        temperature: 温度参数，控制随机性
        top_p: Top-p 采样参数
        top_k: Top-k 采样参数
        max_output_tokens: 最大输出 token 数
        presence_penalty: 存在惩罚
        frequency_penalty: 频率惩罚
        stop_sequences: 停止序列
        response_format: 响应格式（如 JSON）
        thinking_budget_tokens: 思考链 token 预算（Gemini 专用）
    """

    temperature: float = 1.0
    top_p: float = 0.95
    top_k: Optional[int] = None  # 仅 Gemini/Anthropic 支持，DeepSeek/OpenAI 不支持
    max_output_tokens: int = 6000
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    response_format: Optional[Dict[str, Any]] = None
    thinking_budget_tokens: Optional[int] = None  # Gemini thinking config

    def to_gemini_config(self) -> Dict[str, Any]:
        """转换为 Gemini API 配置格式"""
        config: Dict[str, Any] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_output_tokens": self.max_output_tokens,
        }
        # top_k 仅在设置时添加（Gemini/Anthropic 支持）
        if self.top_k is not None:
            config["top_k"] = self.top_k
        if self.stop_sequences:
            config["stop_sequences"] = self.stop_sequences
        if self.response_format:
            config["response_modalities"] = ["TEXT"]
        return config

    def to_openai_config(self) -> Dict[str, Any]:
        """转换为 OpenAI API 配置格式"""
        config = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_output_tokens,
        }
        if self.presence_penalty is not None:
            config["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            config["frequency_penalty"] = self.frequency_penalty
        if self.stop_sequences:
            config["stop"] = self.stop_sequences
        if self.response_format:
            config["response_format"] = self.response_format
        return config


@dataclass
class ToolCall:
    """
    工具调用数据类

    Attributes:
        id: 工具调用 ID
        name: 工具名称
        arguments: 工具参数
    """

    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ProviderInfo:
    """
    Provider 信息数据类

    Attributes:
        name: Provider 名称
        provider_type: Provider 类型标识
        supported_models: 支持的模型列表
        supports_vision: 是否支持视觉
        supports_tools: 是否支持工具调用
        supports_thinking: 是否支持思考链
    """

    name: str
    provider_type: str
    supported_models: List[str] = field(default_factory=list)
    supports_vision: bool = False
    supports_tools: bool = True
    supports_thinking: bool = False


class BaseProvider(ABC):
    """
    AI 服务提供者抽象基类

    所有 AI 服务提供者（Gemini、DeepSeek、OpenAI 兼容等）都需要继承此类并实现其抽象方法。
    """

    provider_type: str = "base"
    supported_models: List[str] = []
    supports_vision: bool = False
    supports_tools: bool = True
    supports_thinking: bool = False

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        tools: Optional[List[Any]] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        生成 AI 回复

        Args:
            messages: 对话消息列表，格式为 [{"role": "user/assistant", "content": "..."}]
            config: 生成配置
            tools: 工具列表（可选）
            **kwargs: 其他参数

        Returns:
            GenerationResult: 生成结果
        """
        pass

    @abstractmethod
    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        tools: Optional[List[Any]] = None,
        tool_executor: Optional[Any] = None,
        max_iterations: int = 25,
        **kwargs,
    ) -> GenerationResult:
        """
        带工具调用支持的生成方法

        Args:
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表
            tool_executor: 工具执行函数
            max_iterations: 最大工具调用迭代次数
            **kwargs: 其他参数

        Returns:
            GenerationResult: 最终生成结果
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        检查服务是否可用

        Returns:
            bool: 服务是否可用
        """
        pass

    @abstractmethod
    def get_client(self) -> Any:
        """
        获取底层客户端对象

        用于需要直接访问客户端的高级功能（如流式响应、工具调用等）

        Returns:
            Any: 底层客户端对象
        """
        pass

    @abstractmethod
    async def generate_embedding(self, text: str, **kwargs) -> Optional[List[float]]:
        """
        生成文本的向量嵌入

        Args:
            text: 要嵌入的文本
            **kwargs: 其他参数

        Returns:
            Optional[List[float]]: 嵌入向量，如果不支持则返回 None
        """
        pass

    def get_info(self) -> ProviderInfo:
        """
        获取 Provider 信息

        Returns:
            ProviderInfo: Provider 信息对象
        """
        return ProviderInfo(
            name=self.__class__.__name__,
            provider_type=self.provider_type,
            supported_models=self.supported_models,
            supports_vision=self.supports_vision,
            supports_tools=self.supports_tools,
            supports_thinking=self.supports_thinking,
        )

    def supports_model(self, model_name: str) -> bool:
        """
        检查是否支持指定模型

        Args:
            model_name: 模型名称

        Returns:
            bool: 是否支持该模型
        """
        return model_name in self.supported_models

    async def close(self):
        """
        关闭 Provider，释放资源

        子类可以覆盖此方法以执行清理操作
        """
        pass


class AIServiceError(Exception):
    """AI 服务错误基类"""

    pass


class ProviderNotAvailableError(AIServiceError):
    """Provider 不可用错误"""

    pass


class ModelNotSupportedError(AIServiceError):
    """模型不支持错误"""

    pass


class GenerationError(AIServiceError):
    """生成错误"""

    def __init__(
        self,
        message: str,
        provider_type: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ):
        self.provider_type = provider_type
        self.original_error = original_error
        super().__init__(message)
