# -*- coding: utf-8 -*-

import discord
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import discord.abc

# 导入所需的服务
from src.chat.services.ai.service import ai_service
from src.chat.utils.prompt_utils import replace_emojis
from src.chat.services.prompt_service import prompt_service
from src.chat.services.context_service_test import get_context_service  # 导入测试服务
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.chat.features.affection.service.affection_service import affection_service
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.utils.database import chat_db_manager
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)
from src.chat.config import chat_config
from src.chat.config.chat_config import DEBUG_CONFIG
from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.services.ai.providers.base import GenerationConfig
from src.chat.services.ai.providers.provider_format import ProviderFormat, MessageFormat
from src.chat.services.persona_preference_service import persona_preference_service

log = logging.getLogger(__name__)


@dataclass
class ChatResult:
    """
    聊天响应结果，包含回复内容和工具调用元数据。

    Attributes:
        content: AI 生成的回复文本
        tools_called: 本次请求中 AI 调用过的工具名称列表
    """

    content: str
    tools_called: List[str] = field(default_factory=list)


class ChatService:
    """
    负责编排整个AI聊天响应流程。
    """

    async def should_process_message(self, message: discord.Message) -> bool:
        """
        执行前置检查，判断消息是否应该被处理，以避免不必要的"输入中"状态。
        """
        author = message.author
        guild_id = message.guild.id if message.guild else 0

        # 1. 全局聊天开关检查
        if not await chat_settings_service.is_chat_globally_enabled(guild_id):
            log.info(f"服务器 {guild_id} 全局聊天已禁用，跳过前置检查。")
            return False

        # 2. 频道/分类设置检查
        effective_config = {}
        if isinstance(message.channel, discord.abc.GuildChannel):
            effective_config = await chat_settings_service.get_effective_channel_config(
                message.channel
            )

        if not effective_config.get("is_chat_enabled", True):
            # 检查是否满足通行许可的例外条件
            pass_is_granted = False
            if isinstance(message.channel, discord.Thread) and message.channel.owner_id:
                # 修正逻辑：只有当帖主明确设置了个人CD时，才算拥有"通行许可"
                owner_id = message.channel.owner_id
                owner_config = await coin_service.get_thread_cooldown_settings(owner_id)

                if owner_config:
                    has_personal_cd = owner_config[
                        "thread_cooldown_seconds"
                    ] is not None or (
                        owner_config["thread_cooldown_duration"] is not None
                        and owner_config["thread_cooldown_limit"] is not None
                    )
                    if has_personal_cd:
                        pass_is_granted = True
                        log.info(
                            f"帖主 {owner_id} 拥有个人CD设置（通行许可），覆盖频道 {message.channel.id} 的聊天限制。"
                        )

            # 如果没有授予通行权，则按原逻辑返回 False
            if not pass_is_granted:
                log.info(f"频道 {message.channel.id} 聊天已禁用，跳过前置检查。")
                return False

        # 3. 新版冷却时间检查
        if await chat_settings_service.is_user_on_cooldown(
            author.id, message.channel.id, effective_config
        ):
            log.info(
                f"用户 {author.id} 在频道 {message.channel.id} 处于新版冷却状态，跳过前置检查。"
            )
            return False

        # 冷却检查通过后立即更新冷却时间戳，防止用户在AI处理期间重复调用
        await chat_settings_service.update_user_cooldown(
            author.id, message.channel.id, effective_config
        )

        # 4. 黑名单检查
        if await chat_db_manager.is_user_blacklisted(author.id, guild_id):
            log.info(f"用户 {author.id} 在服务器 {guild_id} 被拉黑，跳过前置检查。")
            return False

        return True

    async def handle_chat_message(
        self,
        message: discord.Message,
        processed_data: Dict[str, Any],
        guild_name: str,
        location_name: str,
    ) -> Optional[ChatResult]:
        """
        处理聊天消息，生成并返回AI的最终回复。

        Args:
            message (discord.Message): 原始的 discord 消息对象。
            processed_data (Dict[str, Any]): 由 MessageProcessor 处理后的数据。

        Returns:
            ChatResult: AI生成的回复结果（含工具调用元数据）。如果为 None，则表示不应回复。
        """
        author = message.author
        guild_id = message.guild.id if message.guild else 0

        # --- 获取最新的有效配置 ---
        effective_config = {}
        if isinstance(message.channel, discord.abc.GuildChannel):
            effective_config = await chat_settings_service.get_effective_channel_config(
                message.channel
            )

        # --- 个人记忆消息计数 ---
        user_profile_data = await world_book_service.get_profile_by_discord_id(
            author.id
        )

        user_content = processed_data["user_content"]
        replied_content = processed_data["replied_content"]
        image_data_list = processed_data["image_data_list"]

        try:
            # 2. --- 上下文与知识库检索 ---
            # 获取频道历史上下文
            channel_context = (
                await get_context_service().get_formatted_channel_history_new(
                    message.channel.id,
                    author.id,
                    guild_id,
                    exclude_message_id=message.id,
                )
            )

            # 构建备用搜索查询（供 gather_context 工具使用）
            rag_query = user_content
            if replied_content:
                rag_query = f"{replied_content}\n{user_content}"

            # 确保对话块在工具检索前创建（副作用必须保留）
            if user_profile_data:
                await personal_memory_service.check_and_create_block_before_reply(
                    user_id=author.id
                )

            # --- 新增：集中获取所有上下文数据 ---
            affection_status = await affection_service.get_affection_status(author.id)
            persona_style = await persona_preference_service.get_persona_style(str(author.id))

            # 3. --- 好感度与奖励更新（前置） ---
            try:
                # 在生成回复前更新好感度，以确保日志顺序正确
                await affection_service.increase_affection_on_message(author.id)
            except Exception as aff_e:
                log.error(f"增加用户 {author.id} 的好感度时出错: {aff_e}")

            try:
                # 发放每日首次对话奖励
                if await coin_service.grant_daily_message_reward(author.id):
                    log.info(f"已为用户 {author.id} 发放每日首次对话奖励。")
            except Exception as coin_e:
                log.error(f"为用户 {author.id} 发放每日对话奖励时出错: {coin_e}")

            # 4. --- 调用AI生成回复 ---
            # 记录发送给AI的核心上下文
            if DEBUG_CONFIG["LOG_FINAL_CONTEXT"]:
                log.info(f"发送给AI -> 最终上下文: {channel_context}")

            # --- 获取当前设置的AI模型 ---
            current_model = await chat_settings_service.get_current_ai_model()
            log.info(f"当前使用的AI模型: {current_model}")

            # --- [新增] 根据上下文确定用于工具设置的用户ID ---
            user_id_for_settings: Optional[str] = None
            if isinstance(message.channel, discord.Thread) and message.channel.owner_id:
                user_id_for_settings = str(message.channel.owner_id)
                log.info(
                    f"消息在帖子中，将使用帖主 {user_id_for_settings} 的工具设置。"
                )
            else:
                log.info("消息不在帖子中，将使用默认工具集。")
            # --- [结束] ---

            # 获取当前模型对应的 Provider
            provider_name = ai_service._model_to_provider.get(current_model)
            provider_instance = ai_service.get_provider(provider_name) if provider_name else None
            provider_type = provider_instance.provider_type if provider_instance else ""
            log.info(
                f"[Provider 映射调试] current_model={repr(current_model)}, "
                f"provider_name={repr(provider_name)}, "
                f"provider_type={repr(provider_type)}"
            )

            # 根据 Provider 类型确定输出格式
            message_format = ProviderFormat.get_message_format(provider_type)
            output_format = (
                "openai" if message_format == MessageFormat.OPENAI else "gemini"
            )

            # 使用 PromptService 构建消息
            messages = await prompt_service.build_chat_prompt(
                user_name=author.display_name,
                message=user_content,
                replied_message=replied_content,
                images=image_data_list if image_data_list else None,
                channel_context=channel_context,
                world_book_entries=None,
                affection_status=affection_status,
                guild_name=guild_name,
                location_name=location_name,
                personal_summary=None,
                user_profile_data=user_profile_data,
                model_name=current_model,
                channel=message.channel,
                conversation_memory=None,
                latest_block=None,
                output_format=output_format,
                persona_style=persona_style,
            )

            # 获取工具列表（根据 Provider 类型返回对应格式）
            tools = await ai_service.tool_service.get_dynamic_tools_for_context(
                user_id_for_settings, provider_type=provider_type
            )

            # 定义工具执行器（使用闭包追踪本次请求中调用的工具）
            _called_tools: List[str] = []
            _search_scopes: List[str] = []

            async def tool_executor(call, **kwargs):
                # 记录被调用的工具名称（兼容 dict 和 FunctionCall 对象）
                if isinstance(call, dict):
                    name = call.get("name", "")
                    args = call.get("arguments", {})
                else:
                    name = getattr(call, "name", "")
                    args = dict(call.args) if call.args else {}
                _called_tools.append(name)
                if name == "search":
                    _search_scopes.append(args.get("scope", "auto"))
                return await ai_service.tool_service.execute_tool_call(
                    call,
                    channel=message.channel,
                    user_id=author.id,
                    user_id_for_settings=user_id_for_settings,
                    user_name=author.display_name,
                    fallback_query=rag_query,
                    channel_context=channel_context,
                )

            # 创建生成配置（从数据库获取模型参数）
            from src.chat.services.ai.config.models import get_generation_config

            gen_params = get_generation_config(current_model)
            log.debug(
                f"模型 {current_model} 生成参数: "
                f"temperature={gen_params.temperature}, "
                f"top_p={gen_params.top_p}, top_k={gen_params.top_k}, "
                f"max_output_tokens={gen_params.max_output_tokens}, "
                f"thinking_budget_tokens={gen_params.thinking_budget_tokens}"
            )
            generation_config = GenerationConfig(
                temperature=gen_params.temperature,
                top_p=gen_params.top_p,
                top_k=gen_params.top_k,
                max_output_tokens=gen_params.max_output_tokens,
                presence_penalty=gen_params.presence_penalty,
                frequency_penalty=gen_params.frequency_penalty,
                thinking_budget_tokens=gen_params.thinking_budget_tokens,
            )

            # 调用 AIService
            result = await ai_service.generate_with_tools(
                messages=messages,
                config=generation_config,
                model=current_model,
                tools=tools,
                tool_executor=tool_executor,
                user_id_for_settings=user_id_for_settings,
            )

            # 记录模型使用统计
            # 解析模型 ID（支持 "provider:model" 格式）
            model_name, explicit_provider = ai_service.parse_model_id(current_model)
            if explicit_provider:
                provider_name = explicit_provider
            else:
                provider_name = ai_service._model_to_provider.get(model_name, "unknown")

            # 使用纯模型名记录（不含 provider 前缀）
            await chat_settings_service.increment_model_usage(
                model_name=model_name, provider_name=provider_name
            )
            log.debug(f"记录模型使用: {model_name} (Provider: {provider_name})")

            ai_response = result.content

            if not ai_response:
                log.warning(f"AI服务未返回回复（重试+故障转移均失败），跳过用户 {author.id}。")
                return None

            # --- 新增：调用新的个人记忆服务 ---
            # 在获得AI回复后，记录这次对话并根据需要触发总结
            # 传递 current_model 使总结逻辑跟随主模型
            if user_profile_data:
                try:
                    await personal_memory_service.update_and_conditionally_summarize_memory(
                        user_id=author.id,
                        user_name=author.display_name,
                        user_content=user_content,
                        ai_response=ai_response,
                        current_model=current_model,
                    )
                except Exception as mem_e:
                    log.error(
                        f"[ChatService] 用户 {author.id} 对话块总结失败，跳过: {mem_e}",
                        exc_info=True,
                    )

            # 5. --- 后处理与格式化 ---
            final_response = self._format_ai_response(ai_response)

            # --- 为特定工具调用添加后缀 ---
            if _search_scopes and any(
                scope in ("tutorial", "auto") for scope in _search_scopes
            ):
                final_response += chat_config.TUTORIAL_SEARCH_SUFFIX

            # 6. --- 异步执行后续任务（不阻塞回复） ---
            # 此处现在只应包含不影响核心回复流程的日志记录等任务
            # self._log_rag_summary(author, final_content, world_book_entries, final_response)

            log.info(f"已为用户 {author.display_name} 生成AI回复: {final_response}")
            return ChatResult(content=final_response, tools_called=_called_tools)

        except Exception as e:
            log.error(f"[ChatService] 处理聊天消息时出错: {e}", exc_info=True)
            return ChatResult(content="抱歉，处理你的消息时出现了问题，请稍后再试。")

    def _format_ai_response(self, ai_response: str) -> str:
        """清理和格式化AI的原始回复。"""
        # 移除可能包含的自身名字前缀
        bot_name_prefix = "类脑娘:"
        if ai_response.startswith(bot_name_prefix):
            ai_response = ai_response[len(bot_name_prefix) :].lstrip()
        # 将多段回复的双换行符替换为单换行符
        formatted_response = ai_response.replace("\n\n", "\n")
        # 转换表情包占位符为Discord自定义表情
        formatted_response = replace_emojis(formatted_response)
        return formatted_response

    async def _perform_post_response_tasks(
        self,
        author: discord.User,
        guild_id: int,
        query: str,
        rag_entries: list,
        response: str,
    ):
        """执行发送回复后的任务，如记录日志。"""
        # 好感度和奖励逻辑已前置，此处保留用于未来可能的其他后处理任务

        # 记录 RAG 诊断日志
        # self._log_rag_summary(author, query, rag_entries, response)
        pass

    def _log_rag_summary(
        self, author: discord.User, query: str, entries: list, response: str
    ):
        """生成并记录 RAG 诊断摘要日志。"""
        try:
            if entries:
                doc_details = []
                for entry in entries:
                    distance = entry.get("distance", "N/A")
                    distance_str = (
                        f"{distance:.4f}"
                        if isinstance(distance, (int, float))
                        else str(distance)
                    )
                    content = str(entry.get("content", "N/A")).replace("\n", "\n    ")
                    doc_details.append(
                        f"  - Doc ID: {entry.get('id', 'N/A')}, Distance: {distance_str}\n"
                        f"    Content: {content}"
                    )
                retrieved_docs_summary = "\n" + "\n".join(doc_details)
            else:
                retrieved_docs_summary = " N/A"

            summary_log_message = (
                f"\n--- RAG DIAGNOSTIC SUMMARY ---\n"
                f"User: {author} ({author.id})\n"
                f'Initial Query: "{query}"\n'
                f"Retrieved Docs:{retrieved_docs_summary}\n"
                f'Final AI Response: "{response}"\n'
                f"------------------------------"
            )
            log.info(summary_log_message)
        except Exception as log_e:
            log.error(f"生成 RAG 诊断摘要日志时出错: {log_e}")


# 创建一个单例
chat_service = ChatService()
