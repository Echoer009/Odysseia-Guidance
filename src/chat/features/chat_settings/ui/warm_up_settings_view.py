# -*- coding: utf-8 -*-

import discord
from discord.ui import View
from discord import SelectOption, Interaction, ForumChannel
from typing import List, Optional

from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.features.chat_settings.ui.components import PaginatedSelect


class WarmUpSettingsView(View):
    """一个用于管理暖贴频道设置的UI视图。"""

    def __init__(self, interaction: Interaction, parent_view_message: discord.Message):
        super().__init__(timeout=300)
        self.guild = interaction.guild
        self.service = chat_settings_service
        self.parent_view_message = parent_view_message
        self.initial_selection: List[int] = []
        self.paginator: Optional[PaginatedSelect] = None

    async def _initialize(self):
        """异步获取设置并构建UI。"""
        self.initial_selection = await self.service.get_warm_up_channels(self.guild.id)
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

    def _create_paginator(self):
        """创建分页器实例。"""
        forum_channels = [c for c in self.guild.channels if isinstance(c, ForumChannel)]

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
            on_select_callback=self.on_selection,
            label_prefix="论坛",
        )

    def _create_view_items(self):
        """根据当前设置创建并添加所有UI组件。"""
        self.clear_items()

        if self.paginator:
            select = self.paginator.create_select(row=0)
            # 我们需要允许多选
            select.min_values = 0
            select.max_values = len(select.options) if select.options else 1
            self.add_item(select)

            # 将分页按钮添加到第 1 行
            for btn in self.paginator.get_buttons(row=1):
                self.add_item(btn)
        else:
            self.add_item(
                discord.ui.Button(label="服务器内没有论坛频道", disabled=True, row=0)
            )

        # 将返回按钮放到第 2 行
        back_button = discord.ui.Button(
            label="返回主菜单",
            style=discord.ButtonStyle.gray,
            custom_id="back_to_main",
            row=2,
        )
        back_button.callback = self.on_back
        self.add_item(back_button)

    async def _update_view(self, interaction: Interaction):
        """通过编辑附加的消息来刷新视图。"""
        self._create_view_items()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        custom_id = interaction.data.get("custom_id")

        if self.paginator and self.paginator.handle_pagination(custom_id):
            # 分页时，只重新构建项目并更新视图，不重新初始化
            self._create_view_items()
            await interaction.response.edit_message(view=self)
            return False  # 阻止 on_selection 被调用

        return True

    def _create_embed(self) -> discord.Embed:
        """创建一个显示当前已启用暖贴频道的Embed。"""
        embed = discord.Embed(title="暖贴频道设置", color=discord.Color.blue())

        if not self.initial_selection:
            embed.description = "目前没有频道启用暖贴功能。"
        else:
            channel_mentions = []
            for channel_id in self.initial_selection:
                channel = self.guild.get_channel(channel_id)
                if channel:
                    channel_mentions.append(channel.mention)
                else:
                    channel_mentions.append(f"`ID: {channel_id}` (已删除)")

            embed.description = "✅ 以下频道已启用暖贴功能：\n\n" + "\n".join(
                channel_mentions
            )

        embed.set_footer(text="在下面的下拉菜单中勾选或取消勾选以进行修改。")
        return embed

    async def on_selection(self, interaction: Interaction):
        """处理频道选择事件。"""
        await interaction.response.defer()

        # 获取当前页面所有被选中的频道的ID
        current_page_selected_ids = {int(v) for v in interaction.data.get("values", [])}

        # 获取当前页面所有的选项ID
        current_page_option_ids = {
            int(opt.value) for opt in self.paginator.pages[self.paginator.current_page]
        }

        # 找出在当前页面被取消选择的频道
        deselected_ids = current_page_option_ids - current_page_selected_ids

        # 从数据库中移除被取消选择的频道
        for channel_id in deselected_ids:
            if channel_id in self.initial_selection:
                await self.service.remove_warm_up_channel(self.guild.id, channel_id)

        # 添加新选择的频道到数据库
        for channel_id in current_page_selected_ids:
            if channel_id not in self.initial_selection:
                await self.service.add_warm_up_channel(self.guild.id, channel_id)

        await interaction.followup.send("暖贴频道设置已更新。", ephemeral=True)

        # 刷新视图以显示最新状态
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
        # 停止当前视图
        self.stop()
