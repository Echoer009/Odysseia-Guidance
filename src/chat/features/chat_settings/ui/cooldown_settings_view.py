# -*- coding: utf-8 -*-

import discord
from discord.ui import View, Button
from discord import SelectOption, Interaction, CategoryChannel
from typing import List, Optional

from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.features.chat_settings.ui.components import PaginatedSelect
from src.chat.features.chat_settings.ui.channel_settings_modal import ChatSettingsModal


class CooldownSettingsView(View):
    """一个用于管理频道和分类冷却设置的UI视图。"""

    def __init__(self, interaction: Interaction, parent_view_message: discord.Message):
        super().__init__(timeout=300)
        self.guild = interaction.guild
        self.service = chat_settings_service
        self.parent_view_message = parent_view_message
        self.settings: dict = {}
        self.category_paginator: Optional[PaginatedSelect] = None
        self.channel_paginator: Optional[PaginatedSelect] = None

    async def _initialize(self):
        """异步获取设置并构建UI。"""
        if not self.guild:
            return
        self.settings = await self.service.get_guild_settings(self.guild.id)
        self._create_paginators()
        self._create_view_items()

    @classmethod
    async def create(
        cls, interaction: Interaction, parent_view_message: discord.Message
    ):
        """工厂方法，用于异步创建和初始化View。"""
        view = cls(interaction, parent_view_message)
        await view._initialize()
        return view

    def _create_paginators(self):
        """创建分页器实例。"""
        if not self.guild:
            return
        category_options = [
            SelectOption(label=c.name, value=str(c.id))
            for c in sorted(self.guild.categories, key=lambda c: c.position)
        ]
        self.category_paginator = PaginatedSelect(
            placeholder="选择一个分类进行设置...",
            custom_id_prefix="category_select",
            options=category_options,
            on_select_callback=self.on_entity_select,
            label_prefix="分类",
        )

        channel_options = [
            SelectOption(label=c.name, value=str(c.id))
            for c in sorted(self.guild.text_channels, key=lambda c: c.position)
        ]
        self.channel_paginator = PaginatedSelect(
            placeholder="选择一个频道进行设置...",
            custom_id_prefix="channel_select",
            options=channel_options,
            on_select_callback=self.on_entity_select,
            label_prefix="频道",
        )

    def _create_view_items(self):
        """根据当前设置创建并添加所有UI组件。"""
        self.clear_items()

        # 标题说明
        embed = discord.Embed(
            title="⏱️ 冷却设置",
            description="在此管理服务器内分类和频道的聊天冷却设置。",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="💡 提示",
            value="点击下方的分类或频道下拉菜单，选择要设置的项目。\n支持固定冷却和频率限制两种模式。",
            inline=False,
        )

        # 分类选择器 (第 0 行)
        if self.category_paginator:
            self.add_item(self.category_paginator.create_select(row=0))
            # 添加分类翻页按钮 (第 1 行)
            for btn in self.category_paginator.get_buttons(row=1):
                self.add_item(btn)

        # 频道选择器 (第 2 行)
        if self.channel_paginator:
            self.add_item(self.channel_paginator.create_select(row=2))
            # 添加频道翻页按钮 (第 3 行)
            for btn in self.channel_paginator.get_buttons(row=3):
                self.add_item(btn)

        # 返回按钮 (第 4 行)
        back_button = Button(
            label="返回主菜单",
            style=discord.ButtonStyle.gray,
            custom_id="back_to_main",
            row=4,
        )
        back_button.callback = self.on_back
        self.add_item(back_button)

        return embed

    async def _update_view(self, interaction: Interaction):
        """通过编辑附加的消息来刷新视图。"""
        await self._initialize()
        embed = self._create_view_items()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        custom_id = interaction.data.get("custom_id") if interaction.data else None

        # 处理分类分页
        if (
            self.category_paginator
            and custom_id
            and self.category_paginator.handle_pagination(custom_id)
        ):
            self._create_view_items()
            embed = self._create_view_items()
            await interaction.response.edit_message(embed=embed, view=self)
            return False

        # 处理频道分页
        if (
            self.channel_paginator
            and custom_id
            and self.channel_paginator.handle_pagination(custom_id)
        ):
            self._create_view_items()
            embed = self._create_view_items()
            await interaction.response.edit_message(embed=embed, view=self)
            return False

        return True

    async def on_entity_select(self, interaction: Interaction, values: List[str]):
        """统一处理频道和分类的选择事件。"""
        if not values or values[0] == "disabled":
            await interaction.response.defer()
            return

        entity_id = int(values[0])
        if not self.guild:
            await interaction.response.defer()
            return

        entity = self.guild.get_channel(entity_id)
        if not entity:
            await interaction.response.send_message("找不到该项目。", ephemeral=True)
            return

        entity_type = "category" if isinstance(entity, CategoryChannel) else "channel"
        current_config = self.settings.get("channels", {}).get(entity_id, {})

        async def modal_callback(modal_interaction: Interaction, settings: dict):
            await self._handle_modal_submit(
                modal_interaction, entity_id, entity_type, settings
            )
            # Modal 提交后刷新当前视图
            await self._initialize()
            embed = self._create_view_items()
            await interaction.edit_original_response(embed=embed, view=self)

        modal = ChatSettingsModal(
            title=f"编辑 {entity.name} 的设置",
            current_config=current_config,
            on_submit_callback=modal_callback,
            entity_name=entity.name,
        )
        await interaction.response.send_modal(modal)

    async def _handle_modal_submit(
        self,
        interaction: Interaction,
        entity_id: int,
        entity_type: str,
        settings: dict,
    ):
        """处理模态窗口提交的数据并保存。"""
        try:
            if not self.guild:
                await interaction.followup.send("❌ 服务器信息丢失。", ephemeral=True)
                return
            await self.service.set_entity_settings(
                guild_id=self.guild.id,
                entity_id=entity_id,
                entity_type=entity_type,
                is_chat_enabled=settings.get("is_chat_enabled"),
                cooldown_seconds=settings.get("cooldown_seconds"),
                cooldown_duration=settings.get("cooldown_duration"),
                cooldown_limit=settings.get("cooldown_limit"),
            )

            if not self.guild:
                entity_name = f"ID: {entity_id}"
            else:
                entity = self.guild.get_channel(entity_id)
                entity_name = entity.name if entity else f"ID: {entity_id}"

            is_chat_enabled = settings.get("is_chat_enabled")
            enabled_str = "继承"
            if is_chat_enabled is True:
                enabled_str = "✅ 开启"
            if is_chat_enabled is False:
                enabled_str = "❌ 关闭"

            cooldown_seconds = settings.get("cooldown_seconds")
            cd_sec_str = (
                f"{cooldown_seconds} 秒" if cooldown_seconds is not None else "继承"
            )

            cooldown_duration = settings.get("cooldown_duration")
            cooldown_limit = settings.get("cooldown_limit")
            freq_str = "继承"
            if cooldown_duration is not None and cooldown_limit is not None:
                freq_str = f"{cooldown_duration} 秒内最多 {cooldown_limit} 次"

            feedback = (
                f"✅ 已成功为 **{entity_name}** ({entity_type}) 更新设置。\n"
                f"🔹 **聊天总开关**: {enabled_str}\n"
                f"🔹 **固定冷却(秒)**: {cd_sec_str}\n"
                f"🔹 **频率限制**: {freq_str}"
            )

            # 确保交互未被响应
            if not interaction.response.is_done():
                await interaction.response.defer()
            await interaction.followup.send(feedback, ephemeral=True)

        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.defer()
            await interaction.followup.send(f"❌ 保存设置时出错: {e}", ephemeral=True)

    async def on_back(self, interaction: Interaction):
        """返回主设置菜单。"""
        # 延迟导入以避免循环导入
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
