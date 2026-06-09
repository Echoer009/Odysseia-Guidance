# -*- coding: utf-8 -*-
import logging
import re
from typing import Optional, List, Dict, Tuple

from sqlalchemy.future import select
from sqlalchemy import delete, update, func

from src.database.database import AsyncSessionLocal
from src.database.models import UserMemoryNote
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.config import BOT_NAME

log = logging.getLogger(__name__)

VALID_CATEGORIES = ("emotion", "status", "preference", "positive_event")

CATEGORY_LABELS = {
    "emotion": "情感",
    "status": "状态",
    "preference": "偏好",
    "positive_event": "正面事件",
}

CATEGORY_LIMITS = {
    "emotion": 3,
    "status": 3,
    "preference": 5,
    "positive_event": 5,
}

MAX_CONTENT_LENGTH = 150

_BLOCKED_PATTERNS_GENERAL = [
    re.compile(r"文爱", re.IGNORECASE),
    re.compile(r"角色扮演.*(色|涩|黄|h)", re.IGNORECASE),
    re.compile(r"色情|涩情|搞黄|ghs", re.IGNORECASE),
]

_BLOCKED_PATTERNS_PREFERENCE = [
    re.compile(r"(主人|爸爸|老公|妈妈|老婆|daddy|master|husband|wife|主人)", re.IGNORECASE),
    re.compile(r"(主人|爹地|妈咪|相公|娘子|娘子|大爷|奴)", re.IGNORECASE),
]


def validate_memory_content(category: str, content: str) -> Tuple[bool, str]:
    if not content or not content.strip():
        return False, "内容不能为空"
    if len(content) > MAX_CONTENT_LENGTH:
        return False, f"内容过长（{len(content)}/{MAX_CONTENT_LENGTH}字），请精简"
    if category and category not in VALID_CATEGORIES:
        return False, f"无效的类别：{category}，可选：{', '.join(VALID_CATEGORIES)}"

    for pattern in _BLOCKED_PATTERNS_GENERAL:
        if pattern.search(content):
            return False, "该内容包含不适当的内容，不予记录"

    if category == "preference":
        for pattern in _BLOCKED_PATTERNS_PREFERENCE:
            if pattern.search(content):
                return False, f"{BOT_NAME}和用户是平等的好朋友关系，不支持上位/从属/亲密关系的称呼或偏好"

    return True, ""


class UserMemoryNoteService:
    async def has_profile(self, user_id: str) -> bool:
        profile = await world_book_service.get_profile_by_discord_id(int(user_id))
        return profile is not None

    async def get_notes_for_user(self, user_id: str) -> List[UserMemoryNote]:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(UserMemoryNote)
                .where(UserMemoryNote.user_id == user_id)
                .order_by(UserMemoryNote.category, UserMemoryNote.created_at)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_notes_for_context(self, user_id: str) -> Optional[str]:
        notes = await self.get_notes_for_user(user_id)
        if not notes:
            return None

        grouped: Dict[str, List[str]] = {}
        for note in notes:
            label = CATEGORY_LABELS.get(note.category, note.category)
            grouped.setdefault(label, []).append(f"(ID:{note.id}) {note.content}")

        lines = []
        for label, entries in grouped.items():
            for entry in entries:
                lines.append(f"[{label}] {entry}")

        return "\n".join(lines)

    async def count_notes_by_category(self, user_id: str, category: str) -> int:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(func.count())
                .select_from(UserMemoryNote)
                .where(UserMemoryNote.user_id == user_id, UserMemoryNote.category == category)
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def add_note(
        self, user_id: str, category: str, content: str
    ) -> Tuple[bool, str, Optional[int]]:
        valid, err = validate_memory_content(category, content)
        if not valid:
            return False, err, None

        if not await self.has_profile(user_id):
            return False, "该用户没有名片，无法记录记忆", None

        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(UserMemoryNote).where(
                    UserMemoryNote.user_id == user_id,
                    UserMemoryNote.category == category,
                    UserMemoryNote.content == content.strip(),
                )
            )
            if existing.scalars().first():
                log.info(f"[MemoryNote] 用户 {user_id} 跳过重复记忆: [{category}] {content.strip()}")
                return True, "已存在相同记录", None

        limit = CATEGORY_LIMITS.get(category, 5)
        async with AsyncSessionLocal() as session:
            async with session.begin():
                count_result = await session.execute(
                    select(func.count()).select_from(UserMemoryNote).where(
                        UserMemoryNote.user_id == user_id,
                        UserMemoryNote.category == category,
                    )
                )
                count = count_result.scalar() or 0

                if count >= limit:
                    oldest = await session.execute(
                        select(UserMemoryNote)
                        .where(
                            UserMemoryNote.user_id == user_id,
                            UserMemoryNote.category == category,
                        )
                        .order_by(UserMemoryNote.created_at.asc())
                        .limit(1)
                    )
                    oldest_note = oldest.scalars().first()
                    if oldest_note:
                        await session.delete(oldest_note)
                        log.info(f"[MemoryNote] 用户 {user_id} 类别 [{category}] 已满，自动替换最旧记录 ID:{oldest_note.id}")

                note = UserMemoryNote(
                    user_id=user_id,
                    category=category,
                    content=content.strip(),
                )
                session.add(note)
                await session.flush()
                note_id = note.id
            log.info(f"[MemoryNote] 用户 {user_id} 新增记忆: [{category}] {content.strip()}")
            return True, "已记录", note_id

    async def update_note(
        self, user_id: str, note_id: int, content: str
    ) -> Tuple[bool, str]:
        valid, err = validate_memory_content("", content)
        if not valid:
            return False, err

        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = select(UserMemoryNote).where(
                    UserMemoryNote.id == note_id,
                    UserMemoryNote.user_id == user_id,
                )
                result = await session.execute(stmt)
                note = result.scalars().first()
                if not note:
                    return False, f"未找到ID为 {note_id} 的记忆条目"

                valid, err = validate_memory_content(note.category, content)
                if not valid:
                    return False, err

                note.content = content.strip()
                log.info(f"[MemoryNote] 用户 {user_id} 更新记忆 {note_id}: {content.strip()}")
            return True, "已更新"

    async def delete_note(self, user_id: str, note_id: int) -> Tuple[bool, str]:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = select(UserMemoryNote).where(
                    UserMemoryNote.id == note_id,
                    UserMemoryNote.user_id == user_id,
                )
                result = await session.execute(stmt)
                note = result.scalars().first()
                if not note:
                    return False, f"未找到ID为 {note_id} 的记忆条目"
                await session.delete(note)
                log.info(f"[MemoryNote] 用户 {user_id} 删除记忆 {note_id}")
            return True, "已删除"

    async def delete_all_notes_for_user(self, user_id: str) -> int:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = delete(UserMemoryNote).where(UserMemoryNote.user_id == user_id)
                result = await session.execute(stmt)
                count = getattr(result, "rowcount", 0) or 0
                log.info(f"[MemoryNote] 用户 {user_id} 删除全部 {count} 条记忆")
            return count


user_memory_note_service = UserMemoryNoteService()
