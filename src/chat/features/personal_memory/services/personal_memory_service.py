import logging
import sqlite3
import os
from typing import Dict
from datetime import datetime

from src.chat.utils.database import chat_db_manager
from src.chat.config.chat_config import (
    PERSONAL_MEMORY_CONFIG,
    PROMPT_CONFIG,
    SUMMARY_MODEL,
    GEMINI_SUMMARY_GEN_CONFIG,
)

# 新增导入，用于获取频道历史
from src import config

log = logging.getLogger(__name__)


class PersonalMemoryService:
    def __init__(self):
        self.db_manager = chat_db_manager
        self.world_book_db_path = os.path.join(config.DATA_DIR, "world_book.sqlite3")
        # 用于追踪需要监听反应的投票消息 ID 及其发起时间
        self.approval_message_ids: Dict[int, datetime] = {}

    def _get_world_book_connection(self):
        """获取世界书数据库的连接"""
        try:
            conn = sqlite3.connect(self.world_book_db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            log.error(f"连接到世界书数据库失败: {e}", exc_info=True)
            return None

    async def increment_and_check_message_count(
        self, user_id: int, guild_id: int
    ) -> int:
        """
        增加用户的个人消息计数，并返回新的计数值。
        guild_id 用于区分私聊 (0) 和频道对话。
        """
        log.debug(f"开始为用户 {user_id} 在 guild_id {guild_id} 增加个人消息计数。")
        new_count = await self.db_manager.increment_personal_message_count(
            user_id, guild_id=guild_id
        )
        log.debug(
            f"用户 {user_id} 在 guild_id {guild_id} 的个人消息计数已更新为: {new_count}"
        )
        return new_count

    async def reset_message_count(self, user_id: int, guild_id: int):
        """重置用户在指定 guild_id 下的个人消息计数器。"""
        await self.db_manager.reset_personal_message_count(user_id, guild_id=guild_id)
        log.debug(f"已重置用户 {user_id} 在 guild_id {guild_id} 的个人消息计数器。")

    async def summarize_and_save_memory(self, user_id: int, guild_id: int):
        """获取用户的对话历史（根据 guild_id 区分私聊和频道），生成摘要，并保存到数据库。"""
        # 延迟导入以避免循环依赖
        from src.chat.services.gemini_service import gemini_service

        log.info(
            f"用户 {user_id} 在 guild_id {guild_id} 的个人消息已达到 {PERSONAL_MEMORY_CONFIG['summary_threshold']} 条，触发总结。"
        )
        log.debug(
            f"=== 开始为用户 {user_id} 在 guild_id {guild_id} 生成个人记忆摘要 ==="
        )

        # 1. 获取对话历史
        log.debug(
            f"步骤 1: 正在为用户 {user_id} 获取 guild_id {guild_id} 的对话历史..."
        )
        context = await self.db_manager.get_ai_conversation_context(user_id, guild_id)

        if not context:
            log.warning(f"用户 {user_id} 在 guild_id {guild_id} 没有对话上下文记录。")
            return

        log.debug(f"获取到的上下文结构: {list(context.keys()) if context else 'None'}")

        if not context or not context["conversation_history"]:
            log.warning(
                f"用户 {user_id} 在 guild_id {guild_id} 没有可供总结的对话历史。"
            )
            log.debug(
                f"对话历史内容: {context['conversation_history'] if context else 'No context'}"
            )
            return

        conversation_history = context["conversation_history"]
        log.debug(f"对话历史长度: {len(conversation_history)} 条消息")

        # 2. 格式化对话历史为纯文本
        dialogue_text = ""
        for i, turn in enumerate(conversation_history):
            role = "用户" if turn.get("role") == "user" else "模型"
            parts = turn.get("parts", [])
            content = " ".join(str(p) for p in parts if isinstance(p, str))
            if content:
                dialogue_text += f"{role}: {content}\n"
            log.debug(f"消息 {i + 1}: {role} - {content[:50]}...")

        if not dialogue_text.strip():
            log.warning(f"用户 {user_id} 的对话历史为空或格式不正确，无法总结。")
            log.debug(f"原始对话历史: {conversation_history}")
            return

        log.debug(f"格式化后的对话文本长度: {len(dialogue_text)} 字符")

        # 3. 获取旧摘要
        user_profile = await self.db_manager.get_user_profile(user_id)
        old_summary = (
            user_profile["personal_summary"]
            if user_profile and user_profile["personal_summary"]
            else "无"
        )
        log.debug(f"获取到用户 {user_id} 的过往记忆摘要，长度: {len(old_summary)} 字符")
        log.debug(
            f"[MEMORY_SUMMARY] 过往记忆摘要:\n--- OLD SUMMARY ---\n{old_summary}\n-------------------"
        )

        # 4. 构建 Prompt 并调用 AI 生成摘要
        prompt_template = PROMPT_CONFIG.get("personal_memory_summary")
        if not prompt_template:
            log.error("在 PROMPT_CONFIG 中未找到 'personal_memory_summary'。")
            return

        final_prompt = prompt_template.format(
            old_summary=old_summary, dialogue_history=dialogue_text
        )
        log.debug(
            f"[MEMORY_SUMMARY] 用于总结的近期对话:\n--- DIALOGUE HISTORY ---\n{dialogue_text}\n------------------------"
        )
        log.debug(f"步骤 2: 构建分层总结Prompt完成，长度: {len(final_prompt)} 字符")
        log.debug(f"完整Prompt预览: {final_prompt[:300]}...")

        log.debug("步骤 3: 调用AI生成精炼摘要...")
        # 调用增强后的 simple_response 函数，传入完整的配置和模型名称
        new_summary = await gemini_service.generate_simple_response(
            prompt=final_prompt,
            generation_config=GEMINI_SUMMARY_GEN_CONFIG,
            model_name=SUMMARY_MODEL,
        )

        # 5. 保存摘要到数据库
        if new_summary:
            log.debug(
                f"步骤 4: 成功为用户 {user_id} 生成新的精炼摘要，长度: {len(new_summary)} 字符"
            )
            log.debug(f"新摘要内容预览: {new_summary[:150]}...")
            log.debug(
                f"[MEMORY_SUMMARY] AI生成的新摘要:\n--- NEW SUMMARY ---\n{new_summary}\n-------------------"
            )

            # 使用新摘要完全替换旧摘要
            await self.db_manager.update_personal_summary(user_id, new_summary)
            log.info(f"已成功为用户 {user_id} 更新记忆摘要。")
            log.info(f"步骤 5: 成功为用户 {user_id} 生成并覆盖保存了新的个人记忆摘要。")
        else:
            log.error(f"为用户 {user_id} 生成个人记忆摘要失败。AI服务返回空结果。")

        # 无论总结成功与否，都重置计数器
        await self.reset_message_count(user_id, guild_id)
        log.debug(f"步骤 6: 已重置用户 {user_id} 在 guild_id {guild_id} 的消息计数器。")

        log.debug(f"=== 用户 {user_id} 的个人记忆摘要生成过程结束 ===")

    async def unlock_feature(self, user_id: int):
        """为用户直接解锁个人记忆功能。"""
        # 首先检查用户是否存在，如果不存在则创建用户记录
        user_profile = await self.db_manager.get_user_profile(user_id)
        if not user_profile:
            # 用户不存在，先插入记录
            insert_query = "INSERT INTO users (user_id, has_personal_memory, personal_summary) VALUES (?, 1, NULL)"
            await self.db_manager._execute(
                self.db_manager._db_transaction, insert_query, (user_id,), commit=True
            )
            log.info(f"已为用户 {user_id} 创建记录并解锁个人记忆功能。")
        else:
            # 用户已存在，更新记录
            update_query = "UPDATE users SET has_personal_memory = 1 WHERE user_id = ?"
            await self.db_manager._execute(
                self.db_manager._db_transaction, update_query, (user_id,), commit=True
            )
            log.info(f"已为用户 {user_id} 解锁个人记忆功能。")

        # 注意：由于我们没有 discord.Member 对象，我们无法直接发送私信提示用户创建档案。
        # 这个提示将在用户下次与机器人互动时触发（例如，通过 /个人档案 命令或在聊天中）。

    async def get_memory_summary(self, user_id: int) -> str:
        """根据用户ID获取其个人记忆摘要。"""
        log.debug(f"正在为用户 {user_id} 查询个人记忆摘要...")
        user_profile = await self.db_manager.get_user_profile(user_id)
        if user_profile and user_profile["personal_summary"]:
            log.debug(f"成功找到用户 {user_id} 的记忆摘要。")
            return user_profile["personal_summary"]
        else:
            log.debug(f"用户 {user_id} 没有找到个人记忆摘要。")
            return "该用户当前没有个人记忆摘要。"

    async def update_memory_summary(self, user_id: int, new_summary: str):
        """更新指定用户的个人记忆摘要。"""
        log.debug(f"准备为用户 {user_id} 更新个人记忆摘要...")
        await self.db_manager.update_personal_summary(user_id, new_summary)
        log.info(f"已成功为用户 {user_id} 更新记忆摘要。")


# 单例实例
personal_memory_service = PersonalMemoryService()
