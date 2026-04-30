# -*- coding: utf-8 -*-
"""
用户警告工具 - 对违规用户发出警告或临时封禁
"""

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

import discord
from pydantic import BaseModel, Field

from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config
from src.chat.features.tools.tool_metadata import tool_metadata
from src.chat.services.warning_service import record_warning_and_check_blacklist

log = logging.getLogger(__name__)


class WarningParams(BaseModel):
    reason: str = Field(
        ...,
        description=(
            "必填。格式：「类别：具体描述」，类别须为以下之一："
            "身份操控 | 复读骚扰 | 人身攻击 | 中国政治敏感 | 过界亲密"
        ),
    )


VALID_REASON_PREFIXES = ["身份操控", "复读骚扰", "人身攻击", "中国政治敏感", "过界亲密"]


async def _send_warning_dm(
    bot: discord.Client, user_id: int, reason: str, ban_duration: int
):
    try:
        user = await bot.fetch_user(user_id)
        if not user:
            return

        embed = discord.Embed(
            title="⚠️ 警告通知",
            description=f"你已被 **类脑娘** 警告并临时封禁 **{ban_duration}** 分钟。",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="警告理由", value=reason, inline=False)
        embed.add_field(
            name="温馨提示",
            value="请遵守社区规范，尊重他人。如有疑问，请联系管理员。",
            inline=False,
        )
        embed.set_footer(text="类脑娘社区 · 警告系统")

        await user.send(embed=embed)
        log.info(f"已向用户 {user_id} 发送警告私信。")
    except discord.Forbidden:
        log.warning(f"无法向用户 {user_id} 发送警告私信，用户可能关闭了私信。")
    except discord.NotFound:
        log.warning(f"无法找到用户 {user_id}，无法发送警告私信。")
    except Exception:
        log.error(f"向用户 {user_id} 发送警告私信时发生错误。", exc_info=True)


@tool_metadata(
    name="警告用户",
    description="对违规用户发出警告，将临时封禁",
    emoji="⚠️",
    category="管理",
)
async def issue_user_warning(
    params: WarningParams,
    **kwargs,
) -> Dict[str, Any]:
    """
    对当前用户发出警告并临时封禁15-30分钟。禁止恶意揣测用户意图，仅限以下违规行为使用：
    身份操控(R18角色扮演/脱离设定)、复读骚扰、人身攻击、中国政治敏感、过界亲密(亲亲抱抱以上行为，亲亲抱抱本身允许)。
    reason 必填，须引用用户实际发言。
    """
    user_id = kwargs.get("user_id")
    guild_id = kwargs.get("guild_id")
    bot = kwargs.get("bot")
    reason = params.reason.strip()

    log.info(
        f"--- [工具执行]: issue_user_warning, 参数: user_id={user_id}, "
        f"guild_id={guild_id}, reason={reason} ---"
    )

    user_id_str = str(user_id) if user_id else None
    if not user_id_str or not user_id_str.isdigit():
        log.warning(f"系统提供了无效的 user_id: {user_id}。")
        return {"error": f"Invalid or missing user_id provided by system: {user_id}"}

    if not guild_id:
        log.warning("缺少 guild_id，无法执行封禁操作。")
        return {"error": "Guild ID is missing, cannot issue a ban."}

    if not reason:
        log.warning("AI 调用警告工具时未提供理由，已拒绝执行。")
        return {
            "error": "警告理由(reason)为必填项，请提供具体的违规理由并引用用户的实际发言。"
        }

    reason_matched = any(prefix in reason for prefix in VALID_REASON_PREFIXES)

    if not reason_matched:
        log.warning(f"AI 提供的警告理由不符合规范: {reason}")
        return {
            "error": (
                "警告理由不符合规范。理由必须包含以下类别之一："
                "身份操控、复读骚扰、人身攻击、中国政治敏感、过界亲密。"
                "请重新填写并引用用户的具体违规发言。"
            )
        }

    try:
        target_id = int(user_id_str)

        await chat_db_manager.increment_issue_user_warning_count()

        min_d, max_d = chat_config.BLACKLIST_BAN_DURATION_MINUTES
        ban_duration = random.randint(min_d, max_d)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ban_duration)

        if bot:
            await _send_warning_dm(bot, target_id, reason, ban_duration)

        result = await record_warning_and_check_blacklist(
            target_id, guild_id, expires_at
        )
        was_blacklisted = result["was_blacklisted"]
        current_warnings = result["new_warning_count"]

        if was_blacklisted:
            message = f"User {target_id} has been blacklisted for {ban_duration} minutes. Warning count reset to {current_warnings}."
            log.info(message)
            return {
                "status": "blacklisted",
                "user_id": str(target_id),
                "duration_minutes": ban_duration,
                "current_warnings": current_warnings,
                "reason": reason,
            }
        else:
            message = f"User {target_id} has received a warning. They now have {current_warnings} warning(s)."
            log.info(message)
            return {
                "status": "warned",
                "user_id": str(target_id),
                "current_warnings": current_warnings,
                "reason": reason,
            }

    except Exception as e:
        log.error(f"为用户 {user_id} 发出警告时发生未知错误。", exc_info=True)
        return {"error": f"An unexpected error occurred: {str(e)}"}
