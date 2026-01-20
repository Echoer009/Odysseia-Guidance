import logging
from typing import Optional
from sqlalchemy.future import select
from sqlalchemy import update
from src.database.database import AsyncSessionLocal
from src.database.models import CommunityMemberProfile
from src.chat.config.chat_config import (
    PROMPT_CONFIG,
    SUMMARY_MODEL,
    GEMINI_SUMMARY_GEN_CONFIG,
    PERSONAL_MEMORY_CONFIG,
)
from src.chat.services.gemini_service import gemini_service

log = logging.getLogger(__name__)


class PersonalMemoryService:
    async def update_and_conditionally_summarize_memory(
        self, user_id: int, user_name: str, user_content: str, ai_response: str
    ):
        """
        核心入口：更新对话历史和计数，并在达到阈值时触发总结。
        所有数据库操作都在ParadeDB中完成。
        """
        should_summarize = False
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 使用 SELECT ... FOR UPDATE 锁定行，确保事务安全
                stmt = (
                    select(CommunityMemberProfile)
                    .where(CommunityMemberProfile.discord_id == str(user_id))
                    .with_for_update()
                )
                result = await session.execute(stmt)
                profile = result.scalars().first()

                if not profile:
                    log.warning(
                        f"用户 {user_id} 在ParadeDB中没有档案，无法记录个人记忆。"
                    )
                    return

                # 更新计数和历史
                # 使用 getattr 和 setattr 明确处理类型，以消除 Pylance 警告
                current_count = getattr(profile, "personal_message_count", 0)
                new_count = current_count + 1
                setattr(profile, "personal_message_count", new_count)

                new_turn = {"role": "user", "parts": [user_content]}
                new_model_turn = {"role": "model", "parts": [ai_response]}

                log.info(
                    f"用户 {user_id} 的新对话轮次将被添加到历史记录: {user_name}: '{user_content}', 类脑娘: '{ai_response}'"
                )

                current_history = getattr(profile, "history", [])
                new_history = list(current_history or [])
                new_history.extend([new_turn, new_model_turn])
                setattr(profile, "history", new_history)

                log.debug(f"用户 {user_id} 消息计数更新为: {new_count}")

                if new_count >= PERSONAL_MEMORY_CONFIG["summary_threshold"]:
                    should_summarize = True

        # 在主事务之外执行总结，避免长时间锁定
        if should_summarize:
            await self._summarize_memory(user_id)

    async def _summarize_memory(self, user_id: int):
        """私有方法：获取历史，生成摘要，并清空计数和历史。"""
        log.info(f"用户 {user_id} 达到阈值，触发总结。")

        async with AsyncSessionLocal() as session:
            # 1. 获取需要总结的数据
            stmt = select(
                CommunityMemberProfile.personal_summary, CommunityMemberProfile.history
            ).where(CommunityMemberProfile.discord_id == str(user_id))
            result = await session.execute(stmt)
            data = result.first()

            if not data or not data.history:
                log.warning(f"用户 {user_id} 无历史可供总结。")
                return

            old_summary, conversation_history = data
            old_summary = old_summary or "无"

        # 2. 格式化对话历史
        dialogue_text = "\n".join(
            f"{'用户' if turn.get('role') == 'user' else 'AI'}: {' '.join(map(str, turn.get('parts', [])))}"
            for turn in conversation_history
        ).strip()

        if not dialogue_text:
            log.warning(f"用户 {user_id} 的对话历史格式化后为空。")
            return

        # 3. 构建 Prompt 并调用 AI 生成新摘要
        prompt_template = PROMPT_CONFIG.get("personal_memory_summary")
        if not prompt_template:
            log.error("未找到 'personal_memory_summary' 的 prompt 模板。")
            return

        final_prompt = prompt_template.format(
            old_summary=old_summary, dialogue_history=dialogue_text
        )
        new_summary = await gemini_service.generate_simple_response(
            prompt=final_prompt,
            generation_config=GEMINI_SUMMARY_GEN_CONFIG,
            model_name=SUMMARY_MODEL,
        )

        # 4. 将新摘要保存到数据库，并清空历史和计数器
        if new_summary:
            await self.update_summary_and_reset_history(user_id, new_summary)
        else:
            log.error(f"为用户 {user_id} 生成记忆摘要失败，AI 返回空。")
        log.info(f"用户 {user_id} 的总结流程完成。")

    async def get_memory_summary(self, user_id: int) -> str:
        """根据用户ID从 ParadeDB 获取其个人记忆摘要。"""
        async with AsyncSessionLocal() as session:
            stmt = select(CommunityMemberProfile.personal_summary).where(
                CommunityMemberProfile.discord_id == str(user_id)
            )
            result = await session.execute(stmt)
            summary = result.scalars().first()

            if summary:
                log.debug(f"从 ParadeDB 找到用户 {user_id} 的摘要。")
                return summary
            else:
                log.debug(f"在 ParadeDB 中未找到用户 {user_id} 的摘要。")
                return "该用户当前没有个人记忆摘要。"

    async def update_summary_manually(self, user_id: int, new_summary: str):
        """
        仅手动更新用户的个人记忆摘要，不影响计数或历史记录。
        主要用于管理员手动编辑。
        """
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self._update_summary(session, user_id, new_summary)
        log.info(f"为用户 {user_id} 手动更新了记忆摘要。")

    async def _update_summary(self, session, user_id: int, new_summary: Optional[str]):
        """私有方法：只更新摘要。"""
        stmt = (
            update(CommunityMemberProfile)
            .where(CommunityMemberProfile.discord_id == str(user_id))
            .values(personal_summary=new_summary)
        )
        await session.execute(stmt)

    async def _reset_history_and_count(self, session, user_id: int):
        """私有方法：只重置计数和历史。"""
        stmt = (
            update(CommunityMemberProfile)
            .where(CommunityMemberProfile.discord_id == str(user_id))
            .values(
                personal_message_count=0,
                history=[],
            )
        )
        await session.execute(stmt)

    async def update_summary_and_reset_history(
        self, user_id: int, new_summary: Optional[str]
    ):
        """
        在 ParadeDB 中更新摘要，同时重置个人消息计数和对话历史。
        (重构后，此函数调用两个独立的私有方法)
        """
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self._update_summary(session, user_id, new_summary)
                await self._reset_history_and_count(session, user_id)
        log.info(f"为用户 {user_id} 更新了记忆摘要，并重置了计数和历史。")

    async def clear_personal_memory(self, user_id: int):
        """
        清除指定用户的个人记忆摘要、对话历史和消息计数。
        """
        log.info(f"正在为用户 {user_id} 清除个人记忆...")
        await self.update_summary_and_reset_history(user_id, None)
        log.info(f"用户 {user_id} 的个人记忆已清除。")

    async def reset_memory_and_delete_history(self, user_id: int):
        """
        删除对话记录并重置记忆。
        这会清除用户的个人记忆摘要，并删除所有相关的对话历史记录。
        """
        log.info(f"正在为用户 {user_id} 重置记忆并删除对话历史...")
        await self.update_summary_and_reset_history(user_id, None)
        log.info(f"用户 {user_id} 的记忆和对话历史已清除。")

    async def delete_conversation_history(self, user_id: int):
        """
        单纯删除对话记录。
        这仅删除指定用户的对话历史记录和重置消息计数，不影响其个人记忆摘要。
        """
        log.info(f"正在为用户 {user_id} 删除对话历史...")
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await self._reset_history_and_count(session, user_id)
        log.info(f"用户 {user_id} 的对话历史已删除。")


# 单例实例
personal_memory_service = PersonalMemoryService()
