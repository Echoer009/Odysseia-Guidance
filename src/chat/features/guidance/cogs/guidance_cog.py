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

WELCOME_EMBED_COLOR = 0xCE422B
WELCOME_TITLE = "欢迎来到类脑社区 ✦"
WELCOME_DESCRIPTION = (
    "你好呀，新朋友！我是类脑娘，负责引导你熟悉这里～\n\n"
    "社区里有很多有趣的内容等你探索：角色卡、AI绘图、竞技场……\n"
    "点击下面的按钮，让我带你逛一逛吧！"
)
WELCOME_FOOTER = "类脑社区 · Odysseia"
BUTTON_LABEL = "开始引导"
BUTTON_EMOJI = "✨"


class GuidanceStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label=BUTTON_LABEL,
        style=discord.ButtonStyle.primary,
        emoji=BUTTON_EMOJI,
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


def build_welcome_embed() -> discord.Embed:
    embed = discord.Embed(
        title=WELCOME_TITLE,
        description=WELCOME_DESCRIPTION,
        color=WELCOME_EMBED_COLOR,
    )
    embed.set_footer(text=WELCOME_FOOTER)
    return embed


class GuidanceCog(commands.Cog):
    """新成员引导 Activity 启动器"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
            embed = build_welcome_embed()
            view = GuidanceStartView()
            await after.send(embed=embed, view=view)
            log.info(f"Sent guidance welcome DM to {after.id} ({after.display_name})")
        except discord.errors.Forbidden:
            log.warning(f"Cannot send DM to {after.id}, skipping guidance welcome.")
        except Exception as e:
            log.error(f"Failed to send guidance welcome to {after.id}: {e}")


async def setup(bot: commands.Bot):
    if GUIDANCE_TRIGGER_ROLE_ID == 0:
        log.warning(
            "GUIDANCE_TRIGGER_ROLE_ID not set in .env. Guidance welcome DM is disabled."
        )
    await bot.add_cog(GuidanceCog(bot))
