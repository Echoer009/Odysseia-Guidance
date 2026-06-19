# -*- coding: utf-8 -*-
"""
DeepSeek Provider - 支持 DeepSeek API

DeepSeek API 兼容 OpenAI 格式，支持：
- deepseek-chat: 对话模型
- deepseek-reasoner: 推理模型（R1），支持思考链
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List

import httpx

from .base import (
    BaseProvider,
    GenerationConfig,
    GenerationResult,
    FinishReason,
    ProviderNotAvailableError,
    GenerationError,
)
from ..utils.tool_converter import ToolConverter

log = logging.getLogger(__name__)


class DeepSeekProvider(BaseProvider):
    """
    DeepSeek API Provider

    支持：
    - deepseek-chat: 标准对话模型，支持工具调用
    - deepseek-reasoner: 推理模型（R1），支持思考链但不支持工具调用
    """

    provider_type = "deepseek"
    supported_models = [
        "deepseek-chat",
        "deepseek-reasoner",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ]
    supports_vision = False
    supports_tools = True  # deepseek-chat 支持工具调用
    supports_thinking = True  # deepseek-reasoner 支持思考链

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider_name: str = "deepseek",
    ):
        """
        初始化 DeepSeek Provider

        Args:
            api_key: DeepSeek API 密钥
            base_url: API 基础 URL（可选，默认为官方 API）
            provider_name: Provider 名称标识
        """
        self.provider_name = provider_name
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )
        self._client: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            log.warning(f"DeepSeekProvider '{provider_name}' 未配置 API 密钥")
        else:
            log.info(f"DeepSeekProvider '{provider_name}' 初始化完成")

    def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=120.0,
            )
        return self._client

    def get_client(self) -> Any:
        """获取底层客户端对象"""
        return self._get_client()

    async def is_available(self) -> bool:
        """检查服务是否可用"""
        return bool(self.api_key)

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        tools: Optional[List[Any]] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        生成 AI 回复

        Args:
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表（ToolDeclaration 列表）
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            GenerationResult: 生成结果
        """
        if not self.api_key:
            raise ProviderNotAvailableError("未配置 DeepSeek API 密钥")

        config = config or GenerationConfig()
        model_name = model or "deepseek-chat"

        # deepseek-reasoner 不支持工具调用
        if model_name == "deepseek-reasoner" and tools:
            log.warning("deepseek-reasoner 不支持工具调用，将忽略工具配置")
            tools = None

        try:
            client = self._get_client()

            # 构建请求体
            request_body = self._build_request_body(messages, config, tools, model_name)

            # 调用 API
            response = await client.post(
                "/v1/chat/completions",
                json=request_body,
            )
            response.raise_for_status()

            result_data = response.json()

            # 处理响应
            return self._process_response(result_data, model_name)

        except httpx.HTTPStatusError as e:
            log.error(f"DeepSeek API HTTP 错误: {e}")
            raise GenerationError(
                f"DeepSeek API 错误: {e.response.text}",
                provider_type=self.provider_type,
                original_error=e,
            )
        except httpx.RequestError as e:
            log.error(f"DeepSeek API 请求错误: {e}")
            raise GenerationError(
                f"DeepSeek API 请求失败: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )
        except Exception as e:
            log.error(f"DeepSeek 生成错误: {e}", exc_info=True)
            raise GenerationError(
                f"DeepSeek 生成错误: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )

    async def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        config: Optional[GenerationConfig] = None,
        tools: Optional[List[Any]] = None,
        tool_executor: Optional[Any] = None,
        max_iterations: int = 5,
        model: Optional[str] = None,
        **kwargs,
    ) -> GenerationResult:
        """
        带工具调用支持的生成方法

        Args:
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表
            tool_executor: 工具执行函数
            max_iterations: 最大迭代次数
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            GenerationResult: 最终生成结果
        """
        config = config or GenerationConfig()
        model_name = model or "deepseek-chat"

        # deepseek-reasoner 不支持工具调用
        if model_name == "deepseek-reasoner":
            log.warning("deepseek-reasoner 不支持工具调用，将直接生成回复")
            return await self.generate(messages, config, None, model_name)

        if not tools or not tool_executor:
            return await self.generate(messages, config, tools, model_name)

        conversation_history = messages.copy()
        # 收集所有工具调用，用于最终返回
        all_tool_calls = []

        try:
            for iteration in range(max_iterations):
                log.info(
                    f"DeepSeek 工具调用循环: 第 {iteration + 1}/{max_iterations} 次"
                )

                # 调用 API
                result = await self.generate(
                    messages=conversation_history,
                    config=config,
                    tools=tools,
                    model=model_name,
                )

                # 检查是否有工具调用
                if not result.has_tool_calls or not result.tool_calls:
                    # 最终返回时，附加所有收集的工具调用信息
                    if all_tool_calls:
                        return GenerationResult(
                            content=result.content,
                            model_used=result.model_used,
                            finish_reason=result.finish_reason,
                            tool_calls=all_tool_calls,
                        )
                    return result

                # 执行工具调用
                tool_calls_list = result.tool_calls
                log.info(f"DeepSeek 请求调用 {len(tool_calls_list)} 个工具")

                # 收集工具调用
                all_tool_calls.extend(tool_calls_list)

                # 将模型响应添加到对话历史
                assistant_message = {
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(
                                    call["arguments"], ensure_ascii=False
                                ),
                            },
                        }
                        for call in tool_calls_list
                    ],
                }
                if result.thinking_content:
                    assistant_message["reasoning_content"] = result.thinking_content
                conversation_history.append(assistant_message)

                # 执行工具并添加结果
                for call in tool_calls_list:
                    try:
                        tool_result = await tool_executor(call, **kwargs)
                        tool_message = ToolConverter.tool_result_to_openai_message(
                            tool_call_id=call["id"],
                            tool_name=call["name"],
                            result=tool_result,
                            is_error=isinstance(tool_result, dict)
                            and "error" in tool_result,
                        )
                        conversation_history.append(tool_message)
                    except Exception as e:
                        log.error(f"执行工具 {call['name']} 失败: {e}")
                        tool_message = ToolConverter.tool_result_to_openai_message(
                            tool_call_id=call["id"],
                            tool_name=call["name"],
                            result={"error": str(e)},
                            is_error=True,
                        )
                        conversation_history.append(tool_message)

            # 达到最大迭代次数
            log.warning(f"DeepSeek 达到最大工具调用迭代次数 {max_iterations}")
            return GenerationResult(
                content="抱歉，我在处理这个请求时遇到了一些复杂的情况，请换个方式问我。",
                model_used=model_name,
                finish_reason=FinishReason.MAX_ITERATIONS,
                tool_calls=all_tool_calls,
            )

        except Exception as e:
            log.error(f"DeepSeek 工具调用生成错误: {e}", exc_info=True)
            raise GenerationError(
                f"DeepSeek 工具调用生成错误: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )

    async def generate_embedding(self, text: str, **kwargs) -> Optional[List[float]]:
        """
        生成文本的向量嵌入

        DeepSeek 暂不支持 embedding API

        Args:
            text: 要嵌入的文本
            **kwargs: 其他参数

        Returns:
            None
        """
        log.warning("DeepSeek 暂不支持 embedding API")
        return None

    def _convert_messages_to_openai_format(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        将消息转换为 OpenAI 兼容格式

        支持多种输入格式：
        - OpenAI 格式: {"role": "user", "content": "text"}
        - Gemini 格式: {"role": "user", "parts": ["text"]} 或 {"role": "user", "parts": [{"text": "..."}]}
        - 工具调用格式: {"role": "assistant", "tool_calls": [...]}
        - 工具结果格式: {"role": "tool", "tool_call_id": "...", "content": "..."}
        - Gemini 原生对象: genai_types.Content（包含 function_call / function_response）

        Args:
            messages: 消息列表
        Returns:
            List[Dict]: OpenAI 兼容格式的消息列表
        """
        converted_messages = []

        for msg in messages:
            # 处理 Gemini 原生 Content 对象（genai_types.Content）
            if hasattr(msg, "role") and hasattr(msg, "parts"):
                converted = self._convert_gemini_content_object(msg)
                if converted:
                    converted_messages.append(converted)
                continue

            role = msg.get("role", "user")
            content = msg.get("content")
            parts = msg.get("parts")
            tool_calls = msg.get("tool_calls")
            tool_call_id = msg.get("tool_call_id")
            name = msg.get("name")
            # 转换角色 (model -> assistant)
            openai_role = "assistant" if role == "model" else role

            # 1. 处理工具结果消息 (role == "tool")
            if openai_role == "tool" and tool_call_id:
                tool_msg: Dict[str, Any] = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": content
                    if isinstance(content, str)
                    else json.dumps(content, ensure_ascii=False)
                    if content
                    else "",
                }
                if name:
                    tool_msg["name"] = name
                converted_messages.append(tool_msg)
                continue

            # 2. 处理包含工具调用的助手消息
            if tool_calls:
                assistant_msg: Dict[str, Any] = {
                    "role": "assistant",
                    "content": content if isinstance(content, str) else (content or ""),
                    "tool_calls": [],
                }
                for call in tool_calls:
                    if isinstance(call, dict):
                        # 已经是 OpenAI 格式的 tool_call
                        if "type" in call and "function" in call:
                            assistant_msg["tool_calls"].append(call)
                        # 内部格式: {"id": ..., "name": ..., "arguments": {...}}
                        elif "id" in call and "name" in call:
                            assistant_msg["tool_calls"].append(
                                {
                                    "id": call["id"],
                                    "type": "function",
                                    "function": {
                                        "name": call["name"],
                                        "arguments": json.dumps(
                                            call.get("arguments", {}),
                                            ensure_ascii=False,
                                        ),
                                    },
                                }
                            )
                        else:
                            log.warning(f"未知的 tool_call 格式: {call}")
                    else:
                        log.warning(f"非字典类型的 tool_call: {type(call)}")
                reasoning_content = msg.get("reasoning_content")
                if reasoning_content:
                    assistant_msg["reasoning_content"] = reasoning_content
                converted_messages.append(assistant_msg)
                continue

            # 3. 如果已经有 content 字段且是字符串，直接使用
            if content is not None and isinstance(content, str):
                converted_messages.append(
                    {
                        "role": openai_role,
                        "content": content,
                    }
                )
                continue

            # 4. 如果 content 是列表（OpenAI 多部分格式）
            if content is not None and isinstance(content, list):
                # 提取文本内容
                text_parts = []
                for item in content:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))

                if text_parts:
                    converted_messages.append(
                        {
                            "role": openai_role,
                            "content": "\n".join(text_parts),
                        }
                    )
                continue

            # 5. 处理 Gemini 格式 (parts 字段)
            if parts is not None:
                text_parts = []
                if isinstance(parts, list):
                    for item in parts:
                        if isinstance(item, str):
                            if item:  # 跳过空字符串
                                text_parts.append(item)
                        elif isinstance(item, dict) and "text" in item:
                            text = item["text"]
                            if text:
                                text_parts.append(text)
                elif isinstance(parts, str):
                    if parts:
                        text_parts.append(parts)

                if text_parts:
                    converted_messages.append(
                        {
                            "role": openai_role,
                            "content": "\n".join(text_parts),
                        }
                    )
                else:
                    # 如果 parts 为空，添加一个空内容消息以避免 API 错误
                    log.warning(f"消息 parts 为空，将使用占位符内容: {msg}")
                    converted_messages.append(
                        {
                            "role": openai_role,
                            "content": " ",  # 使用空格作为占位符
                        }
                    )
                continue

            # 6. 如果既没有 content 也没有 parts，记录警告并添加占位符
            log.warning(f"消息缺少 content 和 parts 字段: {msg}")
            converted_messages.append(
                {
                    "role": openai_role,
                    "content": " ",  # 使用空格作为占位符
                }
            )

        return converted_messages

    def _convert_gemini_content_object(
        self, content_obj: Any
    ) -> Optional[Dict[str, Any]]:
        """
        将 Gemini 原生 Content 对象 (genai_types.Content) 转换为 OpenAI 消息格式

        处理以下情况：
        - 包含 function_call 的 Content → assistant 消息 + tool_calls
        - 包含 function_response 的 Content → tool 消息
        - 包含纯文本的 Content → assistant/user 消息

        Args:
            content_obj: Gemini genai_types.Content 对象

        Returns:
            Optional[Dict]: OpenAI 格式的消息，如果无法转换则返回 None
        """
        try:
            from google.genai import types as genai_types

            role = getattr(content_obj, "role", "user")
            openai_role = "assistant" if role == "model" else role
            parts = getattr(content_obj, "parts", [])

            if not parts:
                return None

            # 检查是否包含 function_call
            function_calls = []
            text_parts = []
            for part in parts:
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    call_id = getattr(fc, "id", None) or f"call_{id(fc)}"
                    function_calls.append(
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": fc.name,
                                "arguments": json.dumps(
                                    dict(fc.args) if fc.args else {},
                                    ensure_ascii=False,
                                ),
                            },
                        }
                    )
                elif hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    # function_response 需要转换为 tool 消息
                    # 注意：一个 Content 可能包含多个 function_response
                    # 但 OpenAI 格式每条消息只能有一个 tool_call_id
                    response_content = json.dumps(
                        dict(fr.response) if fr.response else {},
                        ensure_ascii=False,
                    )
                    return {
                        "role": "tool",
                        "tool_call_id": getattr(fr, "id", None) or f"call_{id(fr)}",
                        "name": fr.name,
                        "content": response_content,
                    }
                elif hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

            # 如果有 function_calls，返回带 tool_calls 的 assistant 消息
            if function_calls:
                return {
                    "role": "assistant",
                    "content": "\n".join(text_parts) if text_parts else "",
                    "tool_calls": function_calls,
                }

            # 纯文本消息
            if text_parts:
                return {
                    "role": openai_role,
                    "content": "\n".join(text_parts),
                }

            return None

        except Exception as e:
            log.warning(f"转换 Gemini Content 对象失败: {e}")
            return None

    def _build_request_body(
        self,
        messages: List[Dict[str, Any]],
        config: GenerationConfig,
        tools: Optional[List[Any]],
        model: str,
    ) -> Dict[str, Any]:
        """
        构建 API 请求体

        Args:
            messages: 对话消息列表
            config: 生成配置
            tools: 工具列表
            model: 模型名称

        Returns:
            Dict: API 请求体
        """
        # 转换消息格式为 OpenAI 兼容格式
        converted_messages = self._convert_messages_to_openai_format(messages)

        body: Dict[str, Any] = {
            "model": model,
            "messages": converted_messages,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_output_tokens,
        }

        # 添加频率和存在惩罚
        if config.frequency_penalty is not None:
            body["frequency_penalty"] = config.frequency_penalty
        if config.presence_penalty is not None:
            body["presence_penalty"] = config.presence_penalty

        # 添加停止序列
        if config.stop_sequences:
            body["stop"] = config.stop_sequences

        # 添加工具
        # 工具格式由 ToolService.get_dynamic_tools_for_context() 统一转换
        # DeepSeek Provider 接收 OpenAI 格式的工具列表
        if tools:
            body["tools"] = tools

        return body

    def _process_response(
        self, response_data: Dict[str, Any], model_name: str
    ) -> GenerationResult:
        """
        处理 API 响应

        Args:
            response_data: API 响应数据
            model_name: 模型名称

        Returns:
            GenerationResult: 生成结果
        """
        choices = response_data.get("choices", [])
        if not choices:
            return GenerationResult(
                content="",
                model_used=model_name,
                finish_reason=FinishReason.ERROR,
            )

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        # 提取思考链内容（deepseek-reasoner / deepseek-v4-pro / deepseek-v4-flash 均可能返回）
        thinking_content = None
        if "reasoning_content" in message:
            thinking_content = message["reasoning_content"]
            if thinking_content:
                preview = thinking_content[:200]
                log.info(
                    f"模型思考过程 ({model_name}): {preview}..."
                )
                log.debug(
                    f"模型完整思考内容 ({model_name}):\n{thinking_content}"
                )

        # 确定结束原因
        finish_reason_str = choice.get("finish_reason", "stop")
        reason_map = {
            "stop": FinishReason.STOP,
            "length": FinishReason.MAX_TOKENS,
            "content_filter": FinishReason.SAFETY,
            "tool_calls": FinishReason.TOOL_CALL,
        }
        finish_reason = reason_map.get(finish_reason_str.lower(), FinishReason.UNKNOWN)

        # 提取工具调用
        tool_calls = None
        if "tool_calls" in message:
            tool_calls = ToolConverter.parse_openai_function_calls(response_data)
            if tool_calls:
                finish_reason = FinishReason.TOOL_CALL

        # 提取 token 使用量
        usage = response_data.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        tokens_used = (input_tokens or 0) + (output_tokens or 0)

        return GenerationResult(
            content=content,
            model_used=model_name,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            thinking_content=thinking_content,
            raw_response=response_data,
        )

    async def close(self):
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
