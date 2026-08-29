# -*- coding: utf-8 -*-
"""
交互可用性检查工具函数
"""

import discord
from typing import Tuple, Optional

from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config
from src.chat.services.config_override_service import config_override_service
from src.config import DEVELOPER_USER_IDS
from src.chat.features.affection.services.user_command_settings_service import (
    user_command_settings_service,
)


async def check_interaction_channel_availability(
    interaction: discord.Interaction,
) -> Tuple[bool, str]:
    """
    检查交互所在的频道是否可用（非禁言、非禁用频道、非置顶帖子）

    Args:
        interaction: Discord 交互对象

    Returns:
        (is_allowed, error_message): 是否允许交互，错误消息（如果不允许）
    """
    channel = interaction.channel

    # 0. 检查频道是否被禁言
    if channel and await chat_db_manager.is_channel_muted(channel.id):
        return False, "呜…我现在不能在这里说话啦…"

    # 1. 检查是否在禁用的频道中
    disabled_ids = await config_override_service.get_json(
        "channels.disabled_interaction_ids",
        chat_config.DISABLED_INTERACTION_CHANNEL_IDS,
    )
    if channel and channel.id in disabled_ids:
        return False, "嘘... 在这里我需要保持安静，我们去别的地方聊吧？"

    # 2. 检查是否在置顶的帖子中
    if isinstance(channel, discord.Thread) and channel.flags.pinned:
        return (
            False,
            "唔... 这个帖子被置顶了，一定是很重要的内容。我们不要在这里聊天，以免打扰到大家哦。",
        )

    return True, ""


async def check_command_availability_for_thread_owner(
    interaction: discord.Interaction,
    command_name: str,
) -> Tuple[bool, str]:
    """
    检查命令是否在帖子拥有者的设置中启用

    此函数用于检查在帖子（Thread）中使用的命令是否被帖子拥有者允许。
    如果不在帖子中或帖子拥有者没有设置，默认允许所有命令。

    Args:
        interaction: Discord 交互对象
        command_name: 命令名称（如 "投喂"、"忏悔" 等）

    Returns:
        (is_allowed, error_message): 是否允许命令，错误消息（如果不允许）
    """
    channel = interaction.channel

    # 只在帖子（Thread）中检查
    if not isinstance(channel, discord.Thread):
        return True, ""

    # 获取帖子拥有者
    thread_owner_id = str(channel.owner_id)

    # 如果命令使用者就是帖子拥有者，则允许
    if str(interaction.user.id) == thread_owner_id:
        return True, ""

    # 检查帖子拥有者的命令设置
    is_enabled = await user_command_settings_service.is_command_enabled_for_user(
        thread_owner_id, command_name
    )

    if not is_enabled:
        return False, f"帖子主人没有开启 `/{command_name}` 功能哦～"

    return True, ""


async def check_command_availability(
    interaction: discord.Interaction,
    command_name: str,
) -> Tuple[bool, str]:
    """
    综合检查命令是否可用

    包括：
    1. 频道可用性检查（禁言、禁用频道、置顶帖子）
    2. 帖子拥有者的命令设置检查

    Args:
        interaction: Discord 交互对象
        command_name: 命令名称（如 "投喂"、"忏悔" 等）

    Returns:
        (is_allowed, error_message): 是否允许命令，错误消息（如果不允许）
    """
    # 1. 检查频道可用性
    is_available, error_message = await check_interaction_channel_availability(
        interaction
    )
    if not is_available:
        return False, error_message

    # 2. 检查帖子拥有者的命令设置
    is_allowed, error_message = await check_command_availability_for_thread_owner(
        interaction, command_name
    )
    if not is_allowed:
        return False, error_message

    return True, ""


def is_developer(user_id: int) -> bool:
    """
    检查用户是否为开发者（可绕过冷却时间）

    Args:
        user_id: 用户 Discord ID

    Returns:
        是否为开发者
    """
    return user_id in DEVELOPER_USER_IDS
