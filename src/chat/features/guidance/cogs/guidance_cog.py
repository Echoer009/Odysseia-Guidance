# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

GUIDANCE_APPLICATION_ID = int(os.getenv("VITE_DISCORD_CLIENT_ID") or "0")
GUIDANCE_TRIGGER_ROLE_ID = int(os.getenv("GUIDANCE_TRIGGER_ROLE_ID") or "0")
GUIDANCE_CHANNEL_ID = int(os.getenv("GUIDANCE_CHANNEL_ID") or "0")

WELCOME_EMBED_COLOR = 0xF39C12

DM_TITLE = "嗨～欢迎来到类脑社区！"
DM_DESCRIPTION = (
    "诶嘿，你终于来啦！我是类脑娘～\n\n"
    "我们社区可有意思了，角色卡、AI绘图……啥都有！"
    "大家都很友善的，你肯定会喜欢的\n\n"
    "不过这里人好多频道也好多，怕你迷路，所以我准备了一个小引导～\n"
    "点击下面的按钮，让我带你逛一圈吧！"
)
DM_BUTTON_LABEL = "前往引导频道"
DM_BUTTON_EMOJI = "✨"

CHANNEL_EMBED_TITLE = "让类脑娘带你逛逛～"
CHANNEL_EMBED_DESCRIPTION = (
    "好耶！你来了！\n\n"
    "社区里频道蛮多的，第一次来很容易转晕……"
    "所以我帮你整理了一份专属导览，会根据你感兴趣的内容推荐对应的频道！\n\n"
    "放心啦，不会花太长时间的，而且……有我陪着你嘛～\n"
    "点击下面的按钮就开始吧！"
)
CHANNEL_BUTTON_LABEL = "开始引导"
CHANNEL_BUTTON_EMOJI = "✨"

GUILD_ID = int(os.getenv("GUILD_ID", "0").split(",")[0].strip() or "0")

THUMBNAIL_URL = "https://cdn.discordapp.com/attachments/1403347767912562728/1492801117774418053/ComfyUI_temp_rppad_00648_.png"


class ChannelActivityView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label=CHANNEL_BUTTON_LABEL,
        style=discord.ButtonStyle.primary,
        emoji=CHANNEL_BUTTON_EMOJI,
        custom_id="guidance:start",
    )
    async def start_guidance(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if GUIDANCE_APPLICATION_ID == 0:
            await interaction.response.send_message(
                "引导功能暂时不可用，请稍后再试。",
                ephemeral=True,
            )
            return

        try:
            from src.chat.utils.database import chat_db_manager

            await chat_db_manager.set_global_setting(
                f"user_intent:{interaction.user.id}", "guidance"
            )
            await interaction.response.launch_activity()
            log.info(f"Launched guidance activity for user {interaction.user.id}")
        except discord.InteractionResponded:
            log.warning(f"Interaction already responded for user {interaction.user.id}")
        except discord.errors.NotFound as e:
            log.error(f"NotFound launching activity for {interaction.user.id}: {e}")
            try:
                await interaction.followup.send(
                    "启动引导失败，请检查网络或稍后再试。",
                    ephemeral=True,
                )
            except discord.errors.NotFound:
                pass
        except Exception as e:
            log.error(f"Error launching guidance for {interaction.user.id}: {e}")
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "启动引导时遇到错误，请稍后再试。",
                        ephemeral=True,
                    )
                except discord.errors.NotFound:
                    pass


def build_dm_embed() -> discord.Embed:
    embed = discord.Embed(
        title=DM_TITLE,
        description=DM_DESCRIPTION,
        color=WELCOME_EMBED_COLOR,
    )
    if THUMBNAIL_URL:
        embed.set_thumbnail(url=THUMBNAIL_URL)
    return embed


def build_channel_embed() -> discord.Embed:
    embed = discord.Embed(
        title=CHANNEL_EMBED_TITLE,
        description=CHANNEL_EMBED_DESCRIPTION,
        color=WELCOME_EMBED_COLOR,
    )
    if THUMBNAIL_URL:
        embed.set_thumbnail(url=THUMBNAIL_URL)
    return embed


def build_channel_view() -> ChannelActivityView:
    return ChannelActivityView()


