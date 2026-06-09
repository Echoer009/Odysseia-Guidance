# -*- coding: utf-8 -*-
"""
用户人设偏好服务

负责管理用户对Bot人设风格的选择（默认 / 温柔）。
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.database import AsyncSessionLocal
from src.database.models import UserPersonaPreference

log = logging.getLogger(__name__)

VALID_STYLES = {"default", "gentle", "frank"}


class PersonaPreferenceService:
    """用户人设偏好服务"""

    async def get_persona_style(self, user_id: str) -> str:
        """
        获取用户的人设风格偏好。

        Args:
            user_id: 用户的 Discord ID

        Returns:
            "default" 或 "gentle"，无记录时返回 "default"
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserPersonaPreference).where(
                    UserPersonaPreference.user_id == user_id
                )
            )
            pref = result.scalar_one_or_none()
            if pref:
                return pref.persona_style
            return "default"

    async def set_persona_style(self, user_id: str, style: str) -> bool:
        """
        设置用户的人设风格偏好。

        Args:
            user_id: 用户的 Discord ID
            style: "default" 或 "gentle"

        Returns:
            保存是否成功
        """
        if style not in VALID_STYLES:
            log.warning(f"无效的人设风格 '{style}'，用户: {user_id}")
            return False

        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(UserPersonaPreference).where(
                        UserPersonaPreference.user_id == user_id
                    )
                )
                pref = result.scalar_one_or_none()

                if pref:
                    pref.persona_style = style
                else:
                    pref = UserPersonaPreference(
                        user_id=user_id, persona_style=style
                    )
                    session.add(pref)

                await session.commit()
                log.info(f"用户 {user_id} 的人设风格已设置为: {style}")
                return True
        except Exception as e:
            log.error(f"设置用户 {user_id} 的人设风格时出错: {e}", exc_info=True)
            return False


persona_preference_service = PersonaPreferenceService()
