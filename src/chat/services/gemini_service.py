# -*- coding: utf-8 -*-

import os
import logging
from typing import Optional, Dict, List, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import re
import random

from PIL import Image
import io

from google.genai import types

from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config as app_config
from src.chat.config.emoji_config import EMOJI_MAPPINGS, FACTION_EMOJI_MAPPINGS
from src.chat.services.event_service import event_service
from src.chat.services.prompt_service import prompt_service
from src.core.llm.gemini_client import GeminiApiClient, NoAvailableKeyError
from src.chat.features.tools.services.tool_service import ToolService
from src.chat.features.tools.tool_loader import load_tools_from_directory

log = logging.getLogger(__name__)


class GeminiService:
    """
    Gemini AI 服务类，负责处理应用的高层业务逻辑，
    并通过底层的 GeminiApiClient 与 Google API 交互。
    """

    def __init__(self):
        self.bot = None

        google_api_keys_str = os.getenv("GOOGLE_API_KEYS_LIST", "")
        processed_keys_str = google_api_keys_str.strip().strip('"')
        api_keys = [key.strip() for key in processed_keys_str.split(",") if key.strip()]

        self.api_client = GeminiApiClient(api_keys=api_keys)

        self.default_model_name = app_config.GEMINI_MODEL
        self.executor = ThreadPoolExecutor(
            max_workers=app_config.MAX_CONCURRENT_REQUESTS
        )

        self.available_tools, self.tool_map = load_tools_from_directory(
            "src/chat/features/tools/functions"
        )
        self.tool_service = ToolService(bot=None, tool_map=self.tool_map)
        log.info(
            f"Loaded {len(self.available_tools)} tools: {list(self.tool_map.keys())}"
        )

    def set_bot(self, bot):
        self.bot = bot
        self.tool_service.bot = bot
        log.info("Discord Bot instance injected into GeminiService and ToolService.")

    async def get_user_conversation_history(
        self, user_id: int, guild_id: int
    ) -> List[Dict]:
        context = await chat_db_manager.get_ai_conversation_context(user_id, guild_id)
        return context.get("conversation_history", [])

    @staticmethod
    def _serialize_for_logging(obj):
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
        try:
            json.JSONEncoder().default(obj)
            return obj
        except TypeError:
            return str(obj)

    @staticmethod
    def _serialize_parts_for_logging_full(content: types.Content):
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
                        "data_preview": part.inline_data.data[:50].hex() + "...",
                    }
                )
            else:
                serialized_parts.append({"type": "unknown_part", "content": str(part)})
        return {"role": content.role, "parts": serialized_parts}

    def _prepare_api_contents(self, conversation: List[Dict]) -> List[types.Content]:
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

    async def _post_process_response(self, raw_response: str) -> str:
        reply_prefix_pattern = re.compile(
            r"^\s*([\[［]【回复|回复}\s*@.*?[\)）\]］])\s*", re.IGNORECASE
        )
        formatted = reply_prefix_pattern.sub("", raw_response)
        formatted = re.sub(
            r"<CURRENT_USER_MESSAGE_TO_REPLY.*?>", "", formatted, flags=re.IGNORECASE
        )
        discord_emoji_pattern = re.compile(r":\w+:")
        formatted = discord_emoji_pattern.sub("", formatted)

        active_event = event_service.get_active_event()
        selected_faction = event_service.get_selected_faction()
        emoji_map_to_use = EMOJI_MAPPINGS

        if active_event and selected_faction:
            event_id = active_event.get("event_id")
            faction_map = FACTION_EMOJI_MAPPINGS.get(event_id, {}).get(selected_faction)
            if faction_map:
                log.info(
                    f"Using faction-specific emojis for event '{event_id}', faction '{selected_faction}'."
                )
                emoji_map_to_use = faction_map

        for pattern, emojis in emoji_map_to_use:
            if isinstance(emojis, list) and emojis:
                selected_emoji = random.choice(emojis)
                formatted = pattern.sub(selected_emoji, formatted)
            elif isinstance(emojis, str):
                formatted = pattern.sub(emojis, formatted)

        return formatted

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
        try:
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
            )

            chat_config = app_config.GEMINI_CHAT_CONFIG.copy()
            thinking_budget = chat_config.pop("thinking_budget", None)
            gen_config_params = {
                **chat_config,
                "safety_settings": self.api_client.safety_settings,
            }

            if self.available_tools:
                gen_config_params["tools"] = self.available_tools
                gen_config_params["automatic_function_calling"] = (
                    types.AutomaticFunctionCallingConfig(disable=True)
                )

            gen_config = types.GenerateContentConfig(**gen_config_params)

            if thinking_budget is not None:
                gen_config.thinking_config = types.ThinkingConfig(
                    include_thoughts=True, thinking_budget=thinking_budget
                )

            conversation_history = self._prepare_api_contents(final_conversation)

            if app_config.DEBUG_CONFIG["LOG_AI_FULL_CONTEXT"]:
                log.info(
                    f"--- Initial AI Context (User {user_id}) ---\n{json.dumps([self._serialize_parts_for_logging_full(c) for c in conversation_history], ensure_ascii=False, indent=2)}"
                )

            called_tool_names = []
            thinking_was_used = False
            max_calls = 5
            for i in range(max_calls):
                log_detailed = app_config.DEBUG_CONFIG.get(
                    "LOG_DETAILED_GEMINI_PROCESS", False
                )
                if log_detailed:
                    log.info(
                        f"--- [Tool Calling Loop: Iteration {i + 1}/{max_calls}] ---"
                    )

                response = await self.api_client.generate_content(
                    model_name=(model_name or self.default_model_name),
                    contents=conversation_history,
                    generation_config=gen_config,
                )

                if (
                    log_detailed
                    and response.candidates
                    and response.candidates[0].content
                ):
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "thought") and part.thought:
                            thinking_was_used = True
                            log.info(f"--- Model Thought Process ---\n{part.text}")

                function_calls = response.function_calls
                if not function_calls:
                    break

                if log_detailed:
                    for call in function_calls:
                        log.info(
                            f"--- Model decision: Recommend tool call ---\nTool: {call.name}\nArguments:\n{json.dumps(dict(call.args), ensure_ascii=False, indent=2)}"
                        )

                called_tool_names.extend([call.name for call in function_calls])

                if response.candidates and response.candidates[0].content:
                    conversation_history.append(response.candidates[0].content)

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

                tool_result_parts = []
                for result in results:
                    if isinstance(result, Exception):
                        log.error(
                            f"Exception during tool execution: {result}",
                            exc_info=result,
                        )
                        tool_result_parts.append(
                            types.Part.from_function_response(
                                name="unknown_tool",
                                response={
                                    "error": f"An exception occurred: {str(result)}"
                                },
                            )
                        )
                    elif result.function_response:
                        tool_name = result.function_response.name
                        original_result_str = result.function_response.response.get(
                            "result", ""
                        )
                        wrapped_result_str = (
                            prompt_service.build_tool_result_wrapper_prompt(
                                tool_name, original_result_str
                            )
                        )
                        tool_result_parts.append(
                            types.Part.from_function_response(
                                name=tool_name, response={"result": wrapped_result_str}
                            )
                        )
                    else:
                        tool_result_parts.append(result)

                conversation_history.append(
                    types.Content(role="user", parts=tool_result_parts)
                )

                if i == max_calls - 1:
                    log.warning("Max tool call limit reached.")
                    return (
                        "哎呀，我好像陷入了一个复杂的思考循环里，我们换个话题聊聊吧！"
                    )

            if response.parts:
                final_text = "".join(
                    part.text
                    for part in response.parts
                    if hasattr(part, "text")
                    and not (hasattr(part, "thought") and part.thought)
                )
                raw_ai_response = final_text.strip()

                if raw_ai_response:
                    from src.chat.services.context_service import context_service

                    await context_service.update_user_conversation_history(
                        user_id, guild_id, message or "", raw_ai_response
                    )
                    formatted_response = await self._post_process_response(
                        raw_ai_response
                    )

                    log.info(
                        f"--- Gemini API Request Summary ---\nThinking used: {'Yes' if thinking_was_used else 'No'}\nTools called: {', '.join(sorted(list(set(called_tool_names)))) if called_tool_names else 'None'}"
                    )

                    return formatted_response

            if response.prompt_feedback and response.prompt_feedback.block_reason:
                log.warning(
                    f"Request for user {user_id} blocked by safety policy: {response.prompt_feedback.block_reason}"
                )
                return "呜啊! 这个太色情啦,我不看我不看"

            log.warning(f"Failed to generate a valid response for user {user_id}.")
            return "哎呀，我好像没太明白你的意思呢～可以再说清楚一点吗？✨"

        except NoAvailableKeyError:
            log.error("All API keys are unavailable.")
            return "啊啊啊服务器要爆炸啦！现在有点忙不过来，你过一会儿再来找我玩吧！"
        except Exception as e:
            log.error(
                f"Error in generate_response for user {user_id}: {e}", exc_info=True
            )
            return "抱歉，处理你的消息时出现了问题，请稍后再试。"

    async def generate_embedding(
        self,
        text: str,
        task_type: str = "retrieval_document",
        title: Optional[str] = None,
    ) -> Optional[List[float]]:
        if not text or not text.strip():
            log.warning(
                f"generate_embedding received empty text for task_type: '{task_type}'"
            )
            return None
        try:
            embed_config = types.EmbedContentConfig(task_type=task_type)
            if title and task_type == "retrieval_document":
                embed_config.title = title

            embedding_result = await self.api_client.embed_content(
                model_name="gemini-embedding-001",
                contents=[types.Part(text=text)],
                embedding_config=embed_config,
            )
            if embedding_result and embedding_result.embeddings:
                return embedding_result.embeddings[0].values
            return None
        except Exception as e:
            log.error(f"Error generating embedding: {e}", exc_info=True)
            return None

    async def generate_text(
        self, prompt: str, temperature: float = None, model_name: Optional[str] = None
    ) -> Optional[str]:
        try:
            gen_config_params = app_config.GEMINI_TEXT_GEN_CONFIG.copy()
            if temperature is not None:
                gen_config_params["temperature"] = temperature
            gen_config = types.GenerateContentConfig(
                **gen_config_params, safety_settings=self.api_client.safety_settings
            )

            response = await self.api_client.generate_content(
                model_name=(model_name or self.default_model_name),
                contents=[prompt],
                generation_config=gen_config,
            )
            if response.parts:
                return response.text.strip()
            return None
        except Exception as e:
            log.error(f"Error in generate_text: {e}", exc_info=True)
            return None

    async def generate_simple_response(
        self, prompt: str, generation_config: Dict, model_name: Optional[str] = None
    ) -> Optional[str]:
        try:
            gen_config = types.GenerateContentConfig(
                **generation_config, safety_settings=self.api_client.safety_settings
            )
            response = await self.api_client.generate_content(
                model_name=(model_name or self.default_model_name),
                contents=[prompt],
                generation_config=gen_config,
            )
            if response.parts:
                return response.text.strip()
            log.warning(f"generate_simple_response failed. API response: {response}")
            return None
        except Exception as e:
            log.error(f"Error in generate_simple_response: {e}", exc_info=True)
            return None

    async def generate_thread_praise(
        self, conversation_history: List[Dict[str, Any]]
    ) -> Optional[str]:
        try:
            praise_config = app_config.GEMINI_THREAD_PRAISE_CONFIG.copy()
            thinking_budget = praise_config.pop("thinking_budget", None)
            gen_config = types.GenerateContentConfig(
                **praise_config, safety_settings=self.api_client.safety_settings
            )
            if thinking_budget is not None:
                gen_config.thinking_config = types.ThinkingConfig(
                    include_thoughts=True, thinking_budget=thinking_budget
                )

            final_contents = self._prepare_api_contents(conversation_history)

            response = await self.api_client.generate_content(
                model_name=self.default_model_name,
                contents=final_contents,
                generation_config=gen_config,
            )
            if response.parts:
                return "".join(
                    part.text
                    for part in response.parts
                    if hasattr(part, "text")
                    and not (hasattr(part, "thought") and part.thought)
                ).strip()
            log.warning(f"generate_thread_praise failed. API response: {response}")
            return None
        except Exception as e:
            log.error(f"Error in generate_thread_praise: {e}", exc_info=True)
            return None

    async def summarize_for_rag(
        self,
        latest_query: str,
        user_name: str,
        conversation_history: Optional[List[Dict[str, any]]] = None,
    ) -> str:
        if not latest_query:
            return ""
        prompt = prompt_service.build_rag_summary_prompt(
            latest_query, user_name, conversation_history
        )
        summarized_query = await self.generate_text(
            prompt, temperature=0.0, model_name=app_config.QUERY_REWRITING_MODEL
        )
        return (summarized_query or latest_query).strip().strip('"')

    async def clear_user_context(self, user_id: int, guild_id: int):
        await chat_db_manager.clear_ai_conversation_context(user_id, guild_id)
        log.info(f"Cleared conversation context for user {user_id} in guild {guild_id}")

    def is_available(self) -> bool:
        return self.api_client is not None

    async def generate_text_with_image(
        self, prompt: str, image_bytes: bytes, mime_type: str
    ) -> Optional[str]:
        try:
            if mime_type == "image/gif":
                with Image.open(io.BytesIO(image_bytes)) as img:
                    img.seek(0)
                    output_buffer = io.BytesIO()
                    img.save(output_buffer, format="PNG")
                    image_bytes = output_buffer.getvalue()
                    mime_type = "image/png"

            request_contents = [
                prompt,
                types.Part(
                    inline_data=types.Blob(mime_type=mime_type, data=image_bytes)
                ),
            ]
            gen_config = types.GenerateContentConfig(
                **app_config.GEMINI_VISION_GEN_CONFIG,
                safety_settings=self.api_client.safety_settings,
            )
            response = await self.api_client.generate_content(
                model_name=self.default_model_name,
                contents=request_contents,
                generation_config=gen_config,
            )
            if response.parts:
                return response.text.strip()
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                log.warning(
                    f"Image generation request blocked by safety policy: {response.prompt_feedback.block_reason}"
                )
                return "为啥要投喂色图啊喂"
            return "我好像没看懂这张图里是什么，可以换一张或者稍后再试试吗？"
        except Exception as e:
            log.error(f"Error in generate_text_with_image: {e}", exc_info=True)
            return "呜哇，我的眼睛跟不上啦！有点看花眼了"

    async def generate_confession_response(self, prompt: str) -> Optional[str]:
        try:
            gen_config = types.GenerateContentConfig(
                **app_config.GEMINI_CONFESSION_GEN_CONFIG,
                safety_settings=self.api_client.safety_settings,
            )
            response = await self.api_client.generate_content(
                model_name=self.default_model_name,
                contents=[prompt],
                generation_config=gen_config,
            )
            if response.parts:
                return response.text.strip()
            log.warning(
                f"generate_confession_response failed. API response: {response}"
            )
            return None
        except Exception as e:
            log.error(f"Error in generate_confession_response: {e}", exc_info=True)
            return None


gemini_service = GeminiService()
