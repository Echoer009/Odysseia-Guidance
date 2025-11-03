# -*- coding: utf-8 -*-
from typing import Optional

from src.guidance.utils.database import GuidanceDatabaseManager
from src.guidance.models.user_progress import UserProgress


class UserProgressRepository:
    """
    封装所有与 UserProgress 相关的数据库操作。
    这是业务逻辑与底层数据库交互的唯一接口。
    """

    def __init__(self, db_manager: GuidanceDatabaseManager):
        self.db = db_manager

    async def get(self, user_id: int, guild_id: int) -> Optional[UserProgress]:
        """通过用户和服务器ID获取用户进度。"""
        row = await self.db.get_user_progress(user_id, guild_id)
        return UserProgress.from_row(row)

    async def create_or_reset(
        self,
        user_id: int,
        guild_id: int,
        status: str,
        guidance_stage: Optional[str] = None,
    ) -> UserProgress:
        """创建或重置用户进度记录。"""
        row = await self.db.create_or_reset_user_progress(
            user_id, guild_id, status, guidance_stage
        )
        # create_or_reset_user_progress 保证会返回一个 row
        return UserProgress.from_row(row)

    async def update(self, progress: UserProgress) -> Optional[UserProgress]:
        """使用 UserProgress 对象的内容更新数据库记录。"""
        if not progress:
            return None

        # to_db_dict 已经处理了 json.dumps
        updates = progress.to_db_dict()

        # 移除 to_db_dict 中不应该通过 **kwargs 传递的键（如果存在）
        # 在这个实现中，to_db_dict 返回的键都是 user_progress 表的列，所以是安全的

        updated_row = await self.db.update_user_progress(
            progress.user_id, progress.guild_id, **updates
        )
        return UserProgress.from_row(updated_row)
