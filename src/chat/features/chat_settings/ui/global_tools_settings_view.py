# -*- coding: utf-8 -*-
"""
全局工具设置视图

允许管理员通过 Discord UI 控制工具的全局启用/禁用状态和系统保留状态。
"""

import discord
from discord.ui import View, Button, Select
from discord import (
    ButtonStyle,
    SelectOption,
    Interaction,
)
from typing import Optional, Dict, List, Any, TYPE_CHECKING

from src.chat.features.tools.services.global_tool_settings_service import (
    global_tool_settings_service,
)

if TYPE_CHECKING:
    from src.chat.features.chat_settings.ui.chat_settings_view import ChatSettingsView


class GlobalToolsSettingsView(View):
    """全局工具设置面板"""

    def __init__(self, interaction: Interaction, parent_message: discord.Message):
        super().__init__(timeout=300)
        self.guild = interaction.guild
        self.parent_message = parent_message
        self.tools_by_category: Dict[str, List[Dict[str, Any]]] = {}
        self.selected_category: Optional[str] = None
        self.message: Optional[discord.Message] = None

    async def _initialize(self):
        """异步初始化"""
        self.tools_by_category = (
            await global_tool_settings_service.get_tools_by_category()
        )
        self._create_view_items()

    @classmethod
    async def create(
        cls, interaction: Interaction, parent_message: discord.Message
    ) -> "GlobalToolsSettingsView":
        """工厂方法，用于异步创建和初始化 View"""
        view = cls(interaction, parent_message)
        await view._initialize()
        return view

    def _create_view_items(self):
        """创建 UI 组件"""
        self.clear_items()

        # 类别选择下拉框
        categories = list(self.tools_by_category.keys())
        if categories:
            options = []
            for category in categories:
                tool_count = len(self.tools_by_category[category])
                is_selected = self.selected_category == category
                options.append(
                    SelectOption(
                        label=f"{category} ({tool_count})",
                        value=category,
                        default=is_selected,
                    )
                )

            category_select = Select(
                placeholder="选择工具类别...",
                options=options[:25],  # Discord 限制最多 25 个选项
                custom_id="category_select",
                row=0,
            )
            category_select.callback = self.on_category_select
            self.add_item(category_select)

        # 如果选择了类别，显示该类别下的工具
        if self.selected_category and self.selected_category in self.tools_by_category:
            tools = self.tools_by_category[self.selected_category]
            # 显示工具按钮（最多 10 个工具，每个工具 2 个按钮）
            # 按钮 1: 全局禁用/启用 (row 1-2)
            # 按钮 2: 系统保留/取消保留 (row 3-4)
            for i, tool in enumerate(tools[:10]):
                # 全局状态按钮（第一行和第二行）
                disabled_label = f"{'🚫' if tool['is_disabled'] else '✅'} {tool['display_name'][:12]}"
                disabled_button = Button(
                    label=disabled_label,
                    style=ButtonStyle.danger
                    if tool["is_disabled"]
                    else ButtonStyle.success,
                    custom_id=f"toggle_disabled_{tool['name']}",
                    row=1 + (i // 5),
                )
                disabled_button.callback = self._make_toggle_disabled_callback(
                    tool["name"]
                )
                self.add_item(disabled_button)

                # 系统保留按钮（第三行和第四行）
                protected_label = f"{'🔒' if tool['is_protected'] else '🔓'} {tool['display_name'][:12]}"
                protected_button = Button(
                    label=protected_label,
                    style=ButtonStyle.primary
                    if tool["is_protected"]
                    else ButtonStyle.secondary,
                    custom_id=f"toggle_protected_{tool['name']}",
                    row=3 + (i // 5),
                )
                protected_button.callback = self._make_toggle_protected_callback(
                    tool["name"]
                )
                self.add_item(protected_button)

        # 返回按钮（最后一行）
        back_row = 4 if self.selected_category else 1
        self.add_item(
            Button(
                label="🔙 返回主设置",
                style=ButtonStyle.secondary,
                custom_id="back_to_main",
                row=back_row,
            )
        )

    def _make_toggle_disabled_callback(self, tool_name: str):
        """创建切换工具禁用状态的回调函数"""

        async def callback(interaction: Interaction):
            await global_tool_settings_service.toggle_tool_disabled(tool_name)
            # 重新初始化视图
            await self._initialize()
            embed = self._create_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        return callback

    def _make_toggle_protected_callback(self, tool_name: str):
        """创建切换工具系统保留状态的回调函数"""

        async def callback(interaction: Interaction):
            await global_tool_settings_service.toggle_tool_protected(tool_name)
            # 重新初始化视图
            await self._initialize()
            embed = self._create_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        return callback

    async def on_category_select(self, interaction: Interaction):
        """处理类别选择事件"""
        if not interaction.data or "values" not in interaction.data:
            await interaction.response.defer()
            return

        self.selected_category = interaction.data["values"][0]
        await self._initialize()
        embed = self._create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        custom_id = interaction.data.get("custom_id") if interaction.data else None

        if custom_id == "back_to_main":
            await self.on_back_to_main(interaction)
            return True

        # 处理动态创建的按钮回调
        if custom_id and (
            custom_id.startswith("toggle_disabled_")
            or custom_id.startswith("toggle_protected_")
        ):
            # 这些回调已经在创建时绑定，不需要在这里处理
            pass

        return True

    async def on_back_to_main(self, interaction: Interaction):
        """返回主设置面板"""
        from src.chat.features.chat_settings.ui.chat_settings_view import (
            ChatSettingsView,
        )

        await interaction.response.defer()
        main_view = await ChatSettingsView.create(interaction)
        main_view.message = self.parent_message
        embed = await self._create_main_embed(main_view)
        await interaction.edit_original_response(
            content=None, embed=embed, view=main_view
        )
        self.stop()

    async def _create_main_embed(self, view: "ChatSettingsView") -> discord.Embed:
        """创建主设置面板的 Embed"""
        embed = discord.Embed(
            title="⚙️ 聊天设置",
            description="管理机器人的聊天功能设置",
            color=discord.Color.blue(),
        )

        # 全局设置
        global_chat_enabled = view.settings.get("global", {}).get("chat_enabled", True)
        warm_up_enabled = view.settings.get("global", {}).get("warm_up_enabled", True)
        api_fallback_enabled = view.settings.get("global", {}).get(
            "api_fallback_enabled", True
        )

        embed.add_field(
            name="🌐 全局设置",
            value=f"聊天总开关: {'✅ 开' if global_chat_enabled else '❌ 关'}\n"
            f"暖贴功能: {'✅ 开' if warm_up_enabled else '❌ 关'}\n"
            f"API回退: {'✅ 开' if api_fallback_enabled else '❌ 关'}",
            inline=False,
        )

        return embed

    def _create_embed(self) -> discord.Embed:
        """创建当前视图的 Embed"""
        embed = discord.Embed(
            title="🔧 全局工具设置",
            description="管理机器人的工具可用性\n\n"
            "• **全局禁用** (第一排按钮): AI 看不到该工具，整个机器人不可用\n"
            "• **系统保留** (第二排按钮): 用户无法在自己的设置中禁用该工具\n\n"
            "请先选择工具类别，然后点击对应按钮切换状态",
            color=discord.Color.orange(),
        )

        # 显示所有工具的统计信息
        total_tools = sum(len(tools) for tools in self.tools_by_category.values())
        disabled_count = sum(
            1
            for tools in self.tools_by_category.values()
            for tool in tools
            if tool["is_disabled"]
        )
        protected_count = sum(
            1
            for tools in self.tools_by_category.values()
            for tool in tools
            if tool["is_protected"]
        )

        embed.add_field(
            name="📊 统计信息",
            value=f"总工具数: {total_tools}\n"
            f"已禁用: {disabled_count}\n"
            f"系统保留: {protected_count}",
            inline=False,
        )

        # 如果选择了类别，显示该类别下的工具详情
        if self.selected_category and self.selected_category in self.tools_by_category:
            tools = self.tools_by_category[self.selected_category]
            tool_details = []
            for tool in tools[:10]:  # 最多显示 10 个
                status_icons = []
                status_icons.append("🚫" if tool["is_disabled"] else "✅")
                status_icons.append("🔒" if tool["is_protected"] else "🔓")
                tool_details.append(
                    f"{tool['emoji']} **{tool['display_name']}**: {''.join(status_icons)}"
                )

            embed.add_field(
                name=f"📁 {self.selected_category}",
                value="\n".join(tool_details) or "无工具",
                inline=False,
            )

        embed.set_footer(text="第一排: ✅启用/🚫禁用 | 第二排: 🔒保留/🔓可配置")

        return embed


class ToolDetailModal(discord.ui.Modal):
    """工具详情模态框（用于显示和编辑单个工具的设置）"""

    def __init__(self, tool_name: str, tool_info: Dict[str, Any]):
        super().__init__(title=f"工具设置: {tool_info.get('display_name', tool_name)}")
        self.tool_name = tool_name
        self.tool_info = tool_info

        # 添加说明文本
        self.add_item(
            discord.ui.TextInput(
                label="工具描述",
                style=discord.TextStyle.paragraph,
                default=tool_info.get("description", "无描述"),
                required=False,
            )
        )
