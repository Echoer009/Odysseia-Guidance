# -*- coding: utf-8 -*-
"""
对话块服务 - 管理对话块的存储、更新和生命周期

核心功能：
- 从对话历史创建对话块
- 生成对话块的向量嵌入
- 管理对话块的生命周期（清理旧块）
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.database import AsyncSessionLocal
from src.database.models import ConversationBlock
from src.chat.services.embedding_factory import (
    get_embedding_service,
    is_vector_enabled,
)
from src.chat.config import chat_config

log = logging.getLogger(__name__)


def format_time_description(start_time: datetime, end_time: datetime) -> str:
    """
    根据对话块的时间生成人类可读的时间描述。

    规则：
    - 1分钟内：刚刚
    - 1小时内：X分钟前
    - 同一天：X小时前
    - 昨天：昨天
    - 前天：前天
    - 7天内：X天前
    - 30天内：上周 / X周前
    - 90天内：上个月
    - 一年内：X个月前
    - 超过一年：X年前
    """
    now = datetime.now()
    delta = now - start_time

    # 计算今天开始的时间
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    days_diff = (
        today_start - start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    ).days

    if delta.total_seconds() < 60:
        return "刚刚"
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes}分钟前"
    elif days_diff == 0:
        hours = int(delta.total_seconds() / 3600)
        return f"{hours}小时前"
    elif days_diff == 1:
        return "昨天"
    elif days_diff == 2:
        return "前天"
    elif days_diff < 7:
        return f"{days_diff}天前"
    elif days_diff < 14:
        return "上周"
    elif days_diff < 30:
        weeks = days_diff // 7
        return f"{weeks}周前"
    elif days_diff < 60:
        return "上个月"
    elif days_diff < 90:
        return "2个月前"
    elif days_diff < 365:
        months = days_diff // 30
        return f"{months}个月前"
    else:
        years = days_diff // 365
        return f"{years}年前"


class ConversationBlockService:
    """
    对话块管理服务

    负责：
    - 从对话历史创建对话块
    - 生成向量嵌入
    - 管理对话块生命周期
    """

    def __init__(self):
        self.config = chat_config.CONVERSATION_MEMORY_CONFIG
        log.info(f"ConversationBlockService 已初始化，配置: {self.config}")

    def _clean_discord_emojis(self, text: str) -> str:
        """
        清理 Discord 自定义表情格式 <:name:id> 和 <a:name:id>。
        这些表情占用 token 但对语义理解没有帮助。

        Args:
            text: 原始文本

        Returns:
            清理后的文本
        """
        # 匹配 <:name:id> 和 <a:name:id> 格式的 Discord 表情
        # 静态表情: <:emoji_name:123456789>
        # 动态表情: <a:emoji_name:123456789>
        import re

        cleaned = re.sub(r"<a?:[^:]+:\d+>", "", text)
        # 清理多余的空格
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _format_conversation_text(self, history: List[Dict]) -> str:
        """
        将对话历史格式化为存储文本。

        Args:
            history: 对话历史列表，每个元素包含 role 和 parts

        Returns:
            格式化后的对话文本
        """
        lines = []
        for msg in history:
            role = msg.get("role", "unknown")
            parts = msg.get("parts", [])
            text = " ".join(parts) if isinstance(parts, list) else str(parts)

            # 清理 Discord 表情
            text = self._clean_discord_emojis(text)

            if role == "user":
                lines.append(f"用户: {text}")
            else:
                lines.append(f"类脑娘: {text}")

        return "\n".join(lines)

    def _extract_time_range(self, history: List[Dict]) -> tuple[datetime, datetime]:
        """
        从对话历史中提取时间范围。

        Args:
            history: 对话历史列表

        Returns:
            (start_time, end_time) 元组
        """
        timestamps = []
        for msg in history:
            ts = msg.get("timestamp")
            if ts:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                timestamps.append(ts)

        if timestamps:
            return min(timestamps), max(timestamps)
        else:
            # 如果没有时间戳，使用当前时间
            now = datetime.now()
            return now, now

    async def create_block_from_history(
        self,
        discord_id: str,
        history: List[Dict],
        session: Optional[AsyncSession] = None,
    ) -> Optional[int]:
        """
        从对话历史创建对话块。

        Args:
            discord_id: 用户 Discord ID
            history: 对话历史列表
            session: 可选的数据库会话

        Returns:
            创建的对话块 ID，失败返回 None
        """
        if not history:
            log.warning(f"用户 {discord_id} 的对话历史为空，跳过创建对话块")
            return None

        block_size = self.config.get("block_size", 10)

        # 检查历史长度是否达到阈值
        if len(history) < block_size:
            log.debug(
                f"用户 {discord_id} 的对话历史长度 {len(history)} < {block_size}，跳过创建"
            )
            return None

        # 取最近的 block_size 条消息
        history_to_store = history[-block_size:]

        # 格式化对话文本
        conversation_text = self._format_conversation_text(history_to_store)

        # 提取时间范围
        start_time, end_time = self._extract_time_range(history_to_store)

        # 生成向量嵌入
        try:
            embedding_service = await get_embedding_service()
            embedding = await embedding_service.generate_embedding(
                text=conversation_text, task_type="retrieval_document"
            )
            if not embedding:
                log.error(f"用户 {discord_id} 的对话块嵌入生成失败")
                return None
        except Exception as e:
            log.error(f"生成对话块嵌入时出错: {e}", exc_info=True)
            return None

        # 创建数据库记录
        async def _create_block(sess: AsyncSession) -> Optional[int]:
            # 确定使用哪个嵌入列
            from src.chat.services.embedding_factory import get_embedding_column

            embedding_col = await get_embedding_column()

            block = ConversationBlock(
                discord_id=discord_id,
                conversation_text=conversation_text,
                start_time=start_time,
                end_time=end_time,
                message_count=len(history_to_store),
            )

            # 设置对应的嵌入向量
            if embedding_col == "qwen_embedding":
                block.qwen_embedding = embedding
            else:
                block.bge_embedding = embedding

            sess.add(block)
            await sess.flush()
            await sess.refresh(block)

            log.info(
                f"用户 {discord_id} 创建对话块成功: id={block.id}, "
                f"messages={len(history_to_store)}, time_range={start_time} ~ {end_time}"
            )
            return block.id

        if session:
            return await _create_block(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _create_block(sess)

    async def get_user_block_count(self, discord_id: str) -> int:
        """
        获取用户的对话块数量。

        Args:
            discord_id: 用户 Discord ID

        Returns:
            对话块数量
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(ConversationBlock.id)).where(
                    ConversationBlock.discord_id == discord_id
                )
            )
            return result.scalar() or 0

    async def cleanup_old_blocks(
        self, discord_id: str, session: Optional[AsyncSession] = None
    ) -> int:
        """
        清理用户的旧对话块，保留最新的 max_blocks_per_user 个。

        Args:
            discord_id: 用户 Discord ID
            session: 可选的数据库会话

        Returns:
            删除的对话块数量
        """
        max_blocks = self.config.get("max_blocks_per_user", 100)

        async def _cleanup(sess: AsyncSession) -> int:
            # 获取用户的所有对话块 ID，按开始时间降序
            result = await sess.execute(
                select(ConversationBlock.id)
                .where(ConversationBlock.discord_id == discord_id)
                .order_by(ConversationBlock.start_time.desc())
            )
            all_ids = [row[0] for row in result.fetchall()]

            if len(all_ids) <= max_blocks:
                return 0

            # 删除超出限制的旧块
            ids_to_delete = all_ids[max_blocks:]
            await sess.execute(
                delete(ConversationBlock).where(ConversationBlock.id.in_(ids_to_delete))
            )

            log.info(
                f"用户 {discord_id} 清理了 {len(ids_to_delete)} 个旧对话块，"
                f"保留 {max_blocks} 个"
            )
            return len(ids_to_delete)

        if session:
            return await _cleanup(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _cleanup(sess)

    async def delete_all_user_blocks(
        self, discord_id: str, session: Optional[AsyncSession] = None
    ) -> int:
        """
        删除用户的所有对话块（用于用户注销等场景）。

        Args:
            discord_id: 用户 Discord ID
            session: 可选的数据库会话

        Returns:
            删除的对话块数量
        """

        async def _delete_all(sess: AsyncSession) -> int:
            result = await sess.execute(
                delete(ConversationBlock)
                .where(ConversationBlock.discord_id == discord_id)
                .returning(ConversationBlock.id)
            )
            deleted_rows = result.fetchall()
            deleted_count = len(deleted_rows)
            log.info(f"用户 {discord_id} 删除了所有 {deleted_count} 个对话块")
            return deleted_count

        if session:
            return await _delete_all(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _delete_all(sess)

    async def get_latest_block_id(self, discord_id: str) -> Optional[int]:
        """
        获取用户最新的对话块 ID。

        用于在 RAG 检索时排除最新的对话块，避免与当前对话历史重复。

        Args:
            discord_id: 用户 Discord ID

        Returns:
            最新对话块的 ID，如果没有对话块则返回 None
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConversationBlock.id)
                .where(ConversationBlock.discord_id == discord_id)
                .order_by(ConversationBlock.start_time.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row:
                log.debug(f"用户 {discord_id} 最新的对话块 ID: {row}")
            return row

    async def get_latest_block_content(self, discord_id: str) -> Optional[Dict]:
        """
        获取用户最新对话块的完整内容。

        用于作为三层记忆的第三层（最新对话），注入到 prompt 中。

        Args:
            discord_id: 用户 Discord ID

        Returns:
            包含对话块信息的字典，包括：
            - id: 对话块 ID
            - conversation_text: 对话文本
            - start_time: 开始时间
            - end_time: 结束时间
            - message_count: 消息数量
            - time_description: 人类可读的时间描述
            如果没有对话块则返回 None
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConversationBlock)
                .where(ConversationBlock.discord_id == discord_id)
                .order_by(ConversationBlock.start_time.desc())
                .limit(1)
            )
            block = result.scalar_one_or_none()

            if not block:
                log.debug(f"用户 {discord_id} 没有对话块")
                return None

            time_desc = format_time_description(block.start_time, block.end_time)

            log.debug(
                f"用户 {discord_id} 获取最新对话块: id={block.id}, "
                f"messages={block.message_count}, time={time_desc}"
            )

            return {
                "id": block.id,
                "conversation_text": block.conversation_text,
                "start_time": block.start_time,
                "end_time": block.end_time,
                "message_count": block.message_count,
                "time_description": time_desc,
            }

    async def get_unsummarized_blocks(
        self, discord_id: str, session: Optional[AsyncSession] = None
    ) -> List[ConversationBlock]:
        """
        获取用户未被总结的对话块。

        用于方案E：每2个新块触发一次印象总结。

        Args:
            discord_id: 用户 Discord ID
            session: 可选的数据库会话

        Returns:
            未被总结的对话块列表，按时间升序排列（最早的在前）
        """

        async def _get_blocks(sess: AsyncSession) -> List[ConversationBlock]:
            result = await sess.execute(
                select(ConversationBlock)
                .where(
                    ConversationBlock.discord_id == discord_id,
                    ConversationBlock.summarized == 0,
                )
                .order_by(ConversationBlock.start_time.asc())
            )
            return list(result.scalars().all())

        if session:
            return await _get_blocks(session)
        else:
            async with AsyncSessionLocal() as sess:
                return await _get_blocks(sess)

    async def mark_blocks_as_summarized(
        self,
        block_ids: List[int],
        session: Optional[AsyncSession] = None,
    ) -> int:
        """
        将指定的对话块标记为已总结。

        Args:
            block_ids: 要标记的对话块 ID 列表
            session: 可选的数据库会话

        Returns:
            更新的记录数量
        """
        if not block_ids:
            return 0

        from sqlalchemy import update

        async def _mark(sess: AsyncSession) -> int:
            stmt = (
                update(ConversationBlock)
                .where(ConversationBlock.id.in_(block_ids))
                .values(summarized=1)
            )
            await sess.execute(stmt)
            log.info(f"已将 {len(block_ids)} 个对话块标记为已总结: {block_ids}")
            return len(block_ids)

        if session:
            return await _mark(session)
        else:
            async with AsyncSessionLocal() as sess:
                async with sess.begin():
                    return await _mark(sess)

    async def get_blocks_for_summary(
        self,
        discord_id: str,
        session: Optional[AsyncSession] = None,
    ) -> tuple[List[ConversationBlock], bool]:
        """
        检查是否有足够的未总结对话块，如果有2个或更多则返回最早的2个。

        用于方案E：每2个新块触发一次印象总结。

        Args:
            discord_id: 用户 Discord ID
            session: 可选的数据库会话

        Returns:
            (blocks_to_summarize, should_summarize)
            - blocks_to_summarize: 需要总结的对话块列表（最多2个）
            - should_summarize: 是否应该触发总结
        """
        unsummarized = await self.get_unsummarized_blocks(discord_id, session)

        if len(unsummarized) >= 2:
            # 返回最早的2个未总结块
            blocks_to_summarize = unsummarized[:2]
            log.info(
                f"用户 {discord_id} 有 {len(unsummarized)} 个未总结的对话块，"
                f"将总结最早的2个: {[b.id for b in blocks_to_summarize]}"
            )
            return blocks_to_summarize, True
        else:
            log.debug(
                f"用户 {discord_id} 有 {len(unsummarized)} 个未总结的对话块，"
                f"暂不触发总结（需要至少2个）"
            )
            return [], False

    async def get_user_blocks(self, discord_id: str) -> List[Dict]:
        """
        获取用户的所有对话块（用于用户视图）。

        Args:
            discord_id: 用户 Discord ID

        Returns:
            对话块字典列表，按开始时间降序排列
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConversationBlock)
                .where(ConversationBlock.discord_id == discord_id)
                .order_by(ConversationBlock.start_time.desc())
            )
            blocks = result.scalars().all()

            return [
                {
                    "id": block.id,
                    "discord_id": block.discord_id,
                    "conversation_text": block.conversation_text,
                    "message_count": block.message_count,
                    "start_time": block.start_time,
                    "end_time": block.end_time,
                    "bge_embedding": block.bge_embedding is not None,
                    "qwen_embedding": block.qwen_embedding is not None,
                }
                for block in blocks
            ]

    async def delete_block_by_id(self, block_id: int) -> bool:
        """
        删除指定 ID 的对话块。

        Args:
            block_id: 对话块 ID

        Returns:
            是否成功删除
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                delete(ConversationBlock)
                .where(ConversationBlock.id == block_id)
                .returning(ConversationBlock.id)
            )
            deleted = result.scalar_one_or_none()
            await session.commit()

            if deleted:
                log.info(f"已删除对话块 {block_id}")
                return True
            return False


# 创建单例
conversation_block_service = ConversationBlockService()
