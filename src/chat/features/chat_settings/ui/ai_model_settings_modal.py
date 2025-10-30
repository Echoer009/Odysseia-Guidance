import discord
from discord import Interaction
from discord.ui import TextInput
from typing import Callable, Awaitable, Dict, Any, List


class AIModelSettingsModal(discord.ui.Modal):
    """一个用于选择聊天AI模型的模态框。"""

    def __init__(
        self,
        *,
        title: str,
        current_model: str,
        available_models: List[str],
        on_submit_callback: Callable[[Interaction, Dict[str, Any]], Awaitable[None]],
    ):
        super().__init__(title=title)
        self.on_submit_callback = on_submit_callback

        placeholder_text = f"可用模型: {', '.join(available_models)}"
        if len(placeholder_text) > 100:
            placeholder_text = placeholder_text[:97] + "..."

        self.model_input = TextInput(
            label="输入AI模型名称",
            placeholder=placeholder_text,
            default=current_model,
            custom_id="ai_model_input",
        )
        self.add_item(self.model_input)

    async def on_submit(self, interaction: Interaction):
        entered_model = self.model_input.value.strip()
        settings = {"ai_model": entered_model}
        await self.on_submit_callback(interaction, settings)
