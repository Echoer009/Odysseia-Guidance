# -*- coding: utf-8 -*-

import discord
from discord.ui import View, Select
from discord import SelectOption, Interaction, ForumChannel
from typing import List, Optional

from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.features.chat_settings.ui.components import PaginatedSelect


class WarmUpSettingsView(View):
    """一个用于管理暖贴频道设置的UI视图，支持跨服务器操作。"""

    def __init__(self, interaction: Interaction, parent_view_message: discord.Message):
        super().__init__(timeout=300)
        self.bot: discord.Client = interaction.client
        self.original_guild: Optional[discord.Guild] = interaction.guild
        self.selected_guild: Optional[discord.Guild] = interaction.guild
        self.service = chat_settings_service
        self.parent_view_message = parent_view_message
        self.initial_selection: List[int] = []
        self.paginator: Optional[PaginatedSelect] = None

    async def _initialize(self):
        """异步获取设置并构建UI。"""
        if not self.selected_guild:
            return
        self.initial_selection = await self.service.get_warm_up_channels(
            self.selected_guild.id
        )
        self._create_paginator()
        self._create_view_items()

    @classmethod
    async def create(
        cls, interaction: Interaction, parent_view_message: discord.Message
    ):
        """工厂方法，用于异步创建和初始化View。"""
        view = cls(interaction, parent_view_message)
        await view._initialize()
        return view

    def _get_guild_options(self) -> List[SelectOption]:
        """获取所有可用服务器的下拉选项。"""
        options = []
        for guild in sorted(self.bot.guilds, key=lambda g: g.name):
            is_current = (
                self.selected_guild is not None and guild.id == self.selected_guild.id
            )
            options.append(
                SelectOption(
                    label=guild.name,
                    value=str(guild.id),
                    description=f"ID: {guild.id}",
                    default=is_current,
                )
            )
        return options

    def _create_paginator(self):
        """创建分页器实例。"""
        if not self.selected_guild:
            return
        forum_channels = [
            c for c in self.selected_guild.channels if isinstance(c, ForumChannel)
        ]

        options = []
        for channel in sorted(forum_channels, key=lambda c: c.position):
            options.append(
                SelectOption(
                    label=channel.name,
                    value=str(channel.id),
                    default=channel.id in self.initial_selection,
                )
            )

        self.paginator = PaginatedSelect(
            placeholder="选择要开启暖贴功能的论坛频道...",
            custom_id_prefix="warm_up_select",
            options=options,
            on_select_callback=self._on_select_callback,
            label_prefix="论坛",
        )

    def _create_view_items(self):
        """根据当前设置创建并添加所有UI组件。"""
        self.clear_items()

        selected_guild_name = (
            self.selected_guild.name if self.selected_guild else "未知"
        )

        # 第 0 行：服务器选择器
        guild_options = self._get_guild_options()
        if guild_options:
            guild_select = Select(
                placeholder="选择要管理的服务器...",
                options=guild_options[:25],
                custom_id="warm_up_guild_select",
                row=0,
            )
            guild_select.callback = self.on_guild_select
            self.add_item(guild_select)

        # 第 1 行：论坛频道选择器
        if self.paginator:
            select = self.paginator.create_select(row=1)
            select.min_values = 0
            select.max_values = len(select.options) if select.options else 1
            self.add_item(select)

            # 将分页按钮添加到第 2 行
            for btn in self.paginator.get_buttons(row=2):
                self.add_item(btn)
        else:
            self.add_item(
                discord.ui.Button(
                    label=f"{selected_guild_name} 内没有论坛频道",
                    disabled=True,
                    row=1,
                )
            )

        # 将返回按钮放到第 3 行
        back_button = discord.ui.Button(
            label="返回主菜单",
            style=discord.ButtonStyle.gray,
            custom_id="back_to_main",
            row=3,
        )
        back_button.callback = self.on_back
        self.add_item(back_button)

    async def on_guild_select(self, interaction: Interaction):
        """处理服务器选择事件。"""
        if not interaction.data or "values" not in interaction.data:
            await interaction.response.defer()
            return

        selected_guild_id = int(interaction.data["values"][0])
        guild = self.bot.get_guild(selected_guild_id)
        if not guild:
            await interaction.response.send_message(
                "❌ 找不到该服务器，bot 可能已不在该服务器中。",
                ephemeral=True,
            )
            return

        self.selected_guild = guild
        await self._update_view(interaction)

    async def _update_view(self, interaction: Interaction):
        """通过编辑附加的消息来刷新视图。"""
        await self._initialize()
        embed = self._create_embed()
        self._create_view_items()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if not interaction.data:
            return True
        custom_id = interaction.data.get("custom_id")

        if self.paginator and custom_id and self.paginator.handle_pagination(custom_id):
            self._create_view_items()
            await interaction.response.edit_message(view=self)
            return False

        return True

    def _create_embed(self) -> discord.Embed:
        """创建一个显示当前已启用暖贴频道的Embed。"""
        selected_guild_name = (
            self.selected_guild.name if self.selected_guild else "未知"
        )
        embed = discord.Embed(title="暖贴频道设置", color=discord.Color.blue())
        embed.description = (
            f"当前服务器: **{selected_guild_name}**\n在此管理服务器内论坛频道的暖贴功能。"
        )

        if not self.initial_selection:
            embed.add_field(
                name="已启用频道",
                value="目前没有频道启用暖贴功能。",
                inline=False,
            )
        else:
            channel_mentions = []
            if not self.selected_guild:
                return embed
            for channel_id in self.initial_selection:
                channel = self.selected_guild.get_channel(channel_id)
                if channel:
                    channel_mentions.append(channel.mention)
                else:
                    channel_mentions.append(f"`ID: {channel_id}` (已删除)")

            embed.add_field(
                name="已启用频道",
                value="\n".join(channel_mentions),
                inline=False,
            )

        embed.set_footer(text="先选择服务器，再在下拉菜单中勾选或取消勾选论坛频道。")
        return embed

    async def _on_select_callback(self, interaction: Interaction, values: List[str]):
        """PaginatedSelect 回调包装器，符合 (Interaction, List[str]) 签名。"""
        await self.on_selection(interaction, values)

    async def on_selection(self, interaction: Interaction, values: List[str]):
        """处理频道选择事件。"""
        await interaction.response.defer()

        current_page_selected_ids = {int(v) for v in values}

        if not self.paginator:
            return
        current_page_option_ids = {
            int(opt.value) for opt in self.paginator.pages[self.paginator.current_page]
        }

        deselected_ids = current_page_option_ids - current_page_selected_ids

        if not self.selected_guild:
            return
        for channel_id in deselected_ids:
            if channel_id in self.initial_selection:
                await self.service.remove_warm_up_channel(
                    self.selected_guild.id, channel_id
                )

        for channel_id in current_page_selected_ids:
            if channel_id not in self.initial_selection:
                await self.service.add_warm_up_channel(
                    self.selected_guild.id, channel_id
                )

        await interaction.followup.send("暖贴频道设置已更新。", ephemeral=True)

        await self._initialize()
        self._create_view_items()
        embed = self._create_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    async def on_back(self, interaction: Interaction):
        """返回主设置菜单。"""
        from src.chat.features.chat_settings.ui.chat_settings_view import (
            ChatSettingsView,
        )

        await interaction.response.defer()
        main_view = await ChatSettingsView.create(interaction)
        await self.parent_view_message.edit(
            content="在此管理服务器的聊天设置：", view=main_view, embed=None
        )
        self.stop()
