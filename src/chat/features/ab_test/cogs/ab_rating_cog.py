# -*- coding: utf-8 -*-
"""
A/B 测试评价 Cog

处理实验回复评价卡片的按钮投票与差评反馈，
并轮询 AI 重载标记以及时应用后台改动。
"""

import logging

import discord
from discord.ext import commands, tasks

from src.chat.features.ab_test.services.ab_test_service import ab_test_service

log = logging.getLogger(__name__)

VOTE_MAP = {
    "ab:vote:better": 1,
    "ab:vote:worse": 2,
    "ab:vote:same": 3,
}

FEEDBACK_REASONS = ["不符合人设", "说错事实", "太机械", "太啰嗦", "格式乱", "其他"]


def build_reason_select(reply_id: int) -> discord.ui.Select:
    return discord.ui.Select(
        custom_id=f"ab:reason:{reply_id}",
        placeholder="选择哪些地方不行(可多选)",
        min_values=1,
        max_values=len(FEEDBACK_REASONS),
        options=[
            discord.SelectOption(label=reason, value=reason)
            for reason in FEEDBACK_REASONS
        ],
    )


def build_comment_button(reply_id: int) -> discord.ui.Button:
    return discord.ui.Button(
        custom_id=f"ab:comment:{reply_id}",
        label="写两句补充",
        style=discord.ButtonStyle.secondary,
    )


def build_reason_view(reply_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(build_reason_select(reply_id))
    return view


def build_comment_view(reply_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(build_comment_button(reply_id))
    return view


class ABFeedbackModal(discord.ui.Modal):
    def __init__(self, reply_id: int):
        super().__init__(title="想补充就写两句")
        self.reply_id = reply_id
        self.free_text_input = discord.ui.TextInput(
            label="补充说明(可不填)",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=False,
        )
        self.add_item(self.free_text_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await ab_test_service.record_feedback(
                self.reply_id,
                interaction.user.id,
                [],
                self.free_text_input.value or None,
            )
            await interaction.response.send_message("已收到反馈,谢谢!", ephemeral=True)
        except Exception as e:
            log.error(f"[A/B] 记录差评反馈失败: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "反馈记录失败,请稍后再试。", ephemeral=True
                )


class ABRatingCog(commands.Cog):
    """
    处理 A/B 实验回复评价卡片的持久按钮交互。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ai_reload_check.start()

    async def cog_unload(self):
        self.ai_reload_check.cancel()

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type is not discord.InteractionType.component:
            return
        custom_id = (interaction.data or {}).get("custom_id", "")
        if not isinstance(custom_id, str) or not custom_id.startswith("ab:"):
            return
        try:
            if custom_id.startswith("ab:vote:"):
                await self._handle_vote(interaction, custom_id)
            elif custom_id.startswith("ab:reason:"):
                await self._handle_reason(interaction, custom_id)
            elif custom_id.startswith("ab:comment:"):
                await self._handle_comment(interaction, custom_id)
        except Exception as e:
            log.error(f"[A/B] 处理评价交互失败: {e}", exc_info=True)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "操作失败,请稍后再试。", ephemeral=True
                    )
                except Exception:
                    pass

    async def _handle_vote(self, interaction: discord.Interaction, custom_id: str):
        vote = VOTE_MAP.get(custom_id)
        if vote is None or interaction.message is None:
            return
        reply = await ab_test_service.get_reply_by_message_id(interaction.message.id)
        if not reply:
            await interaction.response.send_message(
                "这条回复不属于任何进行中的实验", ephemeral=True
            )
            return
        await ab_test_service.record_vote(reply["id"], interaction.user.id, vote)
        if vote == 2:
            await interaction.response.send_message(
                "已记录。哪里不行?选一下(可多选)",
                view=build_reason_view(reply["id"]),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message("已记录,谢谢!", ephemeral=True)

    async def _handle_reason(self, interaction: discord.Interaction, custom_id: str):
        try:
            reply_id = int(custom_id.split(":")[2])
        except (IndexError, ValueError):
            return
        values = (interaction.data or {}).get("values") or []
        await ab_test_service.record_feedback(reply_id, interaction.user.id, values, None)
        await interaction.response.edit_message(
            content="已记录,谢谢!还想补充可以点下面。",
            view=build_comment_view(reply_id),
        )

    async def _handle_comment(self, interaction: discord.Interaction, custom_id: str):
        try:
            reply_id = int(custom_id.split(":")[2])
        except (IndexError, ValueError):
            return
        await interaction.response.send_modal(ABFeedbackModal(reply_id))

    @tasks.loop(seconds=30)
    async def ai_reload_check(self):
        try:
            if await ab_test_service.consume_ai_reload_pending():
                log.info("[A/B] 检测到 AI 重载标记，开始重载 Provider 与模型配置。")
                from src.chat.services.ai.service import ai_service
                from src.chat.services.ai.config.models import (
                    reload_model_configs_async,
                )

                await ai_service.reload_providers()
                await reload_model_configs_async()
                log.info("[A/B] AI 配置重载完成。")
        except Exception as e:
            log.error(f"[A/B] 处理 AI 重载标记时出错: {e}", exc_info=True)

    @ai_reload_check.before_loop
    async def before_ai_reload_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(ABRatingCog(bot))
    log.info("ABRatingCog 已加载。")
