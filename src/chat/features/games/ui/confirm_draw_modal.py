# -*- coding: utf-8 -*-

import discord
from src.chat.features.games.ui.ghost_card_ui import GhostCardUI
from src.chat.features.games.services.ghost_card_service import ghost_card_service
from src.chat.features.games.config.text_config import text_config
import logging

log = logging.getLogger(__name__)


class DrawConfirmationView(discord.ui.View):
    """抽牌确认视图"""

    def __init__(
        self,
        game_id: str,
        card_index: int,
        card_name: str,
        reaction_text: str,
        reaction_image_url: str,
    ):
        super().__init__(timeout=60)
        self.game_id = game_id
        self.card_index = card_index
        self.card_name = card_name
        self.reaction_text = reaction_text
        self.reaction_image_url = reaction_image_url

    @discord.ui.button(
        label=text_config.confirm_modal.confirm_button,
        style=discord.ButtonStyle.success,
    )
    async def confirm_draw(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """确认抽这张牌"""
        # 延迟响应，以延长交互的生命周期
        await interaction.response.defer()

        # 通过interaction.client获取GhostCardCog实例
        cog = interaction.client.get_cog("GhostCardCog")
        if cog:
            await cog.handle_confirmed_draw(interaction, self.game_id, self.card_index)
        else:
            log.error("GhostCardCog not found")
            # 由于已经调用了defer，这里需要使用followup发送消息
            await interaction.followup.send(
                "❌ 处理操作时出现错误，请稍后再试。", ephemeral=True
            )
        self.stop()

    @discord.ui.button(
        label=text_config.confirm_modal.cancel_button, style=discord.ButtonStyle.danger
    )
    async def cancel_draw(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """取消抽这张牌"""
        game = ghost_card_service.get_game_state(self.game_id)
        if not game:
            await interaction.response.edit_message(
                content="游戏不见了...", embed=None, view=None
            )
            return

        reaction_text, reaction_image_url = (
            ghost_card_service.get_reaction_for_selection(
                self.game_id, self.card_index, "cancelled"
            )
        )

        if not reaction_text:
            # Fallback in case reaction fails
            await interaction.response.edit_message(
                content="发生了一点小错误，请重试。", embed=None, view=None
            )
            return

        embed = discord.Embed(
            title="", description=f"**{reaction_text}**", color=discord.Color.blue()
        )
        if reaction_image_url:
            embed.set_thumbnail(url=reaction_image_url)

        await interaction.response.edit_message(embed=embed, view=None)

        # 延迟3秒后返回抽牌界面
        import asyncio

        await asyncio.sleep(3)

        # 创建并返回抽牌界面
        game_embed = GhostCardUI.create_game_embed(self.game_id)
        game_view = (
            interaction.client.get_cog("GhostCardCog").create_game_view(self.game_id)
            if interaction.client.get_cog("GhostCardCog")
            else None
        )

        try:
            await interaction.edit_original_response(embed=game_embed, view=game_view)
        except:
            # 如果无法编辑原消息，则发送新消息
            await interaction.followup.send(
                embed=game_embed, view=game_view, ephemeral=True
            )

        self.stop()
