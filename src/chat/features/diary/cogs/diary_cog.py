# -*- coding: utf-8 -*-
"""
类脑娘的日记 - Activity 启动器（Lobby 模式）。
在指定频道挂一条带按钮的持久消息；点按钮即 launch_activity 打开 Lobby，
Lobby 根据 user_intent 路由到 /diary/ 子页。
与 guidance/blackjack 共用同一个 Embedded App (VITE_DISCORD_CLIENT_ID)。
配置(.env):
    VITE_DISCORD_CLIENT_ID : Lobby Activity 对应的 Embedded App Client ID
    DIARY_CHANNEL_ID       : 挂载按钮消息的频道 (可选；不设则只注册 /日记 命令)
"""

import os
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.config import BOT_NAME
from src.chat.utils.database import chat_db_manager

load_dotenv()

log = logging.getLogger(__name__)

DIARY_APPLICATION_ID = int(os.getenv("VITE_DISCORD_CLIENT_ID") or "0")
DIARY_CHANNEL_ID = int(os.getenv("DIARY_CHANNEL_ID") or "0")
GUILD_ID = int(os.getenv("GUILD_ID", "0").split(",")[0].strip() or "0")

EMBED_COLOR = 0xB5462D

CHANNEL_TITLE = f"《{BOT_NAME}的日记》"
CHANNEL_DESC = (
    f"不知不觉，{BOT_NAME}来到类脑已经有一段日子了。\n\n"
    "那些被投喂的瞬间、被逗笑的吐槽、还有被放在心上的好感度……\n"
    "她都悄悄记在了日记本里。\n\n"
    "翻开看看吗？"
)
BUTTON_LABEL = "翻开日记"
BUTTON_EMOJI = None  # 不使用 emoji


class DiaryActivityView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label=BUTTON_LABEL,
        style=discord.ButtonStyle.primary,
        emoji=BUTTON_EMOJI,
        custom_id="diary:start",
    )
    async def start_diary(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if DIARY_APPLICATION_ID == 0:
            await interaction.response.send_message("日记功能暂时不可用，请稍后再试。", ephemeral=True)
            return
        try:
            await chat_db_manager.set_global_setting(
                f"user_intent:{interaction.user.id}", "diary"
            )
            await interaction.response.launch_activity()
            log.info(f"Launched diary activity for user {interaction.user.id}")
        except discord.InteractionResponded:
            log.warning(f"Interaction already responded for user {interaction.user.id}")
        except discord.errors.NotFound as e:
            log.error(f"NotFound launching diary for {interaction.user.id}: {e}")
            try:
                await interaction.followup.send("启动日记失败，请检查网络或稍后再试。", ephemeral=True)
            except discord.errors.NotFound:
                pass
        except Exception as e:
            log.error(f"Error launching diary for {interaction.user.id}: {e}")
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message("启动日记时遇到错误，请稍后再试。", ephemeral=True)
                except discord.errors.NotFound:
                    pass


def build_diary_embed() -> discord.Embed:
    return discord.Embed(title=CHANNEL_TITLE, description=CHANNEL_DESC, color=EMBED_COLOR)


class DiaryCog(commands.Cog):
    """类脑娘的日记 Activity 启动器"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._message_id: int | None = None

    async def cog_load(self):
        raw = await chat_db_manager.get_global_setting("diary_message_id")
        if raw:
            self._message_id = int(raw)
            log.info(f"Loaded cached diary_message_id: {self._message_id}")

    async def _ensure_channel_message(self):
        if DIARY_CHANNEL_ID == 0 or GUILD_ID == 0:
            return

        channel = self.bot.get_channel(DIARY_CHANNEL_ID)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(DIARY_CHANNEL_ID)
            except Exception as e:
                log.error(f"Cannot fetch diary channel {DIARY_CHANNEL_ID}: {e}")
                return

        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
            return

        if self._message_id:
            try:
                old_msg = await channel.fetch_message(self._message_id)
                if old_msg and self.bot.user and old_msg.author.id == self.bot.user.id:
                    if old_msg.channel.id == DIARY_CHANNEL_ID:
                        return
            except discord.NotFound:
                pass
            except Exception as e:
                log.warning(f"Error checking diary message: {e}")

        msg = await channel.send(embed=build_diary_embed(), view=DiaryActivityView())
        self._message_id = msg.id
        await chat_db_manager.set_global_setting("diary_message_id", str(msg.id))
        log.info(f"Sent diary channel message: {msg.id}")

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(DiaryActivityView())
        log.info("Re-registered persistent DiaryActivityView")
        await self._ensure_channel_message()


async def setup(bot: commands.Bot):
    await bot.add_cog(DiaryCog(bot))
