# -*- coding: utf-8 -*-

import discord
import logging
import asyncio
from src.chat.features.games.services.ghost_card_service import ghost_card_service
from src.chat.features.games.ui.ghost_card_ui import GhostCardUI
from src.chat.features.odysseia_coin.service.coin_service import coin_service

log = logging.getLogger(__name__)


class BetModal(discord.ui.Modal, title="自定义下注"):
    bet_amount = discord.ui.TextInput(
        label="下注金额",
        placeholder="请输入自定义下注金额 (最低1类脑币)",
        required=True,
        min_length=1,
        max_length=5,
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            bet_value = int(self.bet_amount.value)
            if bet_value <= 0:
                await interaction.response.send_message(
                    "❌ 下注金额必须大于0。", ephemeral=True
                )
                return
            if bet_value > 10000:
                await interaction.response.send_message(
                    "❌ 下注金额不能超过10000。", ephemeral=True
                )
                return
        except ValueError:
            await interaction.response.send_message(
                "❌ 请输入有效的数字。", ephemeral=True
            )
            return

        user_id = interaction.user.id
        guild_id = interaction.guild.id if interaction.guild else 0

        balance = await coin_service.get_balance(user_id)
        if balance < bet_value:
            await interaction.response.send_message(
                f"❌ 你的类脑币不足！需要 {bet_value}，你只有 {balance}。",
                ephemeral=True,
            )
            return

        # 在游戏开始前决定AI策略
        ai_strategy = ghost_card_service.determine_ai_strategy()

        await coin_service.remove_coins(user_id, bet_value, "下注抽鬼牌游戏")

        # 编辑原始消息以显示加载状态
        await interaction.response.edit_message(
            content="正在发牌...", embed=None, view=None
        )

        try:
            game_id = ghost_card_service.start_new_game(
                user_id, guild_id, bet_amount=bet_value, ai_strategy=ai_strategy
            )

            game = ghost_card_service.get_game_state(game_id)
            if not game:
                raise ValueError("游戏创建失败")

            if game["current_turn"] == "ai":
                ai_thinking_embed = GhostCardUI.create_game_embed(game_id)
                await interaction.edit_original_response(
                    content=None, embed=ai_thinking_embed, view=None
                )

                await asyncio.sleep(3)

                ai_success, ai_message, reaction_text, reaction_image_url = (
                    ghost_card_service.ai_draw_card(game_id)
                )

                if ai_success:
                    ai_drawn_embed = GhostCardUI.create_ai_draw_embed(
                        game_id, ai_message, reaction_text, reaction_image_url
                    )
                    await interaction.edit_original_response(
                        embed=ai_drawn_embed, view=None
                    )

                    game = ghost_card_service.get_game_state(game_id)

                    if game and game["game_over"]:
                        await asyncio.sleep(4)
                        await self.cog.handle_game_over(interaction, game_id)
                    else:
                        await asyncio.sleep(4)
                        player_turn_embed = GhostCardUI.create_game_embed(game_id)
                        player_turn_view = self.cog.create_game_view(game_id)
                        await interaction.edit_original_response(
                            embed=player_turn_embed, view=player_turn_view
                        )
                else:
                    error_embed = GhostCardUI.create_game_embed(game_id)
                    error_view = self.cog.create_game_view(game_id)
                    await interaction.edit_original_response(
                        embed=error_embed, view=error_view
                    )
            else:
                embed = GhostCardUI.create_game_embed(game_id)
                view = self.cog.create_game_view(game_id)
                await interaction.edit_original_response(
                    content=None, embed=embed, view=view
                )

        except Exception as e:
            log.error(f"处理自定义下注并开始游戏时出错: {e}")
            await interaction.edit_original_response(
                content="❌ 开始游戏时出现错误，赌注已退还。", embed=None, view=None
            )
            await coin_service.add_coins(user_id, bet_value, "游戏开始失败退款")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error(f"BetModal 发生错误: {error}")
        await interaction.response.send_message(
            "❌ 出现了一个未知的错误。", ephemeral=True
        )