class GuidanceCog(commands.Cog):
    """新成员引导 Activity 启动器"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._guidance_message_id: int | None = None

    async def cog_load(self):
        from src.chat.utils.database import chat_db_manager

        raw = await chat_db_manager.get_global_setting("guidance_message_id")
        if raw:
            self._guidance_message_id = int(raw)
            log.info(f"Loaded cached guidance_message_id: {self._guidance_message_id}")

    async def _ensure_channel_message(self):
        if GUIDANCE_CHANNEL_ID == 0 or GUILD_ID == 0:
            log.warning(
                "GUIDANCE_CHANNEL_ID or GUILD_ID not set, skip channel message setup."
            )
            return

        channel = self.bot.get_channel(GUIDANCE_CHANNEL_ID)
        if not channel or not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
            try:
                channel = await self.bot.fetch_channel(GUIDANCE_CHANNEL_ID)
            except Exception as e:
                log.error(f"Cannot fetch guidance channel {GUIDANCE_CHANNEL_ID}: {e}")
                return

        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
            return

        if self._guidance_message_id:
            try:
                old_msg = await channel.fetch_message(self._guidance_message_id)
                if old_msg and self.bot.user and old_msg.author.id == self.bot.user.id:
                    if old_msg.channel.id == GUIDANCE_CHANNEL_ID:
                        log.info(
                            f"Guidance channel message {self._guidance_message_id} exists in current channel, skipping."
                        )
                        return
                    else:
                        log.info(
                            f"Guidance channel message {self._guidance_message_id} is in a different channel ({old_msg.channel.id}), will resend to {GUIDANCE_CHANNEL_ID}."
                        )
            except discord.NotFound:
                log.info("Cached guidance message not found, will resend.")
            except Exception as e:
                log.warning(f"Error checking guidance message: {e}")

        embed = build_channel_embed()
        view = build_channel_view()
        msg = await channel.send(embed=embed, view=view)
        self._guidance_message_id = msg.id

        from src.chat.utils.database import chat_db_manager

        guidance_url = (
            f"https://discord.com/channels/{msg.guild.id if msg.guild else GUILD_ID}/{msg.channel.id}/{msg.id}"
        )
        await chat_db_manager.set_global_setting("guidance_message_id", str(msg.id))
        await chat_db_manager.set_global_setting("guidance_url", guidance_url)
        log.info(f"Sent guidance channel message: {msg.id}, url: {guidance_url}")

    def _get_guidance_jump_url(self) -> str | None:
        if not self._guidance_message_id or GUILD_ID == 0 or GUIDANCE_CHANNEL_ID == 0:
            return None
        return f"https://discord.com/channels/{GUILD_ID}/{GUIDANCE_CHANNEL_ID}/{self._guidance_message_id}"

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if GUIDANCE_TRIGGER_ROLE_ID == 0:
            return

        if before.bot or after.bot:
            return

        before_had = any(r.id == GUIDANCE_TRIGGER_ROLE_ID for r in before.roles)
        after_has = any(r.id == GUIDANCE_TRIGGER_ROLE_ID for r in after.roles)

        log.info(
            f"on_member_update: user={after.id} before_had={before_had} after_has={after_has} trigger_role={GUIDANCE_TRIGGER_ROLE_ID}"
        )

        if before_had or not after_has:
            return

        try:
            embed = build_dm_embed()
            jump_url = self._get_guidance_jump_url()

            if jump_url:
                view = discord.ui.View()
                view.add_item(
                    discord.ui.Button(
                        label=DM_BUTTON_LABEL,
                        emoji=DM_BUTTON_EMOJI,
                        style=discord.ButtonStyle.link,
                        url=jump_url,
                    )
                )
                await after.send(embed=embed, view=view)
            else:
                fallback_view = ChannelActivityView()
                await after.send(embed=embed, view=fallback_view)

            log.info(f"Sent guidance welcome DM to {after.id} ({after.display_name})")
        except discord.errors.Forbidden:
            log.warning(f"Cannot send DM to {after.id}, skipping guidance welcome.")
        except Exception as e:
            log.error(f"Failed to send guidance welcome to {after.id}: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.add_view(ChannelActivityView())
        log.info("Re-registered persistent ChannelActivityView")
        await self._ensure_channel_message()


async def setup(bot: commands.Bot):
    if GUIDANCE_TRIGGER_ROLE_ID == 0:
        log.warning(
            "GUIDANCE_TRIGGER_ROLE_ID not set in .env. Guidance welcome DM is disabled."
        )
    await bot.add_cog(GuidanceCog(bot))
