"""Embedding 模型设置视图"""

import discord
from discord.ui import View, Button, Select
from discord import (
    ButtonStyle,
    SelectOption,
    Interaction,
)
from typing import Optional, List

from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)


class EmbeddingSettingsView(View):
    """Embedding 模型设置面板"""

    def __init__(self, interaction: Interaction, parent_message: discord.Message):
        super().__init__(timeout=300)
        self.guild = interaction.guild
        self.service = chat_settings_service
        self.parent_message = parent_message
        self.current_model_id: Optional[str] = None
        self.available_models: list = []
        self.disabled_models: List[str] = []
        self.message: Optional[discord.Message] = None

    async def _initialize(self):
        """异步初始化"""
        self.current_model_id = await self.service.get_current_embedding_model()
        self.available_models = self.service.get_available_embedding_models()
        self.disabled_models = await self.service.get_disabled_embedding_models()
        self._create_view_items()

    @classmethod
    async def create(
        cls, interaction: Interaction, parent_message: discord.Message
    ) -> "EmbeddingSettingsView":
        """工厂方法，用于异步创建和初始化 View"""
        view = cls(interaction, parent_message)
        await view._initialize()
        return view

    def _create_view_items(self):
        """创建 UI 组件"""
        self.clear_items()

        # 模型选择下拉框
        options = []
        for model in self.available_models:
            is_selected = self.current_model_id == model["id"]
            options.append(
                SelectOption(
                    label=model["name"],
                    value=model["id"],
                    description=model["description"][:100]
                    if model["description"]
                    else None,
                    default=is_selected,
                    emoji="🧠" if model["id"] == "bge" else "🔮",
                )
            )

        model_select = Select(
            placeholder="选择 Embedding 模型...",
            options=options,
            custom_id="embedding_model_select",
            row=0,
        )
        model_select.callback = self.on_model_select
        self.add_item(model_select)

        # 禁用/启用模型按钮
        for model in self.available_models:
            is_disabled = model["id"] in self.disabled_models
            button_label = f"{'✅' if not is_disabled else '❌'} {model['name']}"
            button_style = (
                ButtonStyle.success if not is_disabled else ButtonStyle.danger
            )

            button = Button(
                label=button_label,
                style=button_style,
                custom_id=f"toggle_disable_{model['id']}",
                row=1 if model["id"] == "bge" else 2,
            )
            button.callback = self._make_toggle_callback(model["id"])
            self.add_item(button)

        # 返回按钮
        self.add_item(
            Button(
                label="🔙 返回主设置",
                style=ButtonStyle.secondary,
                custom_id="back_to_main",
                row=3,
            )
        )

    def _make_toggle_callback(self, model_id: str):
        """创建切换禁用状态的回调函数"""

        async def callback(interaction: Interaction):
            try:
                is_now_disabled = await self.service.toggle_embedding_model_disabled(
                    model_id
                )
                self.disabled_models = (
                    await self.service.get_disabled_embedding_models()
                )
                self._create_view_items()
                embed = self._create_embed()
                await interaction.response.edit_message(embed=embed, view=self)
            except ValueError as e:
                await interaction.response.send_message(
                    f"❌ 操作失败: {e}", ephemeral=True
                )

        return callback

    def _create_embed(self) -> discord.Embed:
        """创建设置面板的 Embed"""
        current_config = None
        for model in self.available_models:
            if model["id"] == self.current_model_id:
                current_config = model
                break

        embed = discord.Embed(
            title="🧠 Embedding 模型设置",
            description="选择用于向量搜索的 Embedding 模型。\n"
            "更改设置后，新的搜索请求将使用所选模型。\n\n"
            "**注意**: 切换模型不会重新生成已有数据的 embedding。",
            color=discord.Color.purple(),
        )

        if current_config:
            embed.add_field(
                name="当前模型",
                value=f"**{current_config['name']}** (`{current_config['model_name']}`)",
                inline=False,
            )
            embed.add_field(
                name="模型说明",
                value=current_config["description"],
                inline=False,
            )

        # 添加模型状态信息
        status_lines = []
        for model in self.available_models:
            is_disabled = model["id"] in self.disabled_models
            status_icon = "❌ 禁用" if is_disabled else "✅ 启用"
            status_lines.append(f"**{model['name']}**: {status_icon}")

        embed.add_field(
            name="⚙️ 模型状态",
            value="\n".join(status_lines),
            inline=False,
        )

        # 添加模型对比信息
        embed.add_field(
            name="📊 模型对比",
            value=(
                "**BGE-M3**: 通用多语言模型，需要指令前缀优化检索效果\n"
                "**Qwen3-Embedding**: 阿里通义千问，无需指令前缀，中文效果更好"
            ),
            inline=False,
        )

        embed.set_footer(
            text="💡 提示: 禁用的模型不会生成新的向量数据，但已有数据仍可搜索"
        )

        return embed

    async def on_model_select(self, interaction: Interaction):
        """处理模型选择"""
        if not interaction.data or "values" not in interaction.data:
            await interaction.response.defer()
            return

        selected_model_id = interaction.data["values"][0]

        try:
            await self.service.set_embedding_model(selected_model_id)
            self.current_model_id = selected_model_id
            self._create_view_items()
            embed = self._create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except ValueError as e:
            await interaction.response.send_message(f"❌ 设置失败: {e}", ephemeral=True)

    async def interaction_check(self, interaction: Interaction) -> bool:
        custom_id = interaction.data.get("custom_id") if interaction.data else None

        if custom_id == "back_to_main":
            await self.on_back_to_main(interaction)
            return True
        elif custom_id == "embedding_model_select":
            # 由 callback 处理
            return True

        return True

    async def on_back_to_main(self, interaction: Interaction):
        """返回主设置面板"""
        from src.chat.features.chat_settings.ui.chat_settings_view import (
            ChatSettingsView,
        )

        await interaction.response.defer()
        main_view = await ChatSettingsView.create(interaction)
        embed = discord.Embed(
            title="⚙️ 聊天设置",
            description="使用下方按钮管理聊天功能设置。",
            color=discord.Color.blue(),
        )
        await interaction.edit_original_response(
            content=None,
            embed=embed,
            view=main_view,
        )
        self.stop()
