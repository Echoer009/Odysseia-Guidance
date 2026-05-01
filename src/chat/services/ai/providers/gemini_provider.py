# -*- coding: utf-8 -*-
"""
Gemini Provider - 支持 Gemini 官方 API 和自定义端点

实现两种模式：
1. 官方 API 模式：使用密钥轮换服务
2. 自定义端点模式：直接使用指定的 API 端点
"""

import logging
import io
from typing import Optional, Dict, Any, List

from PIL import Image
from google import genai
from google.genai import types as genai_types
from google.genai import errors as genai_errors

from .base import (
    BaseProvider,
    GenerationConfig,
    GenerationResult,
    FinishReason,
    ProviderNotAvailableError,
    GenerationError,
)
from ..utils.tool_converter import ToolConverter
from src.chat.services.key_rotation_service import (
    KeyRotationService,
    NoAvailableKeyError,
)

log = logging.getLogger(__name__)


class GeminiProvider(BaseProvider):
    """
    Gemini API Provider

    支持：
    - Gemini 官方 API（带密钥轮换）
    - 自定义 Gemini 端点（公益站等）
    - 工具调用
    - 思考链（Thinking）
    - 视觉（图片理解）
    """

    provider_type = "gemini"
    supported_models = [
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
    ]
    supports_vision = True
    supports_tools = True
    supports_thinking = True

    # 安全惩罚映射
    SAFETY_PENALTY_MAP: Dict[str, int] = {
        "HARM_PROBABILITY_UNSPECIFIED": 0,
        "NEGLIGIBLE": 0,
        "LOW": 5,
        "MEDIUM": 15,
        "HIGH": 30,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        use_key_rotation: bool = True,
        api_keys_list: Optional[List[str]] = None,
        provider_name: str = "gemini_official",
    ):
        """
        初始化 Gemini Provider

        Args:
            api_key: API 密钥（单密钥模式）
            base_url: API 基础 URL（可选，用于代理或自定义端点）
            use_key_rotation: 是否使用密钥轮换
            api_keys_list: API 密钥列表（用于密钥轮换）
            provider_name: Provider 名称标识
        """
        self.provider_name = provider_name
        self.base_url = base_url
        self.use_key_rotation = use_key_rotation

        # 初始化密钥轮换服务
        self.key_rotation_service: Optional[KeyRotationService] = None
        self._single_api_key: Optional[str] = None

        if use_key_rotation and api_keys_list:
            self.key_rotation_service = KeyRotationService(api_keys_list)
            log.info(
                f"GeminiProvider '{provider_name}' 启用密钥轮换，共 {len(api_keys_list)} 个密钥"
            )
        elif api_key:
            self._single_api_key = api_key
            log.info(f"GeminiProvider '{provider_name}' 使用单密钥模式")
        else:
            log.warning(f"GeminiProvider '{provider_name}' 未配置 API 密钥")

        # 安全设置
        self.safety_settings = [
            genai_types.SafetySetting(
                category=genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
            ),
            genai_types.SafetySetting(
                category=genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
            ),
            genai_types.SafetySetting(
                category=genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
            ),
            genai_types.SafetySetting(
                category=genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=genai_types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]

        # 客户端缓存
        self._client_cache: Dict[str, genai.Client] = {}

    def _create_client(self, api_key: str) -> genai.Client:
        """
        创建 Gemini 客户端

        Args:
            api_key: API 密钥

        Returns:
            genai.Client: Gemini 客户端
        """
        REQUEST_TIMEOUT_MS = 40000
        if self.base_url:
            http_options = genai_types.HttpOptions(
                base_url=self.base_url, timeout=REQUEST_TIMEOUT_MS
            )
            return genai.Client(api_key=api_key, http_options=http_options)
        else:
            return genai.Client(
                api_key=api_key,
                http_options=genai_types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
            )

    def get_client(self) -> Any:
        """
        获取底层客户端对象

        如果使用密钥轮换，需要先调用 acquire_client

        Returns:
            genai.Client 或 None
        """
        if self._single_api_key:
            if self._single_api_key not in self._client_cache:
                self._client_cache[self._single_api_key] = self._create_client(
                    self._single_api_key
                )
            return self._client_cache[self._single_api_key]
        return None

    async def acquire_client(self) -> tuple[Any, Optional[str]]:
        """
        获取可用的客户端（支持密钥轮换）

        Returns:
            Tuple[genai.Client, Optional[str]]: (客户端, 密钥标识)

        Raises:
            ProviderNotAvailableError: 没有可用的密钥
        """
        if self.key_rotation_service:
            key_obj = await self.key_rotation_service.acquire_key()
            client = self._create_client(key_obj.key)
            return client, key_obj.key
        elif self._single_api_key:
            client = self.get_client()
            return client, self._single_api_key[-4:] if self._single_api_key else None
        else:
            raise ProviderNotAvailableError("未配置 API 密钥")

    async def release_client(
        self,
        api_key: Optional[str],
        success: bool = True,
        failure_penalty: int = 0,
        safety_penalty: int = 0,
    ):
        """
        释放客户端（更新密钥状态）

        Args:
            api_key: API 密钥
            success: 是否成功
            failure_penalty: 失败惩罚分数
            safety_penalty: 安全惩罚分数
        """
        if self.key_rotation_service and api_key:
            await self.key_rotation_service.release_key(
                api_key,
                success=success,
                failure_penalty=failure_penalty + safety_penalty,
            )

    async def is_available(self) -> bool:
        """检查服务是否可用"""
        if self.key_rotation_service:
            return True
        return bool(self._single_api_key)

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
        config = config or GenerationConfig()
        model_name = model or self.supported_models[0]

        client, api_key = await self.acquire_client()
        failure_penalty = 0
        safety_penalty = 0

        try:
            # 构建生成配置
            gen_config = self._build_generation_config(config)

            # 转换工具格式
            gemini_tools = None
            if tools:
                gemini_tools = ToolConverter.to_gemini_tools(tools)
                gen_config.tools = gemini_tools
                gen_config.automatic_function_calling = (
                    genai_types.AutomaticFunctionCallingConfig(disable=True)
                )

            # 转换消息格式
            contents = self._convert_messages_to_contents(messages)

            # 调用 API（流式）- 避免 Cloudflare 100 秒超时导致 524 错误
            response = await self._stream_generate(
                client, model_name, contents, gen_config
            )

            # 处理响应
            result = self._process_response(response, model_name)

            # 计算安全惩罚
            safety_penalty = self._calculate_safety_penalty(response, api_key)

            # 释放密钥
            await self.release_client(
                api_key, success=True, safety_penalty=safety_penalty
            )

            return result

        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            error_str = str(e)
            log.error(f"Gemini API 错误: {e}")

            # 判断是否可重试
            is_retryable = "429" in error_str or "503" in error_str
            if is_retryable:
                failure_penalty = 10
            elif "403" in error_str or "API_KEY_INVALID" in error_str.upper():
                failure_penalty = 101  # 毁灭性惩罚

            await self.release_client(
                api_key, success=False, failure_penalty=failure_penalty
            )
            raise GenerationError(
                f"Gemini API 错误: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )

        except Exception as e:
            log.error(f"Gemini 生成错误: {e}", exc_info=True)
            await self.release_client(api_key, success=False, failure_penalty=10)
            raise GenerationError(
                f"Gemini 生成错误: {e}",
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
        model_name = model or self.supported_models[0]

        client, api_key = await self.acquire_client()

        try:
            # 构建生成配置
            gen_config = self._build_generation_config(config)

            # 工具格式已由 ToolService.get_dynamic_tools_for_context() 统一转换
            # Gemini Provider 接收的是 List[types.Tool] 格式
            if tools:
                # 调试日志：检查传入的工具格式
                log.info(
                    f"[Gemini Provider 工具调试] 收到 {len(tools)} 个工具，"
                    f"第一个工具类型={type(tools[0]) if tools else 'N/A'}"
                )
                if tools:
                    first_tool = tools[0]
                    # 检查是否是 OpenAI 格式（字典，包含 type 和 function 键）
                    if isinstance(first_tool, dict):
                        log.warning(
                            f"[Gemini Provider 工具调试] 警告：收到的是 OpenAI 格式工具！"
                            f"工具内容: {list(first_tool.keys())}"
                        )
                    elif hasattr(first_tool, "function_declarations"):
                        log.info(
                            f"[Gemini Provider 工具调试] 正确：收到 Gemini 格式工具，"
                            f"包含 {len(first_tool.function_declarations)} 个函数声明"
                        )
                    else:
                        log.warning(
                            f"[Gemini Provider 工具调试] 警告：未知的工具格式！"
                            f"类型={type(first_tool)}"
                        )
                gen_config.tools = tools
                gen_config.automatic_function_calling = (
                    genai_types.AutomaticFunctionCallingConfig(disable=True)
                )

            # 转换消息格式
            conversation_history = self._convert_messages_to_contents(messages)

            # 工具调用循环
            thinking_content = None

            for iteration in range(max_iterations):
                log.info(f"工具调用循环: 第 {iteration + 1}/{max_iterations} 次")

                # 调用 API（流式）- 避免 Cloudflare 100 秒超时导致 524 错误
                response = await self._stream_generate(
                    client, model_name, conversation_history, gen_config
                )

                # 检查思考链
                _first_content = (
                    response.candidates[0].content
                    if response.candidates and response.candidates[0].content
                    else None
                )
                if _first_content and _first_content.parts:
                    log.debug(f"检查 {len(_first_content.parts)} 个 parts for thinking")
                    for idx, part in enumerate(_first_content.parts):
                        # 检查是否是思考部分
                        is_thought = hasattr(part, "thought") and bool(part.thought)

                        # 如果是思考部分，提取文本
                        if is_thought:
                            thinking_content = part.text
                            log.info(
                                f"模型思考过程: {thinking_content[:200] if thinking_content else 'N/A'}..."
                            )
                        else:
                            log.debug(
                                f"Part {idx}: 不是思考部分, text={part.text[:50] if hasattr(part, 'text') and part.text else 'N/A'}..."
                            )

                # 解析函数调用
                function_calls = ToolConverter.parse_gemini_function_calls(response)

                if not function_calls:
                    # 没有工具调用，返回最终结果
                    result = self._process_response(response, model_name)
                    if thinking_content:
                        result.thinking_content = thinking_content
                    await self.release_client(api_key, success=True)
                    return result

                # 有工具调用，执行工具
                log.info(f"模型请求调用 {len(function_calls)} 个工具")

                # 将模型响应添加到对话历史
                if response.candidates and response.candidates[0].content:
                    conversation_history.append(response.candidates[0].content)

                # 执行工具调用
                if tool_executor:
                    tool_results = []
                    for call in function_calls:
                        try:
                            result = await tool_executor(call, **kwargs)
                            tool_results.append(
                                ToolConverter.tool_result_to_gemini_part(
                                    call["name"],
                                    result,
                                    is_error=isinstance(result, dict)
                                    and "error" in result,
                                )
                            )
                        except Exception as e:
                            log.error(f"执行工具 {call['name']} 失败: {e}")
                            tool_results.append(
                                ToolConverter.tool_result_to_gemini_part(
                                    call["name"], {"error": str(e)}, is_error=True
                                )
                            )

                    # 将工具结果添加到对话历史
                    conversation_history.append(
                        genai_types.Content(parts=tool_results, role="user")
                    )
                else:
                    # 没有工具执行器，直接返回
                    result = self._process_response(response, model_name)
                    result.finish_reason = FinishReason.TOOL_CALL
                    result.tool_calls = function_calls
                    await self.release_client(api_key, success=True)
                    return result

            # 达到最大迭代次数
            log.warning(f"达到最大工具调用迭代次数 {max_iterations}")
            await self.release_client(api_key, success=True)
            return GenerationResult(
                content="抱歉，我在处理这个请求时遇到了一些复杂的情况，请换个方式问我。",
                model_used=model_name,
                finish_reason=FinishReason.MAX_ITERATIONS,
            )

        except Exception as e:
            log.error(f"Gemini 工具调用生成错误: {e}", exc_info=True)
            await self.release_client(api_key, success=False, failure_penalty=10)
            raise GenerationError(
                f"Gemini 工具调用生成错误: {e}",
                provider_type=self.provider_type,
                original_error=e,
            )

    async def generate_embedding(
        self, text: str, model: str = "text-embedding-004", **kwargs
    ) -> Optional[List[float]]:
        """
        生成文本的向量嵌入

        Args:
            text: 要嵌入的文本
            model: 嵌入模型名称
            **kwargs: 其他参数

        Returns:
            Optional[List[float]]: 嵌入向量
        """
        try:
            client, api_key = await self.acquire_client()

            try:
                result = await client.aio.models.embed_content(
                    model=model,
                    contents=text,
                )

                await self.release_client(api_key, success=True)

                if result.embeddings:
                    return result.embeddings[0].values
                return None

            except Exception as e:
                log.error(f"生成嵌入失败: {e}")
                await self.release_client(api_key, success=False, failure_penalty=10)
                return None

        except NoAvailableKeyError:
            log.warning("没有可用的 API 密钥用于生成嵌入")
            return None

    async def _stream_generate(
        self,
        client: Any,
        model_name: str,
        contents: List[genai_types.Content],
        gen_config: genai_types.GenerateContentConfig,
    ) -> Any:
        """
        流式调用 Gemini API 并内部拼接完整响应

        使用 generate_content_stream 替代 generate_content，
        让 HTTP 200 头先建立，避免 Cloudflare 等 CDN 的 100 秒连接超时（524 错误）。
        流式 chunk 内部拼接完成后，返回与 generate_content 相同结构的完整响应对象。

        Args:
            client: Gemini 异步客户端
            model_name: 模型名称
            contents: 对话内容
            gen_config: 生成配置

        Returns:
            GenerateContentResponse: 拼接后的完整响应（结构与非流式一致）
        """
        log.info(f"[流式] 开始流式调用 model={model_name}")

        chunks_received = 0
        accumulated_text_parts: List[genai_types.Part] = []
        accumulated_function_calls: List[Any] = []
        final_candidate: Optional[genai_types.Candidate] = None
        final_usage_metadata: Optional[Any] = None

        stream = await client.aio.models.generate_content_stream(
            model=model_name,
            contents=contents,
            config=gen_config,
        )

        async for chunk in stream:
            chunks_received += 1
            if chunks_received == 1:
                log.info("[流式] 已收到第一个 chunk，连接建立成功")

            if not chunk.candidates:
                continue

            candidate = chunk.candidates[0]
            final_candidate = candidate

            if candidate.content:
                for part in candidate.content.parts or []:
                    is_thought = hasattr(part, "thought") and part.thought
                    if is_thought:
                        continue
                    if hasattr(part, "text") and part.text:
                        accumulated_text_parts.append(part)
                    if hasattr(part, "function_call") and part.function_call:
                        accumulated_function_calls.append(part.function_call)

            if chunk.usage_metadata:
                final_usage_metadata = chunk.usage_metadata

            if hasattr(chunk, "function_calls") and chunk.function_calls:
                accumulated_function_calls = list(chunk.function_calls)

        log.info(f"[流式] 流结束，共收到 {chunks_received} 个 chunk")

        merged_parts = accumulated_text_parts[:]
        for fc in accumulated_function_calls:
            merged_parts.append(genai_types.Part(function_call=fc))

        merged_content = (
            genai_types.Content(parts=merged_parts, role="model")
            if merged_parts
            else None
        )

        if final_candidate:
            final_candidate.content = merged_content

        merged_candidates = [final_candidate] if final_candidate else []

        class _MergedResponse:
            def __init__(self, candidates, usage_metadata, function_calls):
                self.candidates = candidates
                self.usage_metadata = usage_metadata
                self._function_calls = function_calls

            @property
            def function_calls(self):
                return self._function_calls

        return _MergedResponse(
            merged_candidates, final_usage_metadata, accumulated_function_calls
        )

    def _build_generation_config(
        self, config: GenerationConfig
    ) -> genai_types.GenerateContentConfig:
        """
        构建 Gemini 生成配置

        Args:
            config: 通用生成配置

        Returns:
            genai_types.GenerateContentConfig: Gemini 生成配置
        """
        log.debug(
            f"构建 Gemini 配置: temperature={config.temperature}, "
            f"top_p={config.top_p}, top_k={config.top_k}, "
            f"max_output_tokens={config.max_output_tokens}, "
            f"thinking_budget_tokens={config.thinking_budget_tokens}"
        )

        gen_config_params: Dict[str, Any] = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_output_tokens": config.max_output_tokens,
            "safety_settings": self.safety_settings,
        }

        # top_k 仅在设置时添加（Gemini 支持）
        if config.top_k is not None:
            gen_config_params["top_k"] = config.top_k

        if config.stop_sequences:
            gen_config_params["stop_sequences"] = config.stop_sequences

        gen_config = genai_types.GenerateContentConfig(**gen_config_params)

        # 添加思考链配置
        log.debug(
            f"思考链配置检查: thinking_budget_tokens={config.thinking_budget_tokens}"
        )
        if config.thinking_budget_tokens is not None:
            gen_config.thinking_config = genai_types.ThinkingConfig(
                thinking_budget=config.thinking_budget_tokens,
                include_thoughts=True,  # 必须设置此参数才能在响应中获取思考内容
            )
            log.info(
                f"已启用思考链: thinking_budget={config.thinking_budget_tokens}, include_thoughts=True"
            )

        return gen_config

    def _convert_messages_to_contents(
        self, messages: List[Dict[str, Any]]
    ) -> List[genai_types.Content]:
        """
        将通用消息格式转换为 Gemini Contents 格式

        支持两种输入格式：
        - OpenAI 格式: {"role": "user", "content": "text"}
        - Gemini 格式: {"role": "user", "parts": ["text"]}

        Args:
            messages: 通用消息列表

        Returns:
            List[genai_types.Content]: Gemini Contents
        """
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content")
            parts_input = msg.get("parts")

            # 转换角色 (assistant -> model)
            gemini_role = (
                "model"
                if role == "assistant"
                else ("user" if role == "user" else "model")
            )

            # 构建 Parts
            parts = []

            # 优先处理 Gemini 格式 (parts 字段)
            if parts_input is not None:
                if isinstance(parts_input, list):
                    for item in parts_input:
                        if isinstance(item, str):
                            if item:  # 跳过空字符串
                                parts.append(genai_types.Part(text=item))
                        elif isinstance(item, dict):
                            # 处理 dict 格式的 part
                            if "text" in item:
                                parts.append(genai_types.Part(text=item["text"]))
                            elif "image" in item and isinstance(
                                item["image"], Image.Image
                            ):
                                # 处理 PIL Image 格式的图片（普通聊天使用的格式）
                                pil_image = item["image"]
                                source = item.get("source", "unknown")
                                try:
                                    # 将 PIL Image 转换为字节
                                    buffer = io.BytesIO()
                                    # 确定图片格式和 MIME 类型
                                    img_format = pil_image.format or "PNG"
                                    if img_format.upper() == "JPEG":
                                        mime_type = "image/jpeg"
                                    elif img_format.upper() == "GIF":
                                        mime_type = "image/gif"
                                    elif img_format.upper() == "WEBP":
                                        mime_type = "image/webp"
                                    else:
                                        img_format = "PNG"
                                        mime_type = "image/png"

                                    # 处理图片模式
                                    if pil_image.mode in ("P", "RGBA"):
                                        if img_format == "JPEG":
                                            pil_image = pil_image.convert("RGB")
                                    elif (
                                        pil_image.mode != "RGB" and img_format == "JPEG"
                                    ):
                                        pil_image = pil_image.convert("RGB")

                                    pil_image.save(buffer, format=img_format)
                                    image_bytes = buffer.getvalue()

                                    parts.append(
                                        genai_types.Part(
                                            inline_data=genai_types.Blob(
                                                mime_type=mime_type,
                                                data=image_bytes,
                                            )
                                        )
                                    )
                                    log.debug(
                                        f"已将 PIL Image 转换为 Gemini 格式，MIME: {mime_type}，来源: {source}"
                                    )
                                except Exception as e:
                                    log.error(f"转换 PIL Image 到 Gemini 格式失败: {e}")
                        elif hasattr(item, "__str__"):
                            # 处理其他可转换为字符串的对象
                            item_str = str(item)
                            if item_str:
                                parts.append(genai_types.Part(text=item_str))
                elif isinstance(parts_input, str):
                    if parts_input:
                        parts.append(genai_types.Part(text=parts_input))

            # 处理 OpenAI 格式 (content 字段)
            elif content is not None:
                if isinstance(content, str):
                    if content:  # 跳过空字符串
                        parts.append(genai_types.Part(text=content))
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, str):
                            if item:
                                parts.append(genai_types.Part(text=item))
                        elif isinstance(item, dict):
                            if item.get("type") == "text":
                                text = item.get("text", "")
                                if text:
                                    parts.append(genai_types.Part(text=text))
                            elif item.get("type") == "image":
                                # 处理 image_bytes 格式的图片（投喂命令使用的格式）
                                image_bytes = item.get("image_bytes")
                                mime_type = item.get("mime_type", "image/png")
                                if image_bytes:
                                    try:
                                        parts.append(
                                            genai_types.Part(
                                                inline_data=genai_types.Blob(
                                                    mime_type=mime_type,
                                                    data=image_bytes,
                                                )
                                            )
                                        )
                                    except Exception as e:
                                        log.error(f"处理 image_bytes 图片失败: {e}")
                            elif item.get("type") == "image_url":
                                # 处理 image_url 格式的图片
                                image_data = item.get("image_url", {})
                                if isinstance(image_data, dict):
                                    url = image_data.get("url", "")
                                    if url.startswith("data:"):
                                        # Base64 编码的图片
                                        import base64

                                        mime_match = (
                                            url.split(";")[0].split(":")[1]
                                            if ":" in url
                                            else "image/png"
                                        )
                                        base64_data = (
                                            url.split(",")[1] if "," in url else ""
                                        )
                                        try:
                                            image_bytes = base64.b64decode(base64_data)
                                            parts.append(
                                                genai_types.Part(
                                                    inline_data=genai_types.Blob(
                                                        mime_type=mime_match,
                                                        data=image_bytes,
                                                    )
                                                )
                                            )
                                        except Exception as e:
                                            log.error(f"解析 Base64 图片失败: {e}")

            if parts:
                contents.append(genai_types.Content(parts=parts, role=gemini_role))
            else:
                log.warning(
                    f"消息转换为空，跳过: role={role}, content={content}, parts={parts_input}"
                )

        return contents

    def _process_response(
        self, response: genai_types.GenerateContentResponse, model_name: str
    ) -> GenerationResult:
        """
        处理 Gemini 响应

        Args:
            response: Gemini 响应对象
            model_name: 模型名称

        Returns:
            GenerationResult: 生成结果
        """
        # 提取文本内容（跳过思考部分）
        content = ""
        if response.candidates and response.candidates[0].content:
            parts = response.candidates[0].content.parts or []
            for part in parts:
                # 跳过思考部分 - 只提取非思考内容的文本
                is_thought = hasattr(part, "thought") and part.thought
                if is_thought:
                    log.debug(
                        f"跳过思考部分文本: {part.text[:50] if part.text else 'N/A'}..."
                    )
                    continue
                if hasattr(part, "text") and part.text:
                    content += part.text

        # 确定结束原因
        finish_reason = FinishReason.STOP
        if response.candidates:
            candidate = response.candidates[0]
            if candidate.finish_reason:
                reason_map = {
                    "STOP": FinishReason.STOP,
                    "MAX_TOKENS": FinishReason.MAX_TOKENS,
                    "SAFETY": FinishReason.SAFETY,
                }
                finish_reason = reason_map.get(
                    str(candidate.finish_reason).upper(), FinishReason.UNKNOWN
                )

        # 提取 token 使用量
        tokens_used = None
        input_tokens = None
        output_tokens = None
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count
            tokens_used = (input_tokens or 0) + (output_tokens or 0)

        return GenerationResult(
            content=content,
            model_used=model_name,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            finish_reason=finish_reason,
            raw_response=response,
        )

    def _calculate_safety_penalty(
        self, response: genai_types.GenerateContentResponse, api_key: Optional[str]
    ) -> int:
        """
        计算安全惩罚分数

        Args:
            response: Gemini 响应
            api_key: API 密钥（用于日志）

        Returns:
            int: 惩罚分数
        """
        total_penalty = 0

        if not response.candidates:
            return total_penalty

        candidate = response.candidates[0]
        if not hasattr(candidate, "safety_ratings") or not candidate.safety_ratings:
            return total_penalty

        for rating in candidate.safety_ratings:
            category_name = rating.category.name if rating.category else "UNKNOWN"
            severity_name = rating.probability.name if rating.probability else "UNKNOWN"

            penalty = self.SAFETY_PENALTY_MAP.get(severity_name, 0)
            if penalty > 0:
                log.warning(
                    f"密钥 ...{api_key[-4:] if api_key else '????'} 收到安全警告。"
                    f"类别: {category_name}, 严重性: {severity_name}, 惩罚: {penalty}"
                )
                total_penalty += penalty

        return total_penalty


class GeminiCustomProvider(GeminiProvider):
    """
    自定义 Gemini 端点 Provider

    用于连接自定义的 Gemini 兼容端点（如公益站）
    """

    provider_type = "gemini_custom"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        provider_name: str = "gemini_custom",
        models: Optional[List[str]] = None,
    ):
        """
        初始化自定义 Gemini Provider

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            provider_name: Provider 名称
            models: 支持的模型列表
        """
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            use_key_rotation=False,
            provider_name=provider_name,
        )

        if models:
            self.supported_models = models
