# -*- coding: utf-8 -*-
"""
用户命令设置服务

负责管理用户在帖子里可以使用的命令设置。
用户可以控制在自己的帖子里哪些命令（如/投喂、/忏悔等）可以使用。
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.database import AsyncSessionLocal
from src.database.models import UserCommandSettings
from src.config import BOT_NAME

log = logging.getLogger(__name__)

# 可配置的命令列表（命令名: 显示名称和描述）
CONFIGURABLE_COMMANDS = {
    "投喂": {
        "name": "投喂",
        "description": f"给{BOT_NAME}投喂食物",
        "emoji": "🍽️",
    },
    "忏悔": {
        "name": "忏悔",
        "description": f"向{BOT_NAME}忏悔",
        "emoji": "🙏",
    },
    "好感度": {
        "name": "好感度",
        "description": "查询好感度状态",
        "emoji": "💕",
    },
    "blackjack": {
        "name": "21点",
        "description": "玩21点游戏",
        "emoji": "🃏",
    },
    "draw": {
        "name": "绘图",
        "description": "AI生成图片",
        "emoji": "🎨",
    },
}


class UserCommandSettingsService:
    """用户命令设置服务"""

    async def get_user_command_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户的命令设置

        Args:
            user_id: 用户的 Discord ID

        Returns:
            如果用户有设置记录，返回 enabled_commands 字典；否则返回 None
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(UserCommandSettings).where(
                    UserCommandSettings.user_id == user_id
                )
            )
            settings = result.scalar_one_or_none()
            if settings:
                return settings.enabled_commands
            return None

    async def save_user_command_settings(
        self, user_id: str, enabled_commands: Dict[str, Any]
    ) -> bool:
        """
        保存用户的命令设置

        Args:
            user_id: 用户的 Discord ID
            enabled_commands: 启用的命令列表（字典格式）

        Returns:
            保存是否成功
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(UserCommandSettings).where(
                        UserCommandSettings.user_id == user_id
                    )
                )
                settings = result.scalar_one_or_none()

                if settings:
                    # 更新现有记录
                    settings.enabled_commands = enabled_commands
                else:
                    # 创建新记录
                    settings = UserCommandSettings(
                        user_id=user_id, enabled_commands=enabled_commands
                    )
                    session.add(settings)

                await session.commit()
                log.info(f"成功保存用户 {user_id} 的命令设置: {enabled_commands}")
                return True
        except Exception as e:
            log.error(f"保存用户 {user_id} 的命令设置时出错: {e}", exc_info=True)
            return False

    async def delete_user_command_settings(self, user_id: str) -> bool:
        """
        删除用户的命令设置（恢复默认：启用所有命令）

        Args:
            user_id: 用户的 Discord ID

        Returns:
            删除是否成功
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(UserCommandSettings).where(
                        UserCommandSettings.user_id == user_id
                    )
                )
                settings = result.scalar_one_or_none()

                if settings:
                    await session.delete(settings)
                    await session.commit()
                    log.info(f"成功删除用户 {user_id} 的命令设置，恢复默认")
                return True
        except Exception as e:
            log.error(f"删除用户 {user_id} 的命令设置时出错: {e}", exc_info=True)
            return False

    async def is_command_enabled_for_user(
        self, user_id: str, command_name: str
    ) -> bool:
        """
        检查命令是否对用户启用

        Args:
            user_id: 帖子拥有者的 Discord ID
            command_name: 命令名称

        Returns:
            命令是否启用（默认启用所有命令）
        """
        settings = await self.get_user_command_settings(user_id)
        if settings is None:
            # 没有设置记录，默认启用所有命令
            return True

        enabled_commands = settings.get("enabled_commands")
        if enabled_commands is None:
            # enabled_commands 为空，默认启用所有命令
            return True

        return command_name in enabled_commands

    def get_configurable_commands(self) -> Dict[str, Dict[str, str]]:
        """
        获取可配置的命令列表

        Returns:
            命令配置字典
        """
        return CONFIGURABLE_COMMANDS


# 全局服务实例
user_command_settings_service = UserCommandSettingsService()
