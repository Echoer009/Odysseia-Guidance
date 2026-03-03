import discord
from discord.ui import View, Button, Select
from discord import (
    ButtonStyle,
    SelectOption,
    Interaction,
    CategoryChannel,
)
from typing import List, Optional, Dict, Any

from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.chat.features.chat_settings.ui.channel_settings_modal import ChatSettingsModal
from src.database.services.token_usage_service import token_usage_service
from src.database.database import AsyncSessionLocal
from src.database.models import TokenUsage
from datetime import datetime
from src.chat.features.chat_settings.ui.warm_up_settings_view import WarmUpSettingsView
from src.chat.features.chat_settings.ui.components import PaginatedSelect
from src.chat.services.event_service import event_service
from src.chat.features.chat_settings.ui.ai_model_settings_modal import (
    AIModelSettingsModal,
)


class ChatSettingsView(View):
    """聊天设置的主UI面板"""

    def __init__(self, interaction: Interaction):
        super().__init__(timeout=300)
        self.guild = interaction.guild
        self.service = chat_settings_service
        self.settings: Dict[str, Any] = {}
        self.model_usage_counts: Dict[str, int] = {}
        self.message: Optional[discord.Message] = None
        self.category_paginator: Optional[PaginatedSelect] = None
        self.channel_paginator: Optional[PaginatedSelect] = None
        self.factions: Optional[List[Dict[str, Any]]] = None
        self.selected_faction: Optional[str] = None
        self.token_usage: Optional[TokenUsage] = None

    async def _initialize(self):
        """异步获取设置并构建UI。"""
        if not self.guild:
            return
        self.settings = await self.service.get_guild_settings(self.guild.id)
        self.model_usage_counts = await self.service.get_model_usage_counts()
        async with AsyncSessionLocal() as session:
            self.token_usage = await token_usage_service.get_token_usage(
                session, datetime.utcnow().date()
            )
        self.factions = event_service.get_event_factions()
        self.selected_faction = event_service.get_selected_faction()
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

    def _add_item_with_buttons(self, item, paginator: PaginatedSelect):
        """辅助函数，将一个项目（如下拉菜单）和它的翻页按钮作为一个整体添加。"""
        # Discord UI 按组件添加顺序自动布局，row参数可以建议布局位置
        # 我们将Select放在第2行，按钮放在第3行，以此类推
        item.row = 2 if "category" in paginator.custom_id_prefix else 4
        self.add_item(item)

        buttons = paginator.get_buttons()
        for btn in buttons:
            btn.row = 2 if "category" in paginator.custom_id_prefix else 4
            self.add_item(btn)

    def _create_view_items(self):
        """根据当前设置创建并添加所有UI组件。"""
        self.clear_items()

        # 全局开关 (第 0 行)
        global_chat_enabled = self.settings.get("global", {}).get("chat_enabled", True)
        self.add_item(
            Button(
                label=f"聊天总开关: {'开' if global_chat_enabled else '关'}",
                style=ButtonStyle.green if global_chat_enabled else ButtonStyle.red,
                custom_id="global_chat_toggle",
                row=0,
            )
        )

        warm_up_enabled = self.settings.get("global", {}).get("warm_up_enabled", True)
        self.add_item(
            Button(
                label=f"暖贴功能: {'开' if warm_up_enabled else '关'}",
                style=ButtonStyle.green if warm_up_enabled else ButtonStyle.red,
                custom_id="warm_up_toggle",
                row=0,
            )
        )

        api_fallback_enabled = self.settings.get("global", {}).get(
            "api_fallback_enabled", True
        )
        self.add_item(
            Button(
                label=f"API回退: {'开' if api_fallback_enabled else '关'}",
                style=ButtonStyle.green if api_fallback_enabled else ButtonStyle.red,
                custom_id="api_fallback_toggle",
                row=0,
            )
        )

        self.add_item(
            Button(
                label="设置暖贴频道",
                style=ButtonStyle.secondary,
                custom_id="warm_up_settings",
                row=4,
            )
        )

        self.add_item(
            Button(
                label="更换AI模型",
                style=ButtonStyle.secondary,
                custom_id="ai_model_settings",
                row=4,
            )
        )

        self.add_item(
            Button(
                label="今日Token",
                style=ButtonStyle.secondary,
                custom_id="show_token_usage",
                row=4,
            )
        )

        # 活动派系选择器 (第 1 行)
        if self.factions:
            faction_options = [
                SelectOption(
                    label="无 / 默认",
                    value="_default",
                    default=self.selected_faction is None,
                )
            ]
            for faction in self.factions:
                is_selected = self.selected_faction == faction["faction_id"]
                faction_options.append(
                    SelectOption(
                        label=f"{faction['faction_name']} ({faction['faction_id']})",
                        value=faction["faction_id"],
                        default=is_selected,
                    )
                )

            faction_select = Select(
                placeholder="设置当前活动派系人设...",
                options=faction_options,
                custom_id="faction_select",
                row=1,
            )
            faction_select.callback = self.on_faction_select
            self.add_item(faction_select)

        # 分类选择器 (第 2 行)
        if self.category_paginator:
            self.add_item(self.category_paginator.create_select(row=2))

        # 频道选择器 (第 3 行)
        if self.channel_paginator:
            self.add_item(self.channel_paginator.create_select(row=3))

        # 分页器按钮暂时不显示，因为UI空间不足
        # TODO: 未来可以考虑重新设计UI布局以支持分页按钮
        # if self.category_paginator:
        #     for btn in self.category_paginator.get_buttons(row=4):
        #         self.add_item(btn)
        # if self.channel_paginator:
        #     for btn in self.channel_paginator.get_buttons(row=4):
        #         self.add_item(btn)

    async def _update_view(self, interaction: Interaction):
        """通过编辑附加的消息来刷新视图。"""
        await self._initialize()  # 重新获取所有数据，包括派系
        await interaction.response.edit_message(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        custom_id = interaction.data.get("custom_id") if interaction.data else None

        if custom_id == "global_chat_toggle":
            await self.on_global_toggle(interaction)
        elif custom_id == "warm_up_toggle":
            await self.on_warm_up_toggle(interaction)
        elif custom_id == "api_fallback_toggle":
            await self.on_api_fallback_toggle(interaction)
        elif custom_id == "warm_up_settings":
            await self.on_warm_up_settings(interaction)
        elif (
            self.category_paginator
            and custom_id
            and self.category_paginator.handle_pagination(custom_id)
        ):
            await self._update_view(interaction)
        elif (
            self.channel_paginator
            and custom_id
            and self.channel_paginator.handle_pagination(custom_id)
        ):
            await self._update_view(interaction)
        elif custom_id == "ai_model_settings":
            await self.on_ai_model_settings(interaction)
        elif custom_id == "show_token_usage":
            await self.on_show_token_usage(interaction)

        return True

    async def on_global_toggle(self, interaction: Interaction):
        current_state = self.settings.get("global", {}).get("chat_enabled", True)
        new_state = not current_state
        if not self.guild:
            return
        await self.service.db_manager.update_global_chat_config(
            self.guild.id, chat_enabled=new_state
        )
        await self._update_view(interaction)

    async def on_warm_up_toggle(self, interaction: Interaction):
        current_state = self.settings.get("global", {}).get("warm_up_enabled", True)
        new_state = not current_state
        if not self.guild:
            return
        await self.service.db_manager.update_global_chat_config(
            self.guild.id, warm_up_enabled=new_state
        )
        await self._update_view(interaction)

    async def on_api_fallback_toggle(self, interaction: Interaction):
        current_state = self.settings.get("global", {}).get(
            "api_fallback_enabled", True
        )
        new_state = not current_state
        if not self.guild:
            return
        await self.service.db_manager.update_global_chat_config(
            self.guild.id, api_fallback_enabled=new_state
        )
        await self._update_view(interaction)

    async def on_warm_up_settings(self, interaction: Interaction):
        """切换到暖贴频道设置视图。"""
        if not self.message:
            await interaction.response.send_message(
                "无法找到原始消息，请重新打开设置面板。", ephemeral=True
            )
            return

        await interaction.response.defer()
        warm_up_view = await WarmUpSettingsView.create(interaction, self.message)
        await interaction.edit_original_response(
            content="管理暖贴功能启用的论坛频道：", view=warm_up_view
        )
        self.stop()

    async def on_faction_select(self, interaction: Interaction):
        """处理派系选择事件。"""
        if not interaction.data or "values" not in interaction.data:
            await interaction.response.defer()
            return

        selected_faction_id = interaction.data["values"][0]

        if selected_faction_id == "_default":
            event_service.set_selected_faction(None)
        else:
            event_service.set_selected_faction(selected_faction_id)

        await self._update_view(interaction)

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

        async def modal_callback(
            modal_interaction: Interaction, settings: Dict[str, Any]
        ):
            await self._handle_modal_submit(
                modal_interaction, entity_id, entity_type, settings
            )
            # Modal 提交后刷新主视图
            if self.message:
                new_view = await ChatSettingsView.create(interaction)
                new_view.message = self.message
                await self.message.edit(content="设置已更新。", view=new_view)

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
        settings: Dict[str, Any],
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

    async def on_ai_model_settings(self, interaction: Interaction):
        """打开AI模型设置模态框。"""
        current_model = await self.service.get_current_ai_model()
        available_models = self.service.get_available_ai_models()

        async def modal_callback(
            modal_interaction: Interaction, settings: Dict[str, Any]
        ):
            new_model = settings.get("ai_model")
            if new_model:
                await self.service.set_ai_model(new_model)
                await modal_interaction.response.send_message(
                    f"✅ 已成功将AI模型更换为: **{new_model}**", ephemeral=True
                )
            else:
                await modal_interaction.response.send_message(
                    "❌ 没有选择任何模型。", ephemeral=True
                )

        modal = AIModelSettingsModal(
            title="更换全局AI模型",
            current_model=current_model,
            available_models=available_models,
            on_submit_callback=modal_callback,
        )
        await interaction.response.send_modal(modal)

    async def on_show_token_usage(self, interaction: Interaction):
        """显示今天的 Token 使用情况。"""
        if not self.token_usage:
            await interaction.response.send_message(
                "今天还没有 Token 使用记录。", ephemeral=True
            )
            return

        input_tokens = self.token_usage.input_tokens or 0
        output_tokens = self.token_usage.output_tokens or 0
        total_tokens = self.token_usage.total_tokens or 0
        call_count = self.token_usage.call_count or 0
        average_per_call = total_tokens // call_count if call_count > 0 else 0
        usage_date = self.token_usage.date.strftime("%Y-%m-%d")

        embed = discord.Embed(
            title=f"📊 今日 Token 統計 ({usage_date})",
            color=discord.Color.blue(),
        )
        embed.add_field(name="📥 Input", value=f"{input_tokens:,}", inline=False)
        embed.add_field(name="📤 Output", value=f"{output_tokens:,}", inline=False)
        embed.add_field(name="📈 Total", value=f"{total_tokens:,}", inline=False)
        embed.add_field(name="🔢 呼叫次數", value=str(call_count), inline=False)
        embed.add_field(name="📊 平均每次", value=f"{average_per_call:,}", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)
