import discord
from discord.ui import View, Button, Select
from discord import ButtonStyle, SelectOption, Interaction, TextChannel, CategoryChannel, app_commands
from typing import List, Optional, Dict, Any, Union, Coroutine, Callable

from src.chat.features.chat_settings.services.chat_settings_service import chat_settings_service
from src.chat.features.chat_settings.ui.channel_settings_modal import ChatSettingsModal
from src.chat.features.chat_settings.ui.warm_up_settings_view import WarmUpSettingsView
from src.chat.features.chat_settings.ui.components import PaginatedSelect

class ChatSettingsView(View):
    """聊天设置的主UI面板"""

    def __init__(self, interaction: Interaction):
        super().__init__(timeout=300)
        self.guild = interaction.guild
        self.service = chat_settings_service
        self.settings: Dict[str, Any] = {}
        self.message: Optional[discord.Message] = None
        self.category_paginator: Optional[PaginatedSelect] = None
        self.channel_paginator: Optional[PaginatedSelect] = None

    async def _initialize(self):
        """异步获取设置并构建UI。"""
        self.settings = await self.service.get_guild_settings(self.guild.id)
        self._create_paginators()
        self._create_view_items()

    @classmethod
    async def create(cls, interaction: Interaction):
        """工厂方法，用于异步创建和初始化View。"""
        view = cls(interaction)
        await view._initialize()
        return view

    def _create_paginators(self):
        """创建分页器实例。"""
        category_options = [SelectOption(label=c.name, value=str(c.id)) for c in sorted(self.guild.categories, key=lambda c: c.position)]
        self.category_paginator = PaginatedSelect(
            placeholder="选择一个分类进行设置...",
            custom_id_prefix="category_select",
            options=category_options,
            on_select_callback=self.on_entity_select,
            label_prefix="分类"
        )

        channel_options = [SelectOption(label=c.name, value=str(c.id)) for c in sorted(self.guild.text_channels, key=lambda c: c.position)]
        self.channel_paginator = PaginatedSelect(
            placeholder="选择一个频道进行设置...",
            custom_id_prefix="channel_select",
            options=channel_options,
            on_select_callback=self.on_entity_select,
            label_prefix="频道"
        )

    def _add_item_with_buttons(self, item, paginator: PaginatedSelect):
        """辅助函数，将一个项目（如下拉菜单）和它的翻页按钮作为一个整体添加。"""
        # Discord UI 按组件添加顺序自动布局，row参数可以建议布局位置
        # 我们将Select放在第2行，按钮放在第3行，以此类推
        item.row = 2 if 'category' in paginator.custom_id_prefix else 4
        self.add_item(item)
        
        buttons = paginator.get_buttons()
        for btn in buttons:
            btn.row = 2 if 'category' in paginator.custom_id_prefix else 4
            self.add_item(btn)


    def _create_view_items(self):
        """根据当前设置创建并添加所有UI组件。"""
        self.clear_items()

        # 全局开关 (第 0 行)
        global_chat_enabled = self.settings.get("global", {}).get("chat_enabled", True)
        self.add_item(Button(
            label=f"聊天总开关: {'开' if global_chat_enabled else '关'}",
            style=ButtonStyle.green if global_chat_enabled else ButtonStyle.red,
            custom_id="global_chat_toggle", row=0
        ))

        warm_up_enabled = self.settings.get("global", {}).get("warm_up_enabled", True)
        self.add_item(Button(
            label=f"暖贴功能: {'开' if warm_up_enabled else '关'}",
            style=ButtonStyle.green if warm_up_enabled else ButtonStyle.red,
            custom_id="warm_up_toggle", row=0
        ))

        self.add_item(Button(
            label="设置暖贴频道",
            style=ButtonStyle.secondary,
            custom_id="warm_up_settings", row=1
        ))

        # 分类选择器 (第 2 行)
        if self.category_paginator:
            self.add_item(self.category_paginator.create_select(row=2))

        # 频道选择器 (第 3 行)
        if self.channel_paginator:
            self.add_item(self.channel_paginator.create_select(row=3))

        # 两个分页器的按钮都放在第 4 行
        if self.category_paginator:
            for btn in self.category_paginator.get_buttons(row=4):
                self.add_item(btn)
        if self.channel_paginator:
            for btn in self.channel_paginator.get_buttons(row=4):
                self.add_item(btn)

    async def _update_view(self, interaction: Interaction):
        """通过编辑附加的消息来刷新视图。"""
        self.settings = await self.service.get_guild_settings(self.guild.id)
        self._create_view_items()
        await interaction.response.edit_message(content="设置已更新。", view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        custom_id = interaction.data.get("custom_id")
        
        if custom_id == "global_chat_toggle":
            await self.on_global_toggle(interaction)
        elif custom_id == "warm_up_toggle":
            await self.on_warm_up_toggle(interaction)
        elif custom_id == "warm_up_settings":
            await self.on_warm_up_settings(interaction)
        elif self.category_paginator and self.category_paginator.handle_pagination(custom_id):
            await self._update_view(interaction)
        elif self.channel_paginator and self.channel_paginator.handle_pagination(custom_id):
            await self._update_view(interaction)
        
        return True

    async def on_global_toggle(self, interaction: Interaction):
        current_state = self.settings.get("global", {}).get("chat_enabled", True)
        new_state = not current_state
        await self.service.db_manager.update_global_chat_config(self.guild.id, chat_enabled=new_state)
        await self._update_view(interaction)

    async def on_warm_up_toggle(self, interaction: Interaction):
        current_state = self.settings.get("global", {}).get("warm_up_enabled", True)
        new_state = not current_state
        await self.service.db_manager.update_global_chat_config(self.guild.id, warm_up_enabled=new_state)
        await self._update_view(interaction)

    async def on_warm_up_settings(self, interaction: Interaction):
        """切换到暖贴频道设置视图。"""
        await interaction.response.defer()
        warm_up_view = await WarmUpSettingsView.create(interaction, self.message)
        await interaction.edit_original_response(content="管理暖贴功能启用的论坛频道：", view=warm_up_view)
        self.stop()

    async def on_entity_select(self, interaction: Interaction):
        """统一处理频道和分类的选择事件。"""
        if not interaction.data['values'] or interaction.data['values'][0] == 'disabled':
            await interaction.response.defer()
            return

        entity_id = int(interaction.data['values'][0])
        entity = self.guild.get_channel(entity_id)
        if not entity:
            await interaction.response.send_message("找不到该项目。", ephemeral=True)
            return

        entity_type = "category" if isinstance(entity, CategoryChannel) else "channel"
        current_config = self.settings.get("channels", {}).get(entity_id, {})
        async def modal_callback(modal_interaction: Interaction, settings: Dict[str, Any]):
            await self._handle_modal_submit(modal_interaction, entity_id, entity_type, settings)
            # Modal 提交后刷新主视图
            if self.message:
                new_view = await ChatSettingsView.create(interaction)
                new_view.message = self.message
                await self.message.edit(content="设置已更新。", view=new_view)

        modal = ChatSettingsModal(
            title=f"编辑 {entity.name} 的设置",
            current_config=current_config,
            on_submit_callback=modal_callback,
            entity_name=entity.name
        )
        await interaction.response.send_modal(modal)

    async def _handle_modal_submit(self, interaction: Interaction, entity_id: int, entity_type: str, settings: Dict[str, Any]):
        """处理模态窗口提交的数据并保存。"""
        try:
            await self.service.set_entity_settings(
                guild_id=self.guild.id,
                entity_id=entity_id,
                entity_type=entity_type,
                is_chat_enabled=settings.get('is_chat_enabled'),
                cooldown_seconds=settings.get('cooldown_seconds'),
                cooldown_duration=settings.get('cooldown_duration'),
                cooldown_limit=settings.get('cooldown_limit')
            )

            entity = self.guild.get_channel(entity_id)
            entity_name = entity.name if entity else f"ID: {entity_id}"

            is_chat_enabled = settings.get('is_chat_enabled')
            enabled_str = "继承"
            if is_chat_enabled is True: enabled_str = "✅ 开启"
            if is_chat_enabled is False: enabled_str = "❌ 关闭"

            cooldown_seconds = settings.get('cooldown_seconds')
            cd_sec_str = f"{cooldown_seconds} 秒" if cooldown_seconds is not None else "继承"
            
            cooldown_duration = settings.get('cooldown_duration')
            cooldown_limit = settings.get('cooldown_limit')
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