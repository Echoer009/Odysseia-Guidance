# -*- coding: utf-8 -*-

import os
import logging
from typing import Optional, Dict, List, Callable, Any
import asyncio
from functools import wraps
from concurrent.futures import ThreadPoolExecutor
import json
from datetime import datetime
import re
import random

from PIL import Image
import io

# 导入新库
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

# 导入数据库管理器和提示词配置
from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config as app_config
from src.chat.config.emoji_config import EMOJI_MAPPINGS, FACTION_EMOJI_MAPPINGS
from src.chat.services.event_service import event_service
from src.chat.services.regex_service import regex_service
from src.chat.services.prompt_service import prompt_service
from src.chat.services.key_rotation_service import (
    KeyRotationService,
    NoAvailableKeyError,
)
from src.chat.features.tools.services.tool_service import ToolService
from src.chat.features.tools.tool_loader import load_tools_from_directory
from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.utils.image_utils import sanitize_image


log = logging.getLogger(__name__)

# --- 设置专门用于记录无效 API 密钥的 logger ---
# 确保 data 目录存在
if not os.path.exists("data"):
    os.makedirs("data")

# 创建一个新的 logger 实例
invalid_key_logger = logging.getLogger("invalid_api_keys")
invalid_key_logger.setLevel(logging.ERROR)

# 创建文件处理器，将日志写入到 data/invalid_api_keys.log
# 使用 a 模式表示追加写入
fh = logging.FileHandler("data/invalid_api_keys.log", mode="a", encoding="utf-8")
fh.setLevel(logging.ERROR)

# 创建格式化器并设置
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)

# 为 logger 添加处理器
# 防止重复添加处理器
if not invalid_key_logger.handlers:
    invalid_key_logger.addHandler(fh)


