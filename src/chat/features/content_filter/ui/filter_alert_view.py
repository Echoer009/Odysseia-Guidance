# -*- coding: utf-8 -*-

import logging
from datetime import datetime, timezone, timedelta
from typing import List
import random

import discord
from discord.ui import View, Button
from discord import ButtonStyle, Interaction

from src.chat.config.chat_config import BLACKLIST_BAN_DURATION_MINUTES
from src.chat.utils.database import chat_db_manager
from src.chat.services.warning_service import record_warning_and_check_blacklist
from src.chat.features.personal_memory.services.conversation_block_service import (
    conversation_block_service,
)
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)
from src.chat.features.content_filter.services.content_filter_service import (
    ignore_keywords,
)
from src.config import BOT_NAME, COMMUNITY_NAME

log = logging.getLogger(__name__)


class FilterAlertView(View):
    def __init__(
        self,
        user_id: int,
        guild_id: int,
        bot: discord.Client,
        matched_keywords: List[str],
    ):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.guild_id = guild_id
        self.bot = bot
        self.matched_keywords = matched_keywords

    async def _disable_all(self, interaction: Interaction, result_text: str):
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True
        if interaction.message:
            embed = interaction.message.embeds[0] if interaction.message.embeds else None
            if embed:
                embed.description = (
                    (embed.description or "") + f"\n\n✅ {result_text}"
                )
            await interaction.message.edit(embed=embed, view=self)

    async def _send_warning_dm(self, user_id: int, reason: str, ban_duration: int):
        try:
            user = await self.bot.fetch_user(user_id)
            if not user:
                return
            embed = discord.Embed(
                title="⚠️ 警告通知",
                description=f"你已被 **{BOT_NAME}** 警告并临时封禁 **{ban_duration}** 分钟。",
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="警告理由", value=reason, inline=False)
            embed.add_field(
                name="温馨提示",
                value="请遵守社区规范，尊重他人。如有疑问，请联系管理员。",
                inline=False,
            )
            embed.set_footer(text=f"{COMMUNITY_NAME}社区 · 警告系统")
            await user.send(embed=embed)
        except Exception as e:
            log.error(f"发送警告私信失败: {e}")

    async def _send_ban_dm(self, user_id: int, reason: str, ban_duration: int):
        try:
            user = await self.bot.fetch_user(user_id)
            if not user:
                return
            embed = discord.Embed(
                title="🔨 封禁通知",
                description=f"你已被 **{BOT_NAME}** 封禁 **{ban_duration}** 分钟。",
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc),
            )
            embed.add_field(name="封禁理由", value=reason, inline=False)
            embed.set_footer(text=f"{COMMUNITY_NAME}社区 · 封禁系统")
            await user.send(embed=embed)
        except Exception as e:
            log.error(f"发送封禁私信失败: {e}")

    async def _do_warn(self, interaction: Interaction):
        await interaction.response.defer()
        try:
            min_d, max_d = BLACKLIST_BAN_DURATION_MINUTES
            ban_duration = random.randint(min_d, max_d)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ban_duration)
            reason = "过界亲密：文爱检测系统触发自动警告"

            await self._send_warning_dm(self.user_id, reason, ban_duration)
            await record_warning_and_check_blacklist(
                self.user_id, self.guild_id, expires_at
            )
            result_text = f"已警告用户 {self.user_id} 并临时封禁 {ban_duration} 分钟"
            log.info(result_text)
            await self._disable_all(interaction, result_text)
        except Exception as e:
            log.error(f"警告操作失败: {e}", exc_info=True)
            await self._disable_all(interaction, f"操作失败: {e}")

    async def _do_ban(self, interaction: Interaction):
        await interaction.response.defer()
        try:
            min_d, max_d = BLACKLIST_BAN_DURATION_MINUTES
            ban_duration = random.randint(min_d, max_d)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=ban_duration)
            reason = "过界亲密：文爱检测系统触发封禁"

            await chat_db_manager.add_to_blacklist(
                self.user_id, self.guild_id, expires_at
            )
            await self._send_ban_dm(self.user_id, reason, ban_duration)
            result_text = f"已封禁用户 {self.user_id} {ban_duration} 分钟"
            log.info(result_text)
            await self._disable_all(interaction, result_text)
        except Exception as e:
            log.error(f"封禁操作失败: {e}", exc_info=True)
            await self._disable_all(interaction, f"操作失败: {e}")

    async def _do_delete_blocks(self, interaction: Interaction):
        await interaction.response.defer()
        try:
            deleted_count = await conversation_block_service.delete_recent_blocks(
                str(self.user_id), count=5
            )
            result_text = f"已删除用户 {self.user_id} 的 {deleted_count} 个最近对话块"
            log.info(result_text)
            await self._disable_all(interaction, result_text)
        except Exception as e:
            log.error(f"删除对话块失败: {e}", exc_info=True)
            await self._disable_all(interaction, f"操作失败: {e}")

    async def _do_clear_history(self, interaction: Interaction):
        await interaction.response.defer()
        try:
            await personal_memory_service.delete_conversation_history(self.user_id)
            result_text = f"已清理用户 {self.user_id} 的最近对话历史"
            log.info(result_text)
            await self._disable_all(interaction, result_text)
        except Exception as e:
            log.error(f"清理对话历史失败: {e}", exc_info=True)
            await self._disable_all(interaction, f"操作失败: {e}")

    async def _do_ignore_keywords(self, interaction: Interaction):
        await interaction.response.defer()
        try:
            await ignore_keywords(self.matched_keywords)
            kw_text = ", ".join(f"`{kw}`" for kw in self.matched_keywords)
            result_text = f"已永久忽略关键词: {kw_text}"
            log.info(result_text)
            await self._disable_all(interaction, result_text)
        except Exception as e:
            log.error(f"忽略关键词失败: {e}", exc_info=True)
            await self._disable_all(interaction, f"操作失败: {e}")

    @discord.ui.button(label="⚠️ 警告", style=ButtonStyle.secondary, row=0)
    async def warn_button(self, interaction: Interaction, button: Button):
        await self._do_warn(interaction)

    @discord.ui.button(label="🔨 封禁", style=ButtonStyle.danger, row=0)
    async def ban_button(self, interaction: Interaction, button: Button):
        await self._do_ban(interaction)

    @discord.ui.button(label="🗑️ 删对话块", style=ButtonStyle.secondary, row=1)
    async def delete_blocks_button(self, interaction: Interaction, button: Button):
        await self._do_delete_blocks(interaction)

    @discord.ui.button(label="🧹 清对话历史", style=ButtonStyle.secondary, row=1)
    async def clear_history_button(self, interaction: Interaction, button: Button):
        await self._do_clear_history(interaction)

    @discord.ui.button(label="🔕 永久忽略", style=ButtonStyle.primary, row=2)
    async def ignore_button(self, interaction: Interaction, button: Button):
        await self._do_ignore_keywords(interaction)
