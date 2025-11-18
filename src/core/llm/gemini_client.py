# -*- coding: utf-8 -*-

import os
import logging
import asyncio
import re
from typing import Any, Callable, Dict, List, Optional
from functools import wraps

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from src.core.llm.key_rotation_service import KeyRotationService, NoAvailableKeyError
from src.chat.config import chat_config as app_config

log = logging.getLogger(__name__)


class GeminiApiClient:
    """
    一个封装了 Google Gemini API 底层交互的客户端。
    负责处理 API 密钥轮换、错误重试、冷却和安全评级。
    """

    SAFETY_PENALTY_MAP = {
        "NEGLIGIBLE": 0,
        "LOW": 1,
        "MEDIUM": 5,
        "HIGH": 10,
    }

    def __init__(self, api_keys: List[str]):
        """
        初始化 Gemini API 客户端。

        Args:
            api_keys: 用于轮换的 Google API 密钥列表。
        """
        if not api_keys:
            raise ValueError("GOOGLE_API_KEYS_LIST is not set or empty.")

        self.key_rotation_service = KeyRotationService(api_keys)
        log.info(
            f"GeminiApiClient initialized with {len(api_keys)} keys managed by KeyRotationService."
        )
        self.safety_settings = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]

    def _create_client_with_key(self, api_key: str) -> genai.Client:
        """使用给定的 API 密钥动态创建一个 Gemini 客户端实例。"""
        base_url = os.getenv("GEMINI_API_BASE_URL")
        if base_url:
            log.info(f"Using custom Gemini API endpoint: {base_url}")
            http_options = types.HttpOptions(base_url=base_url)
            return genai.Client(api_key=api_key, http_options=http_options)
        else:
            log.info("Using default Gemini API endpoint.")
            return genai.Client(api_key=api_key)

    def _handle_safety_ratings(
        self, response: types.GenerateContentResponse, key: str
    ) -> int:
        """检查响应的安全评分并返回相应的惩罚值。"""
        total_penalty = 0
        if not response.candidates:
            return 0

        candidate = response.candidates[0]
        if candidate.safety_ratings:
            for rating in candidate.safety_ratings:
                category_name = rating.category.name.replace("HARM_CATEGORY_", "")
                severity_name = rating.probability.name
                penalty = self.SAFETY_PENALTY_MAP.get(severity_name, 0)
                if penalty > 0:
                    log.warning(
                        f"Key ...{key[-4:]} received a safety warning. Category: {category_name}, Severity: {severity_name}, Penalty: {penalty}"
                    )
                    total_penalty += penalty
        return total_penalty

    def _api_key_handler(func: Callable) -> Callable:
        """
        一个装饰器，用于优雅地处理 API 密钥的获取、释放和重试逻辑。
        """

        @wraps(func)
        async def wrapper(self: "GeminiApiClient", *args, **kwargs):
            while True:
                key_obj = None
                try:
                    key_obj = await self.key_rotation_service.acquire_key()
                    client = self._create_client_with_key(key_obj.key)
                    kwargs["client"] = client  # 将 client 注入到被装饰的方法中

                    failure_penalty = 25
                    key_should_be_cooled_down = False

                    max_attempts = app_config.API_RETRY_CONFIG["MAX_ATTEMPTS_PER_KEY"]
                    for attempt in range(max_attempts):
                        try:
                            log.info(
                                f"Using key ...{key_obj.key[-4:]} (Attempt {attempt + 1}/{max_attempts}) to call {func.__name__}"
                            )

                            result = await func(self, *args, **kwargs)

                            safety_penalty = 0
                            is_blocked_by_safety = False
                            if isinstance(result, types.GenerateContentResponse):
                                safety_penalty = self._handle_safety_ratings(
                                    result, key_obj.key
                                )
                                if (
                                    not result.parts
                                    and result.prompt_feedback
                                    and result.prompt_feedback.block_reason
                                ):
                                    is_blocked_by_safety = True

                            if is_blocked_by_safety:
                                log.warning(
                                    f"Key ...{key_obj.key[-4:]} was blocked by safety policy (Reason: {result.prompt_feedback.block_reason}). Cooling down without penalty."
                                )
                                failure_penalty = 0
                                key_should_be_cooled_down = True
                                break

                            await self.key_rotation_service.release_key(
                                key_obj.key, success=True, safety_penalty=safety_penalty
                            )
                            return result

                        except (
                            genai_errors.ClientError,
                            genai_errors.ServerError,
                        ) as e:
                            error_str = str(e)
                            match = re.match(r"(\d{3})", error_str)
                            status_code = int(match.group(1)) if match else None

                            is_retryable = status_code in [429, 503]
                            if (
                                not is_retryable
                                and isinstance(e, genai_errors.ServerError)
                                and "503" in error_str
                            ):
                                is_retryable = True
                                status_code = 503

                            if is_retryable:
                                log.warning(
                                    f"Key ...{key_obj.key[-4:]} encountered a retryable error (Status: {status_code})."
                                )
                                if attempt < max_attempts - 1:
                                    delay = app_config.API_RETRY_CONFIG[
                                        "RETRY_DELAY_SECONDS"
                                    ]
                                    log.info(
                                        f"Waiting {delay} seconds before retrying."
                                    )
                                    await asyncio.sleep(delay)
                                else:
                                    log.warning(
                                        f"All {max_attempts} retries failed for key ...{key_obj.key[-4:]}. Cooling down."
                                    )
                                    base_penalty = 10
                                    consecutive_failures = (
                                        key_obj.consecutive_failures + 1
                                    )
                                    failure_penalty = (
                                        base_penalty * consecutive_failures
                                    )
                                    log.warning(
                                        f"Key ...{key_obj.key[-4:]} has {consecutive_failures} consecutive failures. Penalty: {failure_penalty}"
                                    )
                                    key_should_be_cooled_down = True

                            elif status_code == 403 or (
                                status_code == 400
                                and "API_KEY_INVALID" in error_str.upper()
                            ):
                                log.error(
                                    f"Key ...{key_obj.key[-4:]} is invalid (Status: {status_code}). Applying devastating penalty."
                                )
                                failure_penalty = 101
                                key_should_be_cooled_down = True
                                break

                            else:
                                log.error(
                                    f"Fatal API error with key ...{key_obj.key[-4:]} (Status: {status_code}): {e}",
                                    exc_info=True,
                                )
                                # Let the exception propagate up to be handled by the caller
                                raise

                    if key_should_be_cooled_down:
                        await self.key_rotation_service.release_key(
                            key_obj.key, success=False, failure_penalty=failure_penalty
                        )

                except NoAvailableKeyError:
                    log.error(
                        "All API keys are unavailable. This is an exceptional situation."
                    )
                    raise  # Re-raise the exception to be handled by the caller
                except Exception:
                    # Ensure the key is released even on unexpected errors
                    if key_obj:
                        await self.key_rotation_service.release_key(
                            key_obj.key, success=True
                        )
                    raise  # Re-raise

        return wrapper

    @_api_key_handler
    async def generate_content(
        self,
        model_name: str,
        contents: List[types.Content],
        generation_config: types.GenerateContentConfig,
        client: genai.Client = None,
    ) -> types.GenerateContentResponse:
        """
        调用 Gemini API 的 generate_content 方法。

        Args:
            model_name: 模型名称。
            contents: 对话历史或提示内容。
            generation_config: 生成配置。
            client: (由装饰器注入) genai.Client 实例。

        Returns:
            API 的响应对象。
        """
        if not client:
            raise ValueError("Decorator failed to provide a client instance.")

        return await client.aio.models.generate_content(
            model=model_name,
            contents=contents,
            config=generation_config,
        )

    @_api_key_handler
    async def embed_content(
        self,
        model_name: str,
        contents: List[types.Part],
        embedding_config: types.EmbedContentConfig,
        client: genai.Client = None,
    ) -> types.EmbedContentResponse:
        """
        调用 Gemini API 的 embed_content 方法。

        Args:
            model_name: 模型名称。
            contents: 要嵌入的内容。
            embedding_config: 嵌入配置。
            client: (由装饰器注入) genai.Client 实例。

        Returns:
            API 的响应对象。
        """
        if not client:
            raise ValueError("Decorator failed to provide a client instance.")

        return client.models.embed_content(
            model=model_name,
            contents=contents,
            config=embedding_config,
        )