class GeminiService:
    """Gemini AI 服务类，使用数据库存储用户对话上下文"""

    def __init__(self):
        self.bot = None  # 用于存储 Discord Bot 实例

        # --- (新) SDK 底层调试日志 ---
        # 根据最新指南 (2025)，开启此选项可查看详细的 HTTP 请求/响应
        if app_config.DEBUG_CONFIG.get("LOG_SDK_HTTP_REQUESTS", False):
            log.info("已开启 google-genai SDK 底层 DEBUG 日志。")
            # 设置基础日志记录器以捕获 httpx 的调试信息
            logging.basicConfig(level=logging.DEBUG)
        # --- 密钥轮换服务 ---
        google_api_keys_str = os.getenv("GOOGLE_API_KEYS_LIST", "")
        if not google_api_keys_str:
            log.error("GOOGLE_API_KEYS_LIST 环境变量未设置！服务将无法运行。")
            # 在这种严重配置错误下，抛出异常以阻止应用启动
            raise ValueError("GOOGLE_API_KEYS_LIST is not set.")

        # 先移除整个字符串两端的空格和引号，以支持 "key1,key2" 格式
        processed_keys_str = google_api_keys_str.strip().strip('"')
        api_keys = [key.strip() for key in processed_keys_str.split(",") if key.strip()]
        self.key_rotation_service = KeyRotationService(api_keys)
        log.info(
            f"GeminiService 初始化并由 KeyRotationService 管理 {len(api_keys)} 个密钥。"
        )

        self.default_model_name = app_config.GEMINI_MODEL
        self.executor = ThreadPoolExecutor(
            max_workers=app_config.MAX_CONCURRENT_REQUESTS
        )
        self.user_request_timestamps: Dict[int, List[datetime]] = {}
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

        # --- 工具配置 (模块化标准) ---
        # 1. 使用加载器动态发现所有工具
        self.available_tools, self.tool_map = load_tools_from_directory(
            "src/chat/features/tools/functions"
        )

        # 2. 实例化工具服务，并传入工具映射
        self.tool_service = ToolService(bot=None, tool_map=self.tool_map)

        log.info("--- 工具加载完成 (模块化) ---")
        log.info(
            f"已加载 {len(self.available_tools)} 个工具: {list(self.tool_map.keys())}"
        )
        log.info("------------------------------------")

    def set_bot(self, bot):
        """注入 Discord Bot 实例。"""
        self.bot = bot
        log.info("Discord Bot 实例已成功注入 GeminiService。")
        # 关键：同时将 bot 实例注入到 ToolService 中
        self.tool_service.bot = bot
        log.info("Discord Bot 实例已成功注入 ToolService。")

    def _create_client_with_key(self, api_key: str):
        """使用给定的 API 密钥动态创建一个 Gemini 客户端实例。"""
        base_url = os.getenv("GEMINI_API_BASE_URL")
        if base_url:
            log.info(f"使用自定义 Gemini API 端点: {base_url}")
            # 根据用户提供的文档，正确的方法是使用 types.HttpOptions
            # Cloudflare Worker 需要 /gemini 后缀，所以我们不移除它
            http_options = types.HttpOptions(base_url=base_url)
            return genai.Client(api_key=api_key, http_options=http_options)
        else:
            log.info("使用默认 Gemini API 端点。")
            return genai.Client(api_key=api_key)

    async def get_user_conversation_history(
        self, user_id: int, guild_id: int
    ) -> List[Dict]:
        """从数据库获取用户的对话历史"""
        context = await chat_db_manager.get_ai_conversation_context(user_id, guild_id)
        if context and context.get("conversation_history"):
            return context["conversation_history"]
        return []

    # --- Refactored Cooldown Logic ---

    # --- Static Helper Methods for Serialization ---
    @staticmethod
    def _serialize_for_logging(obj):
        """自定义序列化函数，用于截断长文本以进行日志记录。"""
        if isinstance(obj, dict):
            return {
                key: GeminiService._serialize_for_logging(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [GeminiService._serialize_for_logging(item) for item in obj]
        elif isinstance(obj, str) and len(obj) > 200:
            return obj[:200] + "..."
        elif isinstance(obj, Image.Image):
            return f"<PIL.Image object: mode={obj.mode}, size={obj.size}>"
        else:
            try:
                json.JSONEncoder().default(obj)
                return obj
            except TypeError:
                return str(obj)

    @staticmethod
    def _serialize_parts_for_error_logging(obj):
        """自定义序列化函数，用于在出现问题时记录请求体。"""
        if isinstance(obj, types.Part):
            if obj.text:
                return {"type": "text", "content": obj.text}
            elif obj.inline_data:
                return {
                    "type": "image",
                    "mime_type": obj.inline_data.mime_type,
                    "data_size": len(obj.inline_data.data),
                }
        elif isinstance(obj, Image.Image):
            return f"<PIL.Image object: mode={obj.mode}, size={obj.size}>"
        try:
            return json.JSONEncoder().default(obj)
        except TypeError:
            return str(obj)

    @staticmethod
    def _serialize_parts_for_logging_full(content: types.Content):
        """自定义序列化函数，用于完整记录 Content 对象。"""
        serialized_parts = []
        for part in content.parts:
            if part.text:
                serialized_parts.append({"type": "text", "content": part.text})
            elif part.inline_data:
                serialized_parts.append(
                    {
                        "type": "image",
                        "mime_type": part.inline_data.mime_type,
                        "data_size": len(part.inline_data.data),
                        "data_preview": part.inline_data.data[:50].hex()
                        + "...",  # 记录数据前50字节的十六进制预览
                    }
                )
            elif part.file_data:
                serialized_parts.append(
                    {
                        "type": "file",
                        "mime_type": part.file_data.mime_type,
                        "file_uri": part.file_data.file_uri,
                    }
                )
            else:
                serialized_parts.append({"type": "unknown_part", "content": str(part)})
        return {"role": content.role, "parts": serialized_parts}

    # --- Refactored generate_response and its helpers ---
    def _prepare_api_contents(self, conversation: List[Dict]) -> List[types.Content]:
        """将对话历史转换为 API 所需的 Content 对象列表。"""
        processed_contents = []
        for turn in conversation:
            role = turn.get("role")
            parts_data = turn.get("parts", [])
            if not (role and parts_data):
                continue

            processed_parts = []
            for part_item in parts_data:
                if isinstance(part_item, str):
                    processed_parts.append(types.Part(text=part_item))
                elif isinstance(part_item, Image.Image):
                    buffered = io.BytesIO()
                    part_item.save(buffered, format="PNG")
                    img_bytes = buffered.getvalue()
                    processed_parts.append(
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/png", data=img_bytes
                            )
                        )
                    )

            if processed_parts:
                processed_contents.append(
                    types.Content(role=role, parts=processed_parts)
                )
        return processed_contents

    async def _post_process_response(
        self, raw_response: str, user_id: int, guild_id: int
    ) -> str:
        """对 AI 的原始回复进行清理和处理。"""
        # 1. Clean various reply prefixes and tags
        reply_prefix_pattern = re.compile(
            r"^\s*([\[［]【回复|回复}\s*@.*?[\)）\]］])\s*", re.IGNORECASE
        )
        formatted = reply_prefix_pattern.sub("", raw_response)
        formatted = re.sub(
            r"<CURRENT_USER_MESSAGE_TO_REPLY.*?>", "", formatted, flags=re.IGNORECASE
        )
        # formatted = regex_service.clean_ai_output(formatted)

        # 2. Remove old Discord emoji codes
        discord_emoji_pattern = re.compile(r":\w+:")
        formatted = discord_emoji_pattern.sub("", formatted)

        # 3. Replace custom emoji placeholders
        active_event = event_service.get_active_event()
        selected_faction = event_service.get_selected_faction()

        emoji_map_to_use = EMOJI_MAPPINGS  # Default to global map

        if active_event and selected_faction:
            event_id = active_event.get("event_id")
            faction_map = FACTION_EMOJI_MAPPINGS.get(event_id, {}).get(selected_faction)
            if faction_map:
                log.info(
                    f"使用事件 '{event_id}' 派系 '{selected_faction}' 的专属表情包。"
                )
                emoji_map_to_use = faction_map
            else:
                log.info(
                    f"未找到派系 '{selected_faction}' 的专属表情包，使用全局表情包。"
                )
        else:
            log.info("未使用任何派系表情包，使用全局表情包。")

        for pattern, emojis in emoji_map_to_use:
            if isinstance(emojis, list) and emojis:
                selected_emoji = random.choice(emojis)
                formatted = pattern.sub(selected_emoji, formatted)
            elif isinstance(emojis, str):
                formatted = pattern.sub(emojis, formatted)

        # 4. Handle warning marker (DEPRECATED)
        # This logic is now handled by the 'issue_user_warning' tool.
        # The code is kept here for reference but is disabled.
        # warning_marker = "<warn>"
        # if formatted.endswith(warning_marker):
        #     formatted = formatted[: -len(warning_marker)].strip()
        #     try:
        #         min_d, max_d = app_config.BLACKLIST_BAN_DURATION_MINUTES
        #         ban_duration = random.randint(min_d, max_d)
        #         expires_at = datetime.now(timezone.utc) + timedelta(
        #             minutes=ban_duration
        #         )
        #
        #         log.info(f"用户 {user_id} 在服务器 {guild_id} 收到一次警告。")
        #
        #         was_blacklisted = (
        #             await chat_db_manager.record_warning_and_check_blacklist(
        #                 user_id, guild_id, expires_at
        #             )
        #         )
        #
        #         if was_blacklisted:
        #             log.info(
        #                 f"用户 {user_id} 因累计3次警告被自动拉黑 {ban_duration} 分钟，过期时间: {expires_at}。"
        #             )
        #             await affection_service.decrease_affection_on_blacklist(
        #                 user_id, guild_id
        #             )
        #         # 如果只是警告而未拉黑，也可以考虑在这里进行轻微的好感度惩罚，但根据当前需求，我们只在拉黑时操作。
        #
        #     except Exception as e:
        #         log.error(f"处理用户 {user_id} 的警告时出错: {e}")

        return formatted

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
                # 将枚举值转换为字符串键
                category_name = rating.category.name.replace("HARM_CATEGORY_", "")
                severity_name = rating.probability.name

                penalty = self.SAFETY_PENALTY_MAP.get(severity_name, 0)
                if penalty > 0:
                    log.warning(
                        f"密钥 ...{key[-4:]} 收到安全警告。类别: {category_name}, 严重性: {severity_name}, 惩罚: {penalty}"
                    )
                    total_penalty += penalty
        return total_penalty

    def _api_key_handler(func: Callable) -> Callable:
        """
        一个装饰器，用于优雅地处理 API 密钥的获取、释放和重试逻辑。
        实现了两层重试：
        1. 外层循环：持续获取可用密钥，如果所有密钥都在冷却，则会等待。
        2. 内层循环：对获取到的单个密钥，在遇到可重试错误时，会根据配置进行多次尝试。
        """

        @wraps(func)
        async def wrapper(self: "GeminiService", *args, **kwargs):
            while True:
                key_obj = None
                try:
                    key_obj = await self.key_rotation_service.acquire_key()
                    client = self._create_client_with_key(key_obj.key)

                    failure_penalty = 25  # 默认的失败惩罚
                    key_should_be_cooled_down = False
                    key_is_invalid = False

                    max_attempts = app_config.API_RETRY_CONFIG["MAX_ATTEMPTS_PER_KEY"]
                    for attempt in range(max_attempts):
                        try:
                            log.info(
                                f"使用密钥 ...{key_obj.key[-4:]} (尝试 {attempt + 1}/{max_attempts}) 调用 {func.__name__}"
                            )

                            result = await func(self, *args, client=client, **kwargs)

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
                                    f"密钥 ...{key_obj.key[-4:]} 因安全策略被阻止 (原因: {result.prompt_feedback.block_reason})。将进入冷却且不扣分。"
                                )
                                failure_penalty = 0  # 明确设置为0，不扣分
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
                                    f"密钥 ...{key_obj.key[-4:]} 遇到可重试错误 (状态码: {status_code})。"
                                )
                                if attempt < max_attempts - 1:
                                    delay = app_config.API_RETRY_CONFIG[
                                        "RETRY_DELAY_SECONDS"
                                    ]
                                    log.info(f"等待 {delay} 秒后重试。")
                                    await asyncio.sleep(delay)
                                else:
                                    log.warning(
                                        f"密钥 ...{key_obj.key[-4:]} 的所有 {max_attempts} 次重试均失败。将进入冷却。"
                                    )
                                    # --- 渐进式惩罚逻辑 ---
                                    base_penalty = 10
                                    consecutive_failures = (
                                        key_obj.consecutive_failures + 1
                                    )  # +1 是因为本次失败也要计算在内
                                    failure_penalty = (
                                        base_penalty * consecutive_failures
                                    )
                                    log.warning(
                                        f"密钥 ...{key_obj.key[-4:]} 已连续失败 {consecutive_failures} 次。"
                                        f"本次惩罚分值: {failure_penalty}"
                                    )
                                    key_should_be_cooled_down = True

                            elif status_code == 403 or (
                                status_code == 400
                                and "API_KEY_INVALID" in error_str.upper()
                            ):
                                log.error(
                                    f"密钥 ...{key_obj.key[-4:]} 无效 (状态码: {status_code})。将施加毁灭性惩罚。"
                                )
                                failure_penalty = 101  # 毁灭性惩罚
                                key_should_be_cooled_down = True
                                break  # 直接跳出重试循环

                            else:
                                log.error(
                                    f"使用密钥 ...{key_obj.key[-4:]} 时发生意外的致命API错误 (状态码: {status_code}): {e}",
                                    exc_info=True,
                                )
                                if isinstance(e, genai_errors.ServerError):
                                    # 对于服务器错误，也采用渐进式惩罚
                                    base_penalty = 15  # 服务器错误的基础惩罚可以稍高
                                    consecutive_failures = (
                                        key_obj.consecutive_failures + 1
                                    )
                                    failure_penalty = (
                                        base_penalty * consecutive_failures
                                    )
                                    log.warning(
                                        f"密钥 ...{key_obj.key[-4:]} 遭遇服务器错误，已连续失败 {consecutive_failures} 次。"
                                        f"本次惩罚分值: {failure_penalty}"
                                    )
                                    key_should_be_cooled_down = True
                                    break
                                else:
                                    await self.key_rotation_service.release_key(
                                        key_obj.key, success=True
                                    )
                                    return "抱歉，AI服务遇到了一个意料之外的错误，请稍后再试。"

                        except Exception as e:
                            log.error(
                                f"使用密钥 ...{key_obj.key[-4:]} 时发生未知错误: {e}",
                                exc_info=True,
                            )
                            await self.key_rotation_service.release_key(
                                key_obj.key, success=True
                            )
                            if func.__name__ == "generate_embedding":
                                return None
                            return "呜哇，有点晕嘞，等我休息一会儿 <伤心>"

                    if key_is_invalid:
                        continue

                    if key_should_be_cooled_down:
                        await self.key_rotation_service.release_key(
                            key_obj.key, success=False, failure_penalty=failure_penalty
                        )

                except NoAvailableKeyError:
                    log.error(
                        "所有API密钥均不可用，且 acquire_key 未能成功等待。这是异常情况。"
                    )
                    return "啊啊啊服务器要爆炸啦！现在有点忙不过来，你过一会儿再来找我玩吧！<生气>"

        return wrapper

    async def generate_response(
        self,
        user_id: int,
        guild_id: int,
        message: str,
        channel: Optional[Any] = None,
        replied_message: Optional[str] = None,
        images: Optional[List[Dict]] = None,
        user_name: str = "用户",
        channel_context: Optional[List[Dict]] = None,
        world_book_entries: Optional[List[Dict]] = None,
        personal_summary: Optional[str] = None,
        affection_status: Optional[Dict[str, Any]] = None,
        user_profile_data: Optional[Dict[str, Any]] = None,
        guild_name: str = "未知服务器",
        location_name: str = "未知位置",
        model_name: Optional[str] = None,
    ) -> str:
        """
        AI 回复生成的分发器。
        如果选择了自定义模型，则优先尝试自定义端点；如果失败，则自动回退到官方 API。
        """
        # 如果选择了自定义模型，则尝试使用它，并准备好回退
        if model_name and model_name in app_config.CUSTOM_GEMINI_ENDPOINTS:
            log.info(f"检测到自定义模型 '{model_name}'，将优先尝试使用自定义端点。")
            max_attempts = 2  # 1次主尝试 + 1次重试
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    log.info(
                        f"尝试使用自定义端点 '{model_name}' (尝试 {attempt + 1}/{max_attempts})"
                    )
                    return await self._generate_with_custom_endpoint(
                        user_id=user_id,
                        guild_id=guild_id,
                        message=message,
                        channel=channel,
                        replied_message=replied_message,
                        images=images,
                        user_name=user_name,
                        channel_context=channel_context,
                        world_book_entries=world_book_entries,
                        personal_summary=personal_summary,
                        affection_status=affection_status,
                        user_profile_data=user_profile_data,
                        guild_name=guild_name,
                        location_name=location_name,
                        model_name=model_name,
                    )
                except Exception as e:
                    last_exception = e
                    log.warning(
                        f"使用自定义端点 '{model_name}' (尝试 {attempt + 1}/{max_attempts}) 失败: {e}"
                    )
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(1)  # 在重试前稍作等待

            # 如果所有尝试都失败了，则执行回退逻辑
            log.warning(
                f"自定义端点 '{model_name}' 的所有 {max_attempts} 次尝试均失败。最终错误: {last_exception}. "
                f"将回退到官方 API。"
            )
            # --- [新逻辑] 回退时固定使用 gemini-2.5-flash 模型 ---
            fallback_model_name = "gemini-2.5-flash"
            log.info(f"回退到官方 API，固定使用模型 '{fallback_model_name}'。")

            return await self._generate_with_official_api(
                user_id=user_id,
                guild_id=guild_id,
                message=message,
                channel=channel,
                replied_message=replied_message,
                images=images,
                user_name=user_name,
                channel_context=channel_context,
                world_book_entries=world_book_entries,
                personal_summary=personal_summary,
                affection_status=affection_status,
                user_profile_data=user_profile_data,
                guild_name=guild_name,
                location_name=location_name,
                model_name=fallback_model_name,  # 关键：使用固定的回退模型
            )

        # 对于非自定义模型或回退失败后的默认路径
        log.info(
            f"使用模型 '{model_name or self.default_model_name}'，将使用官方 API 逻辑。"
        )
        return await self._generate_with_official_api(
            user_id=user_id,
            guild_id=guild_id,
            message=message,
            channel=channel,
            replied_message=replied_message,
            images=images,
            user_name=user_name,
            channel_context=channel_context,
            world_book_entries=world_book_entries,
            personal_summary=personal_summary,
            affection_status=affection_status,
            user_profile_data=user_profile_data,
            guild_name=guild_name,
            location_name=location_name,
            model_name=model_name,
        )

    async def _generate_with_custom_endpoint(
        self,
        user_id: int,
        guild_id: int,
        message: str,
        channel: Optional[Any] = None,
        replied_message: Optional[str] = None,
        images: Optional[List[Dict]] = None,
        user_name: str = "用户",
        channel_context: Optional[List[Dict]] = None,
        world_book_entries: Optional[List[Dict]] = None,
        personal_summary: Optional[str] = None,
        affection_status: Optional[Dict[str, Any]] = None,
        user_profile_data: Optional[Dict[str, Any]] = None,
        guild_name: str = "未知服务器",
        location_name: str = "未知位置",
        model_name: Optional[str] = None,
    ) -> str:
        """
        [新增] 使用自定义端点 (例如公益站) 生成 AI 回复。
        此方法不使用密钥轮换，直接根据配置创建客户端。
        失败时会抛出异常，由调用方 (generate_response) 处理回退逻辑。
        """
        endpoint_config = app_config.CUSTOM_GEMINI_ENDPOINTS.get(model_name)
        if not endpoint_config or not all(
            [endpoint_config.get("base_url"), endpoint_config.get("api_key")]
        ):
            error_msg = (
                f"模型 '{model_name}' 的自定义端点配置不完整或未找到。"
                "请检查 CUSTOM_GEMINI_URL_* 和 CUSTOM_GEMINI_API_KEY_* 环境变量。"
            )
            log.error(error_msg)
            # 抛出异常以触发回退逻辑
            raise ValueError(error_msg)

        # --- 关键：为自定义端点单独创建客户端，不使用全局的 _create_client_with_key ---
        log.info(f"正在为自定义端点创建客户端: {endpoint_config['base_url']}")
        http_options = types.HttpOptions(base_url=endpoint_config["base_url"])
        client = genai.Client(
            api_key=endpoint_config["api_key"], http_options=http_options
        )

        # --- [重构] 针对自定义端点的图片净化 ---
        # 只有在调用自定义端点时才执行此操作，因为官方API可以处理这些图片。
        sanitized_images_for_endpoint = []
        if images:
            log.info(f"检测到 {len(images)} 张图片，将为自定义端点进行净化处理。")
            for img_data in images:
                # --- [优化] 仅当图片来源是用户附件时才进行净化 ---
                if img_data.get("source") == "attachment":
                    try:
                        # [修复] 增加健壮性，同时检查 'data' 和 'bytes' 键
                        image_bytes = img_data.get("data") or img_data.get("bytes")
                        if not image_bytes:
                            log.warning(
                                f"附件图片数据字典中缺少 'data' 或 'bytes' 键，已跳过。Keys: {list(img_data.keys())}"
                            )
                            continue

                        sanitized_bytes, new_mime_type = sanitize_image(image_bytes)
                        # [修复] 保持键名一致性，使用 'data' 存储净化后的字节
                        sanitized_images_for_endpoint.append(
                            {
                                "data": sanitized_bytes,
                                "mime_type": new_mime_type,
                                "source": "attachment",  # 来源是确定的
                            }
                        )
                    except Exception as e:
                        # 如果净化失败，记录错误并通知用户
                        log.error(f"为自定义端点净化附件图片时失败: {e}", exc_info=True)
                        return "呜哇，这张图好像有点问题，我处理不了…可以换一张试试吗？<伤心>"
                else:
                    # 对于非附件图片（如表情），直接使用原始数据
                    sanitized_images_for_endpoint.append(img_data)

        # 复用核心生成逻辑。从此方法抛出的任何异常都将由 generate_response 捕获。
        return await self._execute_generation_cycle(
            user_id=user_id,
            guild_id=guild_id,
            message=message,
            channel=channel,
            replied_message=replied_message,
            images=sanitized_images_for_endpoint
            if images
            else None,  # 如果有图片，则使用净化后的版本
            user_name=user_name,
            channel_context=channel_context,
            world_book_entries=world_book_entries,
            personal_summary=personal_summary,
            affection_status=affection_status,
            user_profile_data=user_profile_data,
            guild_name=guild_name,
            location_name=location_name,
            prompt_model_name=model_name,  # 传递用于选择 Prompt 的原始模型名称
            api_model_name=endpoint_config.get("model_name")
            or self.default_model_name,  # 传递用于调用 API 的真实模型名称
            client=client,
        )

    @_api_key_handler
    async def _generate_with_official_api(
        self,
        user_id: int,
        guild_id: int,
        message: str,
        channel: Optional[Any] = None,
        replied_message: Optional[str] = None,
        images: Optional[List[Dict]] = None,
        user_name: str = "用户",
        channel_context: Optional[List[Dict]] = None,
        world_book_entries: Optional[List[Dict]] = None,
        personal_summary: Optional[str] = None,
        affection_status: Optional[Dict[str, Any]] = None,
        user_profile_data: Optional[Dict[str, Any]] = None,
        guild_name: str = "未知服务器",
        location_name: str = "未知位置",
        model_name: Optional[str] = None,
        client: Any = None,
    ) -> str:
        """
        [重构] 使用官方 API 密钥池生成 AI 回复。
        此方法由 _api_key_handler 装饰器管理，负责密钥轮换和重试。
        """
        if not client:
            raise ValueError("装饰器未能提供客户端实例。")

        # 将所有生成逻辑委托给核心方法
        return await self._execute_generation_cycle(
            user_id=user_id,
            guild_id=guild_id,
            message=message,
            channel=channel,
            replied_message=replied_message,
            images=images,
            user_name=user_name,
            channel_context=channel_context,
            world_book_entries=world_book_entries,
            personal_summary=personal_summary,
            affection_status=affection_status,
            user_profile_data=user_profile_data,
            guild_name=guild_name,
            location_name=location_name,
            prompt_model_name=model_name,  # 对于官方 API，prompt 和 api 模型名称相同
            api_model_name=model_name,
            client=client,
        )

    async def _execute_generation_cycle(
        self,
        user_id: int,
        guild_id: int,
        message: str,
        channel: Optional[Any],
        replied_message: Optional[str],
        images: Optional[List[Dict]],
        user_name: str,
        channel_context: Optional[List[Dict]],
        world_book_entries: Optional[List[Dict]],
        personal_summary: Optional[str],
        affection_status: Optional[Dict[str, Any]],
        user_profile_data: Optional[Dict[str, Any]],
        guild_name: str,
        location_name: str,
        prompt_model_name: Optional[str],
        api_model_name: Optional[str],
        client: Any,
    ) -> str:
        """
        [新增] 核心的 AI 生成周期，包含上下文构建、工具调用循环和响应处理。
        此方法被 _generate_with_official_api 和 _generate_with_custom_endpoint 复用。
        """
        # --- 模型使用计数 ---
        # 使用 prompt_model_name (表面模型名) 进行计数，而不是 api_model_name (真实模型名)
        model_to_count = prompt_model_name or self.default_model_name
        await chat_settings_service.increment_model_usage(model_to_count)

        # 1. 构建完整的对话提示
        final_conversation = prompt_service.build_chat_prompt(
            user_name=user_name,
            message=message,
            replied_message=replied_message,
            images=images,
            channel_context=channel_context,
            world_book_entries=world_book_entries,
            affection_status=affection_status,
            personal_summary=personal_summary,
            user_profile_data=user_profile_data,
            guild_name=guild_name,
            location_name=location_name,
            model_name=prompt_model_name,
        )

        # 3. 准备 API 调用参数
        chat_config = app_config.GEMINI_CHAT_CONFIG.copy()
        thinking_budget = chat_config.pop("thinking_budget", None)
        gen_config_params = {**chat_config, "safety_settings": self.safety_settings}

        if self.available_tools:
            gen_config_params["tools"] = self.available_tools
            gen_config_params["automatic_function_calling"] = (
                types.AutomaticFunctionCallingConfig(disable=True)
            )
            log.info("已启用手动工具调用模式。")

        gen_config = types.GenerateContentConfig(**gen_config_params)

        if thinking_budget is not None:
            gen_config.thinking_config = types.ThinkingConfig(
                include_thoughts=True,
                thinking_budget=thinking_budget,
            )
            log.info(
                f"已为模型启用思维链 (Thinking)，预算: {thinking_budget}，并要求返回思考内容。"
            )

        # 4. 准备初始对话历史
        conversation_history = self._prepare_api_contents(final_conversation)

        if app_config.DEBUG_CONFIG["LOG_AI_FULL_CONTEXT"]:
            log.info(f"--- 初始 AI 上下文 (用户 {user_id}) ---")
            log.info(
                json.dumps(
                    [
                        self._serialize_parts_for_logging_full(c)
                        for c in conversation_history
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            log.info("------------------------------------")

        # 5. 实现手动、顺序工具调用循环
        called_tool_names = []
        thinking_was_used = False
        max_calls = 5
        for i in range(max_calls):
            log_detailed = app_config.DEBUG_CONFIG.get(
                "LOG_DETAILED_GEMINI_PROCESS", False
            )
            if log_detailed:
                log.info(f"--- [工具调用循环: 第 {i + 1}/{max_calls} 次] ---")

            response = None
            for attempt in range(2):
                response = await client.aio.models.generate_content(
                    model=(api_model_name or self.default_model_name),
                    contents=conversation_history,
                    config=gen_config,
                )
                if response and (response.parts or response.function_calls):
                    break
                log.warning(f"模型返回空响应 (尝试 {attempt + 1}/2)。将在1秒后重试...")
                if attempt < 1:
                    await asyncio.sleep(1)

            if log_detailed:
                if response.candidates:
                    candidate = response.candidates[0]
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, "thought") and part.thought:
                                thinking_was_used = True
                                log.info("--- 模型思考过程 (Thinking) ---")
                                log.info(part.text)
                                log.info("---------------------------------")

            function_calls = response.function_calls

            if not function_calls:
                if log_detailed:
                    log.info("--- 模型决策：直接生成文本回复 (未调用工具) ---")
                    log.info("模型返回了最终文本响应，工具调用流程结束。")
                break

            if log_detailed:
                log.info("--- 模型决策：建议进行工具调用 ---")
                for call in function_calls:
                    args_str = json.dumps(dict(call.args), ensure_ascii=False, indent=2)
                    log.info(f"  - 工具名称: {call.name}")
                    log.info(f"  - 调用参数:\n{args_str}")
                log.info("------------------------------------")

            for call in function_calls:
                called_tool_names.append(call.name)

            if response.candidates and response.candidates[0].content:
                conversation_history.append(response.candidates[0].content)

            if log_detailed:
                log.info(f"准备执行 {len(function_calls)} 个工具调用...")

            tool_result_parts = []
            tasks = [
                self.tool_service.execute_tool_call(
                    tool_call=call,
                    channel=channel,
                    author_id=user_id,
                    log_detailed=log_detailed,
                )
                for call in function_calls
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    log.error(f"执行工具时发生异常: {result}", exc_info=result)
                    tool_result_parts.append(
                        types.Part.from_function_response(
                            name="unknown_tool",
                            response={
                                "error": f"An exception occurred during tool execution: {str(result)}"
                            },
                        )
                    )
                else:
                    if result.function_response:
                        tool_name = result.function_response.name
                        original_result_str = result.function_response.response.get(
                            "result", ""
                        )
                        wrapped_result_str = (
                            prompt_service.build_tool_result_wrapper_prompt(
                                tool_name, original_result_str
                            )
                        )
                        new_response_part = types.Part.from_function_response(
                            name=tool_name,
                            response={"result": wrapped_result_str},
                        )
                        tool_result_parts.append(new_response_part)
                    else:
                        tool_result_parts.append(result)

            if log_detailed:
                log.info(
                    f"已收集 {len(tool_result_parts)} 个工具执行结果，准备将其返回给模型。"
                )

            conversation_history.append(
                types.Content(role="user", parts=tool_result_parts)
            )

            if i == max_calls - 1:
                log.warning("已达到最大工具调用限制，流程终止。")
                return "哎呀，我好像陷入了一个复杂的思考循环里，我们换个话题聊聊吧！"

        if response.parts:
            final_thought = ""
            final_text = ""
            for part in response.parts:
                if hasattr(part, "thought") and part.thought:
                    thinking_was_used = True
                    final_thought += part.text
                elif hasattr(part, "text"):
                    final_text += part.text

            if log_detailed:
                if final_thought:
                    log.info("--- 模型最终回复的思考过程 ---")
                    log.info(final_thought.strip())
                    log.info("-----------------------------")
                else:
                    log.info("--- 模型最终回复未提供明确的思考过程。---")

            raw_ai_response = final_text.strip()

            if raw_ai_response:
                from src.chat.services.context_service import context_service

                await context_service.update_user_conversation_history(
                    user_id, guild_id, message if message else "", raw_ai_response
                )
                formatted_response = await self._post_process_response(
                    raw_ai_response, user_id, guild_id
                )
                total_tokens = 0
                if response.usage_metadata:
                    total_tokens = response.usage_metadata.total_token_count

                log.info("--- Gemini API 请求摘要 ---")
                log.info(
                    f"  - 本次调用是否使用思考功能: {'是' if thinking_was_used else '否'}"
                )
                if thinking_was_used:
                    log.info(f"  - 思考过程Token消耗: {total_tokens}")

                if called_tool_names:
                    unique_tools = sorted(list(set(called_tool_names)))
                    log.info(
                        f"  - 调用了 {len(unique_tools)} 个工具: {', '.join(unique_tools)}"
                    )
                else:
                    log.info("  - 未调用任何工具。")
                log.info("--------------------------")

                return formatted_response

        elif response.prompt_feedback and response.prompt_feedback.block_reason:
            try:
                conversation_for_log = json.dumps(
                    GeminiService._serialize_for_logging(final_conversation),
                    ensure_ascii=False,
                    indent=2,
                )
                full_response_for_log = str(response)
                log.warning(
                    f"用户 {user_id} 的请求被安全策略阻止，原因: {response.prompt_feedback.block_reason}\n"
                    f"--- 完整的对话历史 ---\n{conversation_for_log}\n"
                    f"--- 完整的 API 响应 ---\n{full_response_for_log}"
                )
            except Exception as log_e:
                log.error(f"序列化被阻止的请求用于日志记录时出错: {log_e}")
                log.warning(
                    f"用户 {user_id} 的请求被安全策略阻止，原因: {response.prompt_feedback.block_reason} (详细内容记录失败)"
                )
            return "呜啊! 这个太色情啦,我不看我不看"
        else:
            log.warning(f"未能为用户 {user_id} 生成有效回复。")
            return "哎呀，我好像没太明白你的意思呢～可以再说清楚一点吗？✨"

    @_api_key_handler
    async def generate_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
        title: Optional[str] = None,
        client: Any = None,
    ) -> Optional[List[float]]:
        """
        为给定文本生成嵌入向量。
        """
        if not client:
            raise ValueError("装饰器未能提供客户端实例。")

        if not text or not text.strip():
            log.warning(
                f"generate_embedding 接收到空文本！text: '{text}', task_type: '{task_type}'"
            )
            return None

        loop = asyncio.get_event_loop()
        embed_config = types.EmbedContentConfig(task_type=task_type)
        if title and task_type == "retrieval_document":
            embed_config.title = title

        embedding_result = await loop.run_in_executor(
            self.executor,
            lambda: client.models.embed_content(
                model="gemini-embedding-001",
                contents=[types.Part(text=text)],
                config=embed_config,
            ),
        )

        if embedding_result and embedding_result.embeddings:
            return embedding_result.embeddings[0].values
        return None

    @_api_key_handler
    async def generate_text(
        self,
        prompt: str,
        temperature: float = None,
        model_name: Optional[str] = None,
        client: Any = None,
    ) -> Optional[str]:
        """
        一个用于简单文本生成的精简方法。
        不涉及对话历史或上下文，仅根据输入提示生成文本。
        非常适合用于如“查询重写”等内部任务。

        Args:
            prompt: 提供给模型的输入提示。
            temperature: 控制生成文本的随机性。如果为 None，则使用 config 中的默认值。
            model_name: 指定要使用的模型。如果为 None，则使用默认的聊天模型。

        Returns:
            生成的文本字符串，如果失败则返回 None。
        """
        if not client:
            raise ValueError("装饰器未能提供客户端实例。")

        loop = asyncio.get_event_loop()
        gen_config_params = app_config.GEMINI_TEXT_GEN_CONFIG.copy()
        if temperature is not None:
            gen_config_params["temperature"] = temperature
        gen_config = types.GenerateContentConfig(
            **gen_config_params, safety_settings=self.safety_settings
        )
        final_model_name = model_name or self.default_model_name

        response = await loop.run_in_executor(
            self.executor,
            lambda: client.models.generate_content(
                model=final_model_name, contents=[prompt], config=gen_config
            ),
        )

        if response.parts:
            return response.text.strip()
        return None

    @_api_key_handler
    async def generate_simple_response(
        self,
        prompt: str,
        generation_config: Dict,
        model_name: Optional[str] = None,
        client: Any = None,
    ) -> Optional[str]:
        """
        一个用于单次、非对话式文本生成的方法，允许传入完整的生成配置和可选的模型名称。
        非常适合用于如“礼物回应”、“投喂”等需要自定义生成参数的一次性任务。

        Args:
            prompt: 提供给模型的完整输入提示。
            generation_config: 一个包含生成参数的字典 (e.g., temperature, max_output_tokens).
            model_name: (可选) 指定要使用的模型。如果为 None，则使用默认的聊天模型。

        Returns:
            生成的文本字符串，如果失败则返回 None。
        """
        if not client:
            raise ValueError("装饰器未能提供客户端实例。")

        loop = asyncio.get_event_loop()
        gen_config = types.GenerateContentConfig(
            **generation_config, safety_settings=self.safety_settings
        )
        final_model_name = model_name or self.default_model_name

        response = await loop.run_in_executor(
            self.executor,
            lambda: client.models.generate_content(
                model=final_model_name, contents=[prompt], config=gen_config
            ),
        )

        if response.parts:
            return response.text.strip()

        log.warning(f"generate_simple_response 未能生成有效内容。API 响应: {response}")
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            log.warning(
                f"请求可能被安全策略阻止，原因: {response.prompt_feedback.block_reason}"
            )

        return None

    @_api_key_handler
    async def generate_thread_praise(
        self, conversation_history: List[Dict[str, Any]], client: Any = None
    ) -> Optional[str]:
        """
        专用于生成帖子夸奖的方法。
        现在接收一个由 prompt_service 构建好的完整对话历史。

        Args:
            conversation_history: 完整的对话历史列表。
            client: (由装饰器注入) Gemini 客户端。

        Returns:
            生成的夸奖文本，如果失败则返回 None。
        """
        if not client:
            raise ValueError("装饰器未能提供客户端实例。")

        loop = asyncio.get_event_loop()
        # --- (新增) 为暖贴功能启用思考 ---
        praise_config = app_config.GEMINI_THREAD_PRAISE_CONFIG.copy()
        thinking_budget = praise_config.pop("thinking_budget", None)

        gen_config = types.GenerateContentConfig(
            **praise_config,
            safety_settings=self.safety_settings,
        )

        if thinking_budget is not None:
            gen_config.thinking_config = types.ThinkingConfig(
                include_thoughts=True, thinking_budget=thinking_budget
            )
            log.info(f"已为暖贴功能启用思维链 (Thinking)，预算: {thinking_budget}。")

        final_model_name = self.default_model_name

        final_contents = self._prepare_api_contents(conversation_history)

        # 如果开启了 AI 完整上下文日志，则打印到终端
        if app_config.DEBUG_CONFIG["LOG_AI_FULL_CONTEXT"]:
            log.info("--- 暖贴功能 · 完整 AI 上下文 ---")
            log.info(
                json.dumps(
                    [
                        self._serialize_parts_for_logging_full(content)
                        for content in final_contents
                    ],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            log.info("------------------------------------")

        response = await loop.run_in_executor(
            self.executor,
            lambda: client.models.generate_content(
                model=final_model_name, contents=final_contents, config=gen_config
            ),
        )

        if response.parts:
            # --- (修正) 采用与主对话相同的逻辑，正确分离思考过程和最终回复 ---
            final_text = ""
            for part in response.parts:
                # 关键：只有当 part 不是思考过程时，才将其文本内容计入最终回复
                if hasattr(part, "thought") and part.thought:
                    # 这是思考过程，忽略它
                    pass
                elif hasattr(part, "text"):
                    # 这是最终回复
                    final_text += part.text
            return final_text.strip()

        log.warning(f"generate_thread_praise 未能生成有效内容。API 响应: {response}")
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            log.warning(
                f"请求可能被安全策略阻止，原因: {response.prompt_feedback.block_reason}"
            )

        return None

    async def summarize_for_rag(
        self,
        latest_query: str,
        user_name: str,
        conversation_history: Optional[List[Dict[str, any]]] = None,
    ) -> str:
        """
        根据用户的最新发言和可选的对话历史，生成一个用于RAG搜索的独立查询。

        Args:
            latest_query: 用户当前发送的最新消息。
            user_name: 提问用户的名字。
            conversation_history: (可选) 包含多轮对话的列表。

        Returns:
            一个精炼后的、适合向量检索的查询字符串。
        """
        if not latest_query:
            log.info("RAG summarization called with no latest_query.")
            return ""

        prompt = prompt_service.build_rag_summary_prompt(
            latest_query, user_name, conversation_history
        )
        summarized_query = await self.generate_text(
            prompt, temperature=0.0, model_name=app_config.QUERY_REWRITING_MODEL
        )

        if not summarized_query:
            log.info("RAG查询总结失败，将直接使用用户的原始查询。")
            return latest_query.strip()

        return summarized_query.strip().strip('"')

    async def clear_user_context(self, user_id: int, guild_id: int):
        """清除指定用户的对话上下文"""
        await chat_db_manager.clear_ai_conversation_context(user_id, guild_id)
        log.info(f"已清除用户 {user_id} 在服务器 {guild_id} 的对话上下文")

    def is_available(self) -> bool:
        """检查AI服务是否可用"""
        return self.key_rotation_service is not None

    @_api_key_handler
    async def generate_text_with_image(
        self, prompt: str, image_bytes: bytes, mime_type: str, client: Any = None
    ) -> Optional[str]:
        """
        一个用于简单图文生成的精简方法。
        不涉及对话历史或上下文，仅根据输入提示和图片生成文本。
        非常适合用于如“投喂”等一次性功能。

        Args:
            prompt: 提供给模型的输入提示。
            image_bytes: 图片的字节数据。
            mime_type: 图片的 MIME 类型 (e.g., 'image/jpeg', 'image/png').

        Returns:
            生成的文本字符串，如果失败则返回 None。
        """
        if not client:
            raise ValueError("装饰器未能提供客户端实例。")

        # --- 新增：处理 GIF 图片 ---
        if mime_type == "image/gif":
            try:
                log.info("检测到 GIF 图片，尝试提取第一帧...")
                with Image.open(io.BytesIO(image_bytes)) as img:
                    # 寻求第一帧并转换为 RGBA 以确保兼容性
                    img.seek(0)
                    # 创建一个新的 BytesIO 对象来保存转换后的图片
                    output_buffer = io.BytesIO()
                    # 将图片保存为 PNG 格式
                    img.save(output_buffer, format="PNG")
                    # 获取转换后的字节数据
                    image_bytes = output_buffer.getvalue()
                    # 更新 MIME 类型
                    mime_type = "image/png"
                    log.info("成功将 GIF 第一帧转换为 PNG。")
            except Exception as e:
                log.error(f"处理 GIF 图片时出错: {e}", exc_info=True)
                return "呜哇，我的眼睛跟不上啦！有点看花眼了"
        # --- GIF 处理结束 ---

        request_contents = [
            prompt,
            types.Part(inline_data=types.Blob(mime_type=mime_type, data=image_bytes)),
        ]
        gen_config = types.GenerateContentConfig(
            **app_config.GEMINI_VISION_GEN_CONFIG, safety_settings=self.safety_settings
        )

        response = await client.aio.models.generate_content(
            model=self.default_model_name, contents=request_contents, config=gen_config
        )

        if response.parts:
            return response.text.strip()
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
            log.warning(
                f"图文生成请求被安全策略阻止: {response.prompt_feedback.block_reason}"
            )
            return "为啥要投喂色图啊喂"

        log.warning(f"未能为图文生成有效回复。Response: {response}")
        return "我好像没看懂这张图里是什么，可以换一张或者稍后再试试吗？"

    @_api_key_handler
    async def generate_confession_response(
        self, prompt: str, client: Any = None
    ) -> Optional[str]:
        """
        专用于生成忏悔回应的方法。
        """
        if not client:
            raise ValueError("装饰器未能提供客户端实例。")

        gen_config = types.GenerateContentConfig(
            **app_config.GEMINI_CONFESSION_GEN_CONFIG,
            safety_settings=self.safety_settings,
        )
        final_model_name = self.default_model_name

        if app_config.DEBUG_CONFIG["LOG_AI_FULL_CONTEXT"]:
            log.info("--- 忏悔功能 · 完整 AI 上下文 ---")
            log.info(prompt)
            log.info("------------------------------------")

        response = await client.aio.models.generate_content(
            model=final_model_name, contents=[prompt], config=gen_config
        )

        if response.parts:
            return response.text.strip()

        log.warning(
            f"generate_confession_response 未能生成有效内容。API 响应: {response}"
        )
        if response.prompt_feedback and response.prompt_feedback.block_reason:
            log.warning(
                f"请求可能被安全策略阻止，原因: {response.prompt_feedback.block_reason}"
            )

        return None


# 全局实例
gemini_service = GeminiService()
