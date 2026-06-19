# -*- coding: utf-8 -*-

import discord
from discord import Interaction
from typing import Callable, Awaitable

MAX_REPLY_DELAY_SECONDS = 120
DEFAULT_REPLY_DELAY_SECONDS = 30


class ReplyDelayModal(discord.ui.Modal):
    """用于设置全局回复延迟（秒）的模态框。"""

    def __init__(
        self,
        current_delay: int,
        on_submit_callback: Callable[[Interaction, int], Awaitable[None]],
    ):
        super().__init__(title="设置回复延迟 (秒)")
        self.on_submit_callback = on_submit_callback

        self.delay_input = discord.ui.TextInput(
            label="回复延迟秒数 (0 = 关闭)",
            placeholder=f"输入 0 到 {MAX_REPLY_DELAY_SECONDS} 之间的整数",
            default=str(current_delay),
            required=True,
            min_length=1,
            max_length=3,
        )
        self.add_item(self.delay_input)

    async def on_submit(self, interaction: Interaction):
        raw = self.delay_input.value.strip()
        try:
            seconds = int(raw)
        except (ValueError, TypeError):
            await interaction.response.send_message(
                "❌ 请输入有效的整数。", ephemeral=True
            )
            return

        if seconds < 0 or seconds > MAX_REPLY_DELAY_SECONDS:
            await interaction.response.send_message(
                f"❌ 请输入 0 到 {MAX_REPLY_DELAY_SECONDS} 之间的整数。", ephemeral=True
            )
            return

        await self.on_submit_callback(interaction, seconds)
