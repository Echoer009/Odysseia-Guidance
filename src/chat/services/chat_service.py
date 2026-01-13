# -*- coding: utf-8 -*-

import discord
import logging
from typing import Dict, Any, Optional
import discord.abc

# 导入所需的服务
from src.chat.services.gemini_service import gemini_service
from src.chat.services.context_service_test import context_service_test  # 导入测试服务
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.chat.features.affection.service.affection_service import affection_service
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.utils.database import chat_db_manager
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)
from src.chat.config.chat_config import PERSONAL_MEMORY_CONFIG, DEBUG_CONFIG
from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)

log = logging.getLogger(__name__)


class ChatService:
    """
    负责编排整个AI聊天响应流程。
    """

    async def should_process_message(self, message: discord.Message) -> bool:
        """
        执行前置检查，判断消息是否应该被处理，以避免不必要的“输入中”状态。
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
                # 修正逻辑：只有当帖主明确设置了个人CD时，才算拥有“通行许可”
                owner_id = message.channel.owner_id
                query = "SELECT thread_cooldown_seconds, thread_cooldown_duration, thread_cooldown_limit FROM user_coins WHERE user_id = ?"
                owner_config_row = await chat_db_manager._execute(
                    chat_db_manager._db_transaction, query, (owner_id,), fetch="one"
                )

                if owner_config_row:
                    has_personal_cd = owner_config_row[
                        "thread_cooldown_seconds"
                    ] is not None or (
                        owner_config_row["thread_cooldown_duration"] is not None
                        and owner_config_row["thread_cooldown_limit"] is not None
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
    ) -> Optional[str]:
        """
        处理聊天消息，生成并返回AI的最终回复。

        Args:
            message (discord.Message): 原始的 discord 消息对象。
            processed_data (Dict[str, Any]): 由 MessageProcessor 处理后的数据。

        Returns:
            str: AI生成的最终回复文本。如果为 None，则表示不应回复。
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
        # --- 个人记忆处理 ---
        user_profile = await chat_db_manager.get_user_profile(author.id)
        personal_summary = None
        has_personal_memory = user_profile and user_profile["has_personal_memory"]

        if has_personal_memory and user_profile:
            personal_summary = user_profile["personal_summary"]
            # 在所有对话中进行消息计数和触发总结
            log.debug(f"--- 个人记忆诊断: 用户 {author.id} ---")
            log.debug(
                f"步骤 1: 检查 has_personal_memory 状态。值为: {has_personal_memory}"
            )

            # 在所有对话中进行消息计数和触发总结
            log.debug(f"用户 {author.id} 已启用个人记忆，开始计数。")
            new_count = await personal_memory_service.increment_and_check_message_count(
                author.id, guild_id
            )
            log.debug(f"步骤 2: 消息计数器更新。新计数值为: {new_count}")

            summary_threshold = PERSONAL_MEMORY_CONFIG["summary_threshold"]
            log.debug(
                f"步骤 3: 检查是否达到阈值。当前计数: {new_count}, 阈值: {summary_threshold}"
            )

            if new_count >= summary_threshold:
                log.info(
                    f"用户 {author.id} 在 guild_id {guild_id} 的个人消息已达到 {new_count} 条，触发总结。"
                )
                await personal_memory_service.summarize_and_save_memory(
                    author.id, guild_id
                )
                await personal_memory_service.reset_message_count(author.id, guild_id)
            else:
                log.debug(
                    f"用户 {author.id} 在 guild_id {guild_id} 的个人消息计数 {new_count} 尚未达到阈值 {summary_threshold}，不触发总结。"
                )

        # 移除了对未开启个人记忆的私聊消息的特殊处理

        user_content = processed_data["user_content"]
        replied_content = processed_data["replied_content"]
        image_data_list = processed_data["image_data_list"]

        try:
            # 2. --- 上下文与知识库检索 ---
            # 获取频道历史上下文
            # 使用新的测试上下文服务
            channel_context = (
                await context_service_test.get_formatted_channel_history_new(
                    message.channel.id,
                    author.id,
                    guild_id,
                    exclude_message_id=message.id,
                )
            )

            # RAG: 从世界书检索相关条目
            # --- RAG 查询优化 ---
            # 如果存在回复内容，则将其与用户当前消息合并，为RAG搜索提供更完整的上下文
            rag_query = user_content
            if replied_content:
                # replied_content 已包含 "> [回复 xxx]:" 等格式
                rag_query = f"{replied_content}\n{user_content}"

            log.info(f"为 RAG 搜索生成的查询: '{rag_query}'")

            world_book_entries = await world_book_service.find_entries(
                latest_query=rag_query,  # 使用合并后的查询
                user_id=author.id,
                guild_id=guild_id,
                user_name=author.display_name,
                conversation_history=channel_context,
            )

            # --- 新增：集中获取所有上下文数据 ---
            affection_status = await affection_service.get_affection_status(author.id)
            user_profile_data = dict(user_profile) if user_profile else None

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
            # PromptService 内部会处理合并用户消息的逻辑，这里我们总是传递 final_content
            # 记录发送给AI的核心上下文
            if DEBUG_CONFIG["LOG_FINAL_CONTEXT"]:
                log.info(f"发送给AI -> 最终上下文: {channel_context}")

            # --- 获取当前设置的AI模型 ---
            current_model = await chat_settings_service.get_current_ai_model()
            log.info(f"当前使用的AI模型: {current_model}")

            ai_response = await gemini_service.generate_response(
                author.id,
                guild_id,
                message=user_content,
                channel=message.channel,
                replied_message=replied_content,
                images=image_data_list if image_data_list else None,
                user_name=author.display_name,
                channel_context=channel_context,
                world_book_entries=world_book_entries,
                personal_summary=personal_summary,
                affection_status=affection_status,
                user_profile_data=user_profile_data,
                guild_name=guild_name,
                location_name=location_name,
                model_name=current_model,  # 传递模型名称
            )

            if not ai_response:
                log.info(f"AI服务未返回回复（可能由于冷却），跳过用户 {author.id}。")
                return None

            # 更新新系统的CD
            await chat_settings_service.update_user_cooldown(
                author.id, message.channel.id, effective_config
            )

            # 5. --- 后处理与格式化 ---
            final_response = self._format_ai_response(ai_response)

            # 6. --- 异步执行后续任务（不阻塞回复） ---
            # 此处现在只应包含不影响核心回复流程的日志记录等任务
            # self._log_rag_summary(author, final_content, world_book_entries, final_response)

            log.info(f"已为用户 {author.display_name} 生成AI回复: {final_response}")
            return final_response

        except Exception as e:
            log.error(f"[ChatService] 处理聊天消息时出错: {e}", exc_info=True)
            return "抱歉，处理你的消息时出现了问题，请稍后再试。"

    def _format_ai_response(self, ai_response: str) -> str:
        """清理和格式化AI的原始回复。"""
        # 移除可能包含的自身名字前缀
        bot_name_prefix = "类脑娘:"
        if ai_response.startswith(bot_name_prefix):
            ai_response = ai_response[len(bot_name_prefix) :].lstrip()
        # 将多段回复的双换行符替换为单换行符
        return ai_response.replace("\n\n", "\n")

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
