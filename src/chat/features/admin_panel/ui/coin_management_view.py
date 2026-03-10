# -*- coding: utf-8 -*-
import discord
from discord.ui import View, Button
from typing import cast

from src import config as root_config
from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.admin_panel.ui.coin_management_modal import (
    UserSearchModal,
    CoinBalanceModal,
)
from src.chat.features.odysseia_coin.ui.transaction_history_ui import (
    TransactionHistoryView,
)


class CoinManagementView(View):
    """
    类脑币管理视图
    """

    def __init__(
        self, main_interaction: discord.Interaction, original_message: discord.Message
    ):
        super().__init__(timeout=300)
        self.main_interaction = main_interaction
        self.guild = main_interaction.guild
        self.message = original_message
        self.target_user_id: int | None = None
        self.target_user: discord.User | None = None
        self.current_balance: int = 0

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                button = cast(discord.ui.Button, item)
                button.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass

    async def update_view(self):
        """更新视图和Embed"""
        embed = await self.get_embed()
        self.update_buttons()
        await self.message.edit(embed=embed, view=self)

    def update_buttons(self):
        """根据当前状态更新按钮的可见性和禁用状态"""
        self.clear_items()

        # 添加返回数据库浏览器主界面的按钮
        from src.chat.features.admin_panel.ui.views.db_management_view import (
            DBManagementView,
        )

        back_button = Button(
            label="返回数据库浏览器", style=discord.ButtonStyle.grey, emoji="⬅️", row=4
        )

        async def back_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            view = DBManagementView(self.main_interaction.user.id)
            view.message = self.message
            await view.update_view()

        back_button.callback = back_callback
        self.add_item(back_button)

        # 添加搜索按钮
        search_button = Button(
            label="搜索用户", style=discord.ButtonStyle.primary, emoji="🔍", row=0
        )

        async def search_callback(interaction: discord.Interaction):
            search_modal = UserSearchModal(self)
            await interaction.response.send_modal(search_modal)

        search_button.callback = search_callback
        self.add_item(search_button)

        # 如果已找到用户，添加设置余额按钮
        if self.target_user_id:
            set_balance_button = Button(
                label="修改余额", style=discord.ButtonStyle.success, emoji="💰", row=0
            )

            async def set_balance_callback(interaction: discord.Interaction):
                balance_modal = CoinBalanceModal(self)
                await interaction.response.send_modal(balance_modal)

            set_balance_button.callback = set_balance_callback
            self.add_item(set_balance_button)

            view_transactions_button = Button(
                label="查看流水", style=discord.ButtonStyle.secondary, emoji="📜", row=1
            )

            async def view_transactions_callback(interaction: discord.Interaction):
                if not self.target_user:
                    await interaction.response.send_message(
                        "无法获取用户信息以查看流水。", ephemeral=True
                    )
                    return

                await interaction.response.defer()
                transaction_view = TransactionHistoryView(
                    interaction, self.target_user, self.message
                )
                await transaction_view.start()

            view_transactions_button.callback = view_transactions_callback
            self.add_item(view_transactions_button)

    async def get_embed(self) -> discord.Embed:
        """生成类脑币管理的 Embed"""
        if self.target_user:
            description = f"正在管理用户 **{self.target_user.display_name}** (`{self.target_user_id}`) 的类脑币。"
            color = root_config.EMBED_COLOR_SUCCESS
        else:
            description = "请使用下方按钮搜索您想管理的用户ID。"
            color = root_config.EMBED_COLOR_INFO

        embed = discord.Embed(
            title="🪙 类脑币管理", description=description, color=color
        )

        if self.target_user or self.target_user_id:
            embed.add_field(
                name="当前余额",
                value=f"**{self.current_balance}** 类脑币",
                inline=False,
            )
        if self.target_user_id and not self.target_user:
            if embed.description:
                embed.description += f"\n\n⚠️ 未能在服务器内找到ID为 `{self.target_user_id}` 的用户，但仍可操作数据库。"

        embed.set_footer(text="Odysseia Admin Panel")
        return embed

    async def search_user(self, user_id: int, interaction: discord.Interaction):
        """根据ID搜索用户并更新视图"""
        await interaction.followup.send(f"正在搜索用户 `{user_id}`...", ephemeral=True)
        self.target_user_id = user_id
        self.target_user = None

        try:
            if self.guild:
                member = await self.guild.fetch_member(user_id)
                self.target_user = cast(discord.User, member)
        except discord.NotFound:
            try:
                user = await self.main_interaction.client.fetch_user(user_id)
                self.target_user = user
            except discord.NotFound:
                await interaction.followup.send(
                    f"⚠️ 警告：在Discord中找不到ID为 `{user_id}` 的用户。但如果数据库中存在该用户的记录，您仍然可以进行操作。",
                    ephemeral=True,
                )

        self.current_balance = await coin_service.get_balance(user_id)
        await self.update_view()

    async def set_balance(self, new_balance: int, interaction: discord.Interaction):
        """设置用户的余额"""
        if self.target_user_id is None:
            await interaction.response.send_message(
                "错误：没有指定用户。", ephemeral=True
            )
            return

        current_balance = await coin_service.get_balance(self.target_user_id)
        diff = new_balance - current_balance

        try:
            if diff > 0:
                await coin_service.add_coins(
                    self.target_user_id, diff, f"管理员 {interaction.user.id} 修改"
                )
            elif diff < 0:
                await coin_service.remove_coins(
                    self.target_user_id, -diff, f"管理员 {interaction.user.id} 修改"
                )

            self.current_balance = new_balance

            user_display = (
                self.target_user.display_name
                if self.target_user
                else f"用户ID {self.target_user_id}"
            )

            await interaction.response.send_message(
                f"✅ 成功将 **{user_display}** 的余额修改为 **{new_balance}**。",
                ephemeral=True,
            )
            await self.update_view()
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 修改余额时发生错误: {e}", ephemeral=True
            )
