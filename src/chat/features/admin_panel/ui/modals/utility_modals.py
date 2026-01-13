# -*- coding: utf-8 -*-

import discord

from ..typing import AnyDBView


# --- 跳转页面的模态窗口 ---
class JumpToPageModal(discord.ui.Modal):
    def __init__(self, db_view: AnyDBView):
        super().__init__(title="跳转到页面")
        self.db_view = db_view
        self.page_input = discord.ui.TextInput(
            label=f"输入页码 (1 - {self.db_view.total_pages})",
            placeholder="例如: 5",
            required=True,
            min_length=1,
            max_length=len(str(self.db_view.total_pages)),
        )
        self.add_item(self.page_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        page_str = self.page_input.value
        if not page_str.isdigit():
            await interaction.followup.send("请输入一个有效的数字。", ephemeral=True)
            return

        page = int(page_str)
        if 1 <= page <= self.db_view.total_pages:
            self.db_view.current_page = page - 1
            await self.db_view.update_view()
        else:
            await interaction.followup.send(
                f"页码必须在 1 到 {self.db_view.total_pages} 之间。", ephemeral=True
            )
