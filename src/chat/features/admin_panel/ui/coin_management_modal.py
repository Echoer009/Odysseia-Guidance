# -*- coding: utf-8 -*-
import discord
from discord.ui import Modal, TextInput
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.chat.features.admin_panel.ui.coin_management_view import CoinManagementView


class UserSearchModal(Modal, title="搜索用户"):
    user_id_input = TextInput(
        label="用户ID",
        placeholder="请输入用户的数字ID...",
        style=discord.TextStyle.short,
        required=True,
        min_length=17,
        max_length=20,
    )

    def __init__(self, parent_view: "CoinManagementView"):
        super().__init__(timeout=300)
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            user_id = int(self.user_id_input.value)
            await self.parent_view.search_user(user_id, interaction)
        except ValueError:
            await interaction.followup.send(
                "❌ 无效的用户ID，请输入纯数字。", ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(f"❌ 搜索时发生错误: {e}", ephemeral=True)


class CoinBalanceModal(Modal, title="修改用户余额"):
    new_balance_input = TextInput(
        label="新的余额",
        placeholder="请输入新的类脑币总额...",
        style=discord.TextStyle.short,
        required=True,
    )

    def __init__(self, parent_view: "CoinManagementView"):
        super().__init__(timeout=300)
        self.parent_view = parent_view
        # Set default value to current balance
        self.new_balance_input.default = str(parent_view.current_balance)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_balance = int(self.new_balance_input.value)
            if new_balance < 0:
                await interaction.response.send_message(
                    "❌ 余额不能为负数。", ephemeral=True
                )
                return

            await self.parent_view.set_balance(new_balance, interaction)

        except ValueError:
            await interaction.response.send_message(
                "❌ 无效的金额，请输入纯数字。", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 设置余额时发生错误: {e}", ephemeral=True
            )
