import logging
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.future import select
from sqlalchemy import update
from src.database.database import AsyncSessionLocal
from src.database.models import CommunityMemberProfile, ConversationBlock
from src.chat.config.chat_config import (
    PROMPT_CONFIG,
    CONVERSATION_MEMORY_CONFIG,
)
from src.chat.features.personal_memory.services.conversation_block_service import (
    conversation_block_service,
)
# --- [DISABLED] 印象总结功能（flash模型）相关的导入 ---
# from src.chat.config.chat_config import SUMMARY_MODEL, GEMINI_SUMMARY_GEN_CONFIG
# from src.chat.services.ai.service import ai_service
# from src.chat.services.ai.providers.base import GenerationConfig, ModelNotSupportedError
# from src.chat.features.chat_settings.services.chat_settings_service import chat_settings_service

log = logging.getLogger(__name__)


class PersonalMemoryService:
    async def check_and_create_block_before_reply(self, user_id: int) -> bool:
        """
        在AI回复前检查是否需要创建对话块。

        如果用户的对话历史已达到 block_size 阈值，先创建对话块，
        这样RAG检索就能包含这些历史对话。

        Args:
            user_id: 用户 Discord ID

        Returns:
            bool: 是否创建了新的对话块
        """
        if not CONVERSATION_MEMORY_CONFIG.get("enabled", True):
            return False

        block_size = CONVERSATION_MEMORY_CONFIG.get("block_size", 10)

        try:
            async with AsyncSessionLocal() as session:
                stmt = select(CommunityMemberProfile).where(
                    CommunityMemberProfile.discord_id == str(user_id)
                )
                result = await session.execute(stmt)
                profile = result.scalars().first()

                if not profile:
                    log.debug(f"用户 {user_id} 没有个人档案，跳过对话块检查。")
                    return False

                current_history = getattr(profile, "history", []) or []

                # 只有当历史达到阈值时才创建块
                if len(current_history) >= block_size:
                    log.info(
                        f"用户 {user_id} 的对话历史达到 {len(current_history)} 条，"
                        f"（阈值 {block_size}）在AI回复前创建对话块。"
                    )
                    # 使用独立事务创建对话块并清理历史
                    try:
                        async with AsyncSessionLocal() as block_session:
                            # 创建对话块（只保存最近的 block_size 条）
                            await conversation_block_service.create_block_from_history(
                                discord_id=str(user_id),
                                history=list(current_history),
                                session=block_session,
                            )
                            # 清理旧的对话块
                            await conversation_block_service.cleanup_old_blocks(
                                discord_id=str(user_id),
                                session=block_session,
                            )

                            # 清理已保存的历史，只保留最近的 block_size 条之后的新消息
                            # 这样可以避免下次创建时重复保存相同的消息
                            remaining_history = current_history[block_size:]

                            # 更新 profile.history（需要在同一个事务中）
                            stmt_update = (
                                update(CommunityMemberProfile)
                                .where(
                                    CommunityMemberProfile.discord_id == str(user_id)
                                )
                                .values(history=remaining_history)
                            )
                            await block_session.execute(stmt_update)

                            await block_session.commit()
                            log.info(
                                f"用户 {user_id} 对话块创建成功，"
                                f"清理了 {block_size} 条已保存的历史，"
                                f"剩余 {len(remaining_history)} 条。"
                            )
                            return True
                    except Exception as e:
                        log.error(f"用户 {user_id} 创建对话块失败: {e}", exc_info=True)
                        return False
                else:
                    log.debug(
                        f"用户 {user_id} 对话历史 {len(current_history)}/{block_size}，"
                        f"暂不需要创建对话块。"
                    )
                    return False

        except Exception as e:
            log.error(f"检查用户 {user_id} 对话块时出错: {e}", exc_info=True)
            return False

    async def update_and_conditionally_summarize_memory(
        self,
        user_id: int,
        user_name: str,
        user_content: str,
        ai_response: str,
        current_model: str | None = None,
    ):
        """
        核心入口：更新对话历史和计数，并在达到阈值时触发总结。
        所有数据库操作都在ParadeDB中完成。

        新增功能：
        - 记录对话时添加时间戳
        - 在达到 block_size 阈值时创建对话块（永久记忆）
        - 方案E：每2个新对话块触发一次印象总结

        Args:
            user_id: 用户ID
            user_name: 用户名
            user_content: 用户消息内容
            ai_response: AI回复内容
            current_model: 当前使用的模型名称（用于总结时跟随主模型）
        """
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = (
                    select(CommunityMemberProfile)
                    .where(CommunityMemberProfile.discord_id == str(user_id))
                    .with_for_update()
                )
                result = await session.execute(stmt)
                profile = result.scalars().first()

                if not profile:
                    log.warning(f"用户 {user_id} 没有个人档案，无法记录记忆。")
                    return

                # 添加带时间戳的对话记录
                now = datetime.now().isoformat()
                new_turn = {"role": "user", "parts": [user_content], "timestamp": now}
                new_model_turn = {
                    "role": "model",
                    "parts": [ai_response],
                    "timestamp": now,
                }

                current_history = getattr(profile, "history", [])
                new_history = list(current_history or [])
                new_history.extend([new_turn, new_model_turn])
                setattr(profile, "history", new_history)

                log.debug(f"用户 {user_id} 的对话历史更新为: {len(new_history)} 条")

        # 注意：对话块的创建已移至 check_and_create_block_before_reply 方法，
        # 在AI回复前执行，确保最新对话可被RAG检索

        # --- [DISABLED] 印象总结功能（flash模型）已禁用 ---
        # await self._check_and_summarize_blocks(user_id, current_model)

    # --- [DISABLED] 印象总结功能（flash模型）已禁用 - 以下两个方法不再使用 ---
    # async def _check_and_summarize_blocks(
    #     self, user_id: int, current_model: str | None = None
    # ):
    #     """方案E：检查是否有足够的未总结对话块，如果有2个则触发印象总结。"""
    #     (
    #         blocks_to_summarize,
    #         should_summarize,
    #     ) = await conversation_block_service.get_blocks_for_summary(str(user_id))
    #     if not should_summarize or not blocks_to_summarize:
    #         return
    #     log.info(
    #         f"用户 {user_id} 有 {len(blocks_to_summarize)} 个未总结的对话块，"
    #         f"开始生成印象总结。"
    #     )
    #     await self._summarize_blocks(user_id, blocks_to_summarize, current_model)

    # async def _summarize_blocks(
    #     self,
    #     user_id: int,
    #     blocks: List[ConversationBlock],
    #     current_model: str | None = None,
    # ):
    #     """方案E：从对话块生成印象总结。"""
    #     log.info(f"开始为用户 {user_id} 从 {len(blocks)} 个对话块生成印象总结。")
    #     async with AsyncSessionLocal() as session:
    #         stmt = select(CommunityMemberProfile.personal_summary).where(
    #             CommunityMemberProfile.discord_id == str(user_id)
    #         )
    #         result = await session.execute(stmt)
    #         old_summary = result.scalars().first() or "无"
    #     dialogue_text = "\n\n".join(
    #         f"[对话块 {i + 1}]\n{block.conversation_text}"
    #         for i, block in enumerate(blocks)
    #     ).strip()
    #     if not dialogue_text:
    #         log.warning(f"用户 {user_id} 的对话块文本为空。")
    #         return
    #     prompt_template = PROMPT_CONFIG.get("personal_memory_summary")
    #     if not prompt_template:
    #         log.error("未找到 'personal_memory_summary' 的 prompt 模板。")
    #         return
    #     final_prompt = prompt_template.format(
    #         old_summary=old_summary, dialogue_history=dialogue_text
    #     )
    #     def count_summary_lines(summary: str) -> int:
    #         return len([line for line in summary.split("\n") if line.strip().startswith("-")])
    #     old_summary_lines = count_summary_lines(old_summary)
    #     log.info(f"---[MEMORY DEBUGGER - 方案E]--- 用户 {user_id} 开始总结 ---")
    #     log.info(f"旧摘要行数: {old_summary_lines}")
    #     log.info(f"完整的旧摘要:\n{old_summary}")
    #     log.info(f"用于总结的对话块数量: {len(blocks)}")
    #     log.info(f"对话块 ID: {[b.id for b in blocks]}")
    #     configured_summary_model = await chat_settings_service.get_summary_model()
    #     model_to_use = configured_summary_model or SUMMARY_MODEL
    #     log.info(f"使用模型 {model_to_use} 进行印象总结")
    #     messages = [{"role": "user", "content": final_prompt}]
    #     config = GenerationConfig(
    #         temperature=GEMINI_SUMMARY_GEN_CONFIG.get("temperature", 0.7),
    #         max_output_tokens=GEMINI_SUMMARY_GEN_CONFIG.get("max_output_tokens", 2048),
    #     )
    #     try:
    #         result = await ai_service.generate(
    #             messages=messages, config=config, model=model_to_use
    #         )
    #     except ModelNotSupportedError:
    #         fallback = current_model or ai_service._get_default_model()
    #         log.warning(f"总结模型 {model_to_use} 不可用，回退到 {fallback}")
    #         result = await ai_service.generate(
    #             messages=messages, config=config, model=fallback
    #         )
    #     new_summary = result.content
    #     if new_summary:
    #         new_summary_lines = count_summary_lines(new_summary)
    #         log.info(f"---[MEMORY DEBUGGER - 方案E]--- 用户 {user_id} 总结完毕 ---")
    #         log.info(f"新摘要行数: {new_summary_lines} (Prompt要求 <= 30)")
    #         if new_summary_lines > 30:
    #             log.error("!!!!!!!! MEMORY EXPLOSION DETECTED !!!!!!!!")
    #             log.error(f"用户 {user_id} 的新摘要行数 ({new_summary_lines}) 超过了30条的硬性限制！")
    #             log.error(f"完整的失控摘要:\n{new_summary}")
    #         else:
    #             log.debug(f"完整的新摘要:\n{new_summary}")
    #         await self.update_summary_manually(user_id, new_summary)
    #         block_ids = [b.id for b in blocks]
    #         await conversation_block_service.mark_blocks_as_summarized(block_ids)
    #         log.info(f"用户 {user_id} 印象总结完成，已标记 {len(block_ids)} 个对话块为已总结。")
    #     else:
    #         log.error(f"为用户 {user_id} 生成记忆摘要失败，AI 返回空。")
    # --- [DISABLED END] ---

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

    async def get_recent_chat_history(
        self, user_id: int, limit: int = 10
    ) -> List[Dict]:
        """
        获取用户最近的聊天历史（尚未打包成对话块的消息）。

        这些消息从 profile.history 中读取，最多返回 limit 条。
        返回的消息按时间顺序排列（从旧到新）。

        Args:
            user_id: 用户 Discord ID
            limit: 最多返回的消息条数

        Returns:
            消息列表，每条包含 role, parts, timestamp
        """
        async with AsyncSessionLocal() as session:
            stmt = select(CommunityMemberProfile.history).where(
                CommunityMemberProfile.discord_id == str(user_id)
            )
            result = await session.execute(stmt)
            history = result.scalars().first()

            if not history:
                return []

            history_list = list(history)
            return history_list[-limit:] if len(history_list) > limit else history_list

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
