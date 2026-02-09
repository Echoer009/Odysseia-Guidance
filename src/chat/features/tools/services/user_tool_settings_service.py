"""
用户工具设置服务

负责管理用户在帖子里类脑娘可以使用的工具设置。
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.database import AsyncSessionLocal
from src.database.models import UserToolSettings

log = logging.getLogger(__name__)


class UserToolSettingsService:
    """用户工具设置服务"""

    async def get_user_tool_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户的工具设置

        Args:
            user_id: 用户的 Discord ID

        Returns:
            如果用户有设置记录，返回 enabled_tools 字典；否则返回 None
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserToolSettings).where(UserToolSettings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            if settings:
                return settings.enabled_tools
            return None

    async def save_user_tool_settings(
        self, user_id: str, enabled_tools: Dict[str, Any]
    ) -> bool:
        """
        保存用户的工具设置

        Args:
            user_id: 用户的 Discord ID
            enabled_tools: 启用的工具列表（字典格式）

        Returns:
            保存是否成功
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(UserToolSettings).where(UserToolSettings.user_id == user_id)
                )
                settings = result.scalar_one_or_none()

                if settings:
                    # 更新现有记录
                    settings.enabled_tools = enabled_tools
                else:
                    # 创建新记录
                    settings = UserToolSettings(
                        user_id=user_id, enabled_tools=enabled_tools
                    )
                    session.add(settings)

                await session.commit()
                log.info(f"成功保存用户 {user_id} 的工具设置: {enabled_tools}")
                return True
        except Exception as e:
            log.error(f"保存用户 {user_id} 的工具设置时出错: {e}", exc_info=True)
            return False

    async def delete_user_tool_settings(self, user_id: str) -> bool:
        """
        删除用户的工具设置（恢复默认：启用所有工具）

        Args:
            user_id: 用户的 Discord ID

        Returns:
            删除是否成功
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(UserToolSettings).where(UserToolSettings.user_id == user_id)
                )
                settings = result.scalar_one_or_none()

                if settings:
                    await session.delete(settings)
                    await session.commit()
                    log.info(f"成功删除用户 {user_id} 的工具设置，恢复默认")
                return True
        except Exception as e:
            log.error(f"删除用户 {user_id} 的工具设置时出错: {e}", exc_info=True)
            return False


# 全局服务实例
user_tool_settings_service = UserToolSettingsService()
