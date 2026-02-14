# -*- coding: utf-8 -*-
"""
交互可用性检查工具函数
"""

import discord
from typing import Tuple

from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config
from src.config import DEVELOPER_USER_IDS


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
    if channel and channel.id in chat_config.DISABLED_INTERACTION_CHANNEL_IDS:
        return False, "嘘... 在这里我需要保持安静，我们去别的地方聊吧？"

    # 2. 检查是否在置顶的帖子中
    if isinstance(channel, discord.Thread) and channel.flags.pinned:
        return (
            False,
            "唔... 这个帖子被置顶了，一定是很重要的内容。我们不要在这里聊天，以免打扰到大家哦。",
        )

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
