# -*- coding: utf-8 -*-

import discord
from discord.utils import format_dt
import logging
from typing import Optional

from src.chat.features.odysseia_coin.service.coin_service import coin_service

log = logging.getLogger(__name__)

ITEMS_PER_PAGE = 10


class JumpToPageModal(discord.ui.Modal):
    def __init__(self, view: "TransactionHistoryView"):
        super().__init__(title="跳转到页面")
        self.view = view
        self.page_input = discord.ui.TextInput(
            label=f"输入页码 (1 - {self.view.total_pages})",
            placeholder="例如: 5",
            required=True,
            min_length=1,
            max_length=len(str(self.view.total_pages)),
        )
        self.add_item(self.page_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        page_str = self.page_input.value
        if not page_str.isdigit():
            await interaction.followup.send("请输入一个有效的数字。", ephemeral=True)
            return

        page = int(page_str)
        if 1 <= page <= self.view.total_pages:
            self.view.current_page = page - 1
            await self.view.update_view()
        else:
            await interaction.followup.send(
                f"页码必须在 1 到 {self.view.total_pages} 之间。", ephemeral=True
            )


class TransactionHistoryView(discord.ui.View):
    """显示用户类脑币交易历史记录并提供分页的视图"""

    def __init__(
        self,
        original_interaction: discord.Interaction,
        target_user: discord.User,
        message: Optional[discord.Message] = None,
    ):
        super().__init__(timeout=300)
        self.original_interaction = original_interaction
        self.target_user = target_user
        self.message = message
        self.current_page = 0
        self.total_pages = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.response.send_message(
                "你不能操作这个视图。", ephemeral=True
            )
            return False
        return True

    async def start(self):
        """初始化并显示第一页"""
        if not self.message:
            self.message = await self.original_interaction.followup.send(
                "正在加载交易记录...", ephemeral=True
            )
        await self.update_view()

    async def update_view(self):
        """根据当前页面更新视图和Embed"""
        embed = await self._build_embed()
        self._update_buttons()
        if self.message:
            await self.message.edit(embed=embed, view=self)

    def _update_buttons(self):
        """更新分页按钮的状态"""
        self.clear_items()

        prev_button = discord.ui.Button(
            label="上一页",
            emoji="⬅️",
            style=discord.ButtonStyle.secondary,
            disabled=self.current_page == 0,
        )
        prev_button.callback = self.go_to_previous_page
        self.add_item(prev_button)

        next_button = discord.ui.Button(
            label="下一页",
            emoji="➡️",
            style=discord.ButtonStyle.secondary,
            disabled=self.current_page >= self.total_pages - 1,
        )
        next_button.callback = self.go_to_next_page
        self.add_item(next_button)

        jump_button = discord.ui.Button(
            label="跳转",
            emoji="🔢",
            style=discord.ButtonStyle.secondary,
            disabled=self.total_pages <= 1,
        )
        jump_button.callback = self.jump_to_page
        self.add_item(jump_button)

    async def jump_to_page(self, interaction: discord.Interaction):
        """显示一个模态窗口让用户输入页码"""
        if self.total_pages > 1:
            modal = JumpToPageModal(self)
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message(
                "只有一页，无需跳转。", ephemeral=True
            )

    async def _build_embed(self) -> discord.Embed:
        """构建显示交易记录的Embed"""
        total_transactions = await coin_service.get_transaction_count(
            self.target_user.id
        )
        self.total_pages = (total_transactions + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        offset = self.current_page * ITEMS_PER_PAGE
        transactions = await coin_service.get_transaction_history(
            self.target_user.id, limit=ITEMS_PER_PAGE, offset=offset
        )

        embed = discord.Embed(
            title=f"{self.target_user.display_name} 的类脑币流水",
            color=discord.Color.gold(),
        )

        if not transactions:
            embed.description = "该用户没有任何交易记录。"
            return embed

        description = ""
        for t in transactions:
            amount_str = f"+{t['amount']}" if t["amount"] > 0 else str(t["amount"])
            emoji = "🟢" if t["amount"] > 0 else "🔴"
            timestamp = t["timestamp"]
            # 确保 timestamp 是 datetime 对象
            if isinstance(timestamp, str):
                from datetime import datetime

                timestamp = datetime.fromisoformat(timestamp)

            description += f"{emoji} **{amount_str}** - {t['reason']} ({format_dt(timestamp, style='R')})\n"

        embed.description = description
        embed.set_footer(
            text=f"第 {self.current_page + 1} / {self.total_pages or 1} 页"
        )
        return embed

    async def go_to_previous_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_view()

    async def go_to_next_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_view()

    # async def go_back(self, interaction: discord.Interaction):
    #     """返回到之前的金币管理视图"""
    #     await interaction.response.defer()
    #     # 这里需要一种方式来重新显示 CoinManagementView
    #     # 这通常通过一个父控制器或在 CoinManagementView 中处理状态来实现
    #     # 暂时先发送一条消息
    #     await self.message.edit(content="返回功能待实现。", embed=None, view=None)
