# -*- coding: utf-8 -*-

import discord
import logging
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.config.chat_config import WARMUP_MESSAGES
from src.chat.utils.prompt_utils import replace_emojis

log = logging.getLogger(__name__)


class WarmupConsentView(discord.ui.View):
    """
    一个用于征求用户是否同意暖贴的私信视图。
    """

    def __init__(self, user_id: int):
        super().__init__(timeout=None)  # 永久有效
        self.user_id = user_id

    @discord.ui.button(
        label=WARMUP_MESSAGES["consent_accept_label"],
        style=discord.ButtonStyle.success,
        custom_id="warmup_consent_accept",
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        """用户同意继续接收暖贴。"""
        try:
            # 实际上无需操作，因为默认就是开启的。但为了明确，我们调用一次。
            await coin_service.set_warmup_preference(
                user_id=self.user_id, wants_warmup=True
            )
            response_text = replace_emojis(WARMUP_MESSAGES["consent_accept_response"])
            await interaction.response.edit_message(
                content=response_text,
                view=None,  # 禁用按钮
            )
            log.info(f"用户 {self.user_id} 通过私信同意了暖贴功能。")
        except Exception as e:
            log.error(f"处理用户 {self.user_id} 同意暖贴时出错: {e}", exc_info=True)
            error_text = replace_emojis(WARMUP_MESSAGES["consent_error_response"])
            await interaction.response.edit_message(content=error_text, view=None)

    @discord.ui.button(
        label=WARMUP_MESSAGES["consent_decline_label"],
        style=discord.ButtonStyle.danger,
        custom_id="warmup_consent_decline",
    )
    async def decline(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """用户拒绝接收暖贴。"""
        try:
            await coin_service.set_warmup_preference(
                user_id=self.user_id, wants_warmup=False
            )
            response_text = replace_emojis(WARMUP_MESSAGES["consent_decline_response"])
            await interaction.response.edit_message(
                content=response_text,
                view=None,  # 禁用按钮
            )
            log.info(f"用户 {self.user_id} 通过私信拒绝了暖贴功能。")
        except Exception as e:
            log.error(f"处理用户 {self.user_id} 拒绝暖贴时出错: {e}", exc_info=True)
            error_text = replace_emojis(WARMUP_MESSAGES["consent_error_response"])
            await interaction.response.edit_message(content=error_text, view=None)
