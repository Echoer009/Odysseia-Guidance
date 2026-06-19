import discord
import logging
from discord.ui import View, Button, Select
from discord import (
    ButtonStyle,
    SelectOption,
    Interaction,
)
from typing import List, Optional, Dict, Any

log = logging.getLogger(__name__)

from src.chat.features.chat_settings.services.chat_settings_service import (
    chat_settings_service,
)
from src.database.services.token_usage_service import token_usage_service
from src.database.database import AsyncSessionLocal
from src.database.models import TokenUsage
from datetime import datetime
from src.chat.features.chat_settings.ui.warm_up_settings_view import WarmUpSettingsView
from src.chat.features.chat_settings.ui.cooldown_settings_view import (
    CooldownSettingsView,
)
from src.chat.services.event_service import event_service
from src.chat.features.chat_settings.ui.ai_model_settings_view import (
    AIModelSettingsView,
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
        self.factions: Optional[List[Dict[str, Any]]] = None
        self.selected_faction: Optional[str] = None
        self.token_usage: Optional[TokenUsage] = None
        self.interaction: Interaction = interaction

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
        self._create_view_items()

    @classmethod
    async def create(cls, interaction: Interaction):
        """工厂方法，用于异步创建和初始化View。"""
        view = cls(interaction)
        await view._initialize()
        return view

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

        feeding_image_enabled = self.settings.get("global", {}).get(
            "feeding_image_enabled", True
        )
        self.add_item(
            Button(
                label=f"投喂生图: {'开' if feeding_image_enabled else '关'}",
                style=ButtonStyle.green if feeding_image_enabled else ButtonStyle.red,
                custom_id="feeding_image_toggle",
                row=0,
            )
        )

        feeding_command_enabled = self.settings.get("global", {}).get(
            "feeding_command_enabled", True
        )
        self.add_item(
            Button(
                label=f"投喂命令: {'开' if feeding_command_enabled else '关'}",
                style=ButtonStyle.green if feeding_command_enabled else ButtonStyle.red,
                custom_id="feeding_command_toggle",
                row=0,
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

        # 功能按钮 (第 2 行)
        self.add_item(
            Button(
                label="⏱️ 冷却设置",
                style=ButtonStyle.primary,
                custom_id="cooldown_settings",
                row=2,
            )
        )

        reply_delay = self.settings.get("global", {}).get("reply_delay_seconds", 30)
        self.add_item(
            Button(
                label=f"🐢 回复延迟: {reply_delay}s",
                style=ButtonStyle.secondary,
                custom_id="reply_delay_settings",
                row=2,
            )
        )

        self.add_item(
            Button(
                label="设置暖贴频道",
                style=ButtonStyle.secondary,
                custom_id="warm_up_settings",
                row=2,
            )
        )

        self.add_item(
            Button(
                label="更换AI模型",
                style=ButtonStyle.secondary,
                custom_id="ai_model_settings",
                row=3,
            )
        )

        # --- [DISABLED] 印象总结功能（flash模型）已禁用 ---
        # self.add_item(
        #     Button(
        #         label="📝 总结模型",
        #         style=ButtonStyle.secondary,
        #         custom_id="summary_model_settings",
        #         row=3,
        #     )
        # )

        # 两阶段回复管线：工具模型 / 写作模型设置
        self.add_item(
            Button(
                label="🔧 工具模型",
                style=ButtonStyle.secondary,
                custom_id="tool_model_settings",
                row=3,
            )
        )

        self.add_item(
            Button(
                label="✍️ 写作模型",
                style=ButtonStyle.secondary,
                custom_id="writer_model_settings",
                row=3,
            )
        )

        two_stage_enabled = self.settings.get("global", {}).get(
            "two_stage_enabled", False
        )
        self.add_item(
            Button(
                label=f"🔀 两阶段: {'开' if two_stage_enabled else '关'}",
                style=ButtonStyle.green if two_stage_enabled else ButtonStyle.red,
                custom_id="two_stage_toggle",
                row=2,
            )
        )

        self.add_item(
            Button(
                label="今日Token",
                style=ButtonStyle.secondary,
                custom_id="show_token_usage",
                row=3,
            )
        )

        # 第 3 行：模型参数设置
        self.add_item(
            Button(
                label="🎛️ 模型参数",
                style=ButtonStyle.secondary,
                custom_id="model_params_settings",
                row=3,
            )
        )

        # 第 4 行：Embedding 设置
        self.add_item(
            Button(
                label="🧠 Embedding模型",
                style=ButtonStyle.secondary,
                custom_id="embedding_settings",
                row=4,
            )
        )

        # 第 4 行：全局工具设置
        self.add_item(
            Button(
                label="🔧 全局工具设置",
                style=ButtonStyle.secondary,
                custom_id="global_tools_settings",
                row=4,
            )
        )

        # 第 4 行：Provider / Model 管理
        self.add_item(
            Button(
                label="🔌 Provider管理",
                style=ButtonStyle.success,
                custom_id="provider_management",
                row=4,
            )
        )

        self.add_item(
            Button(
                label="🤖 Model管理",
                style=ButtonStyle.success,
                custom_id="model_management",
                row=4,
            )
        )

        # 第 4 行：文爱过滤
        self.add_item(
            Button(
                label="🛡️ 文爱过滤",
                style=ButtonStyle.secondary,
                custom_id="content_filter",
                row=4,
            )
        )

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
        elif custom_id == "feeding_image_toggle":
            await self.on_feeding_image_toggle(interaction)
        elif custom_id == "feeding_command_toggle":
            await self.on_feeding_command_toggle(interaction)
        elif custom_id == "cooldown_settings":
            await self.on_cooldown_settings(interaction)
        elif custom_id == "reply_delay_settings":
            await self.on_reply_delay_settings(interaction)
        elif custom_id == "warm_up_settings":
            await self.on_warm_up_settings(interaction)
        elif custom_id == "ai_model_settings":
            await self.on_ai_model_settings(interaction)
        elif custom_id == "tool_model_settings":
            await self.on_tool_model_settings(interaction)
        elif custom_id == "writer_model_settings":
            await self.on_writer_model_settings(interaction)
        elif custom_id == "two_stage_toggle":
            await self.on_two_stage_toggle(interaction)
        # --- [DISABLED] 印象总结功能（flash模型）已禁用 ---
        # elif custom_id == "summary_model_settings":
        #     await self.on_summary_model_settings(interaction)
        elif custom_id == "show_token_usage":
            await self.on_show_token_usage(interaction)
        elif custom_id == "embedding_settings":
            await self.on_embedding_settings(interaction)
        elif custom_id == "global_tools_settings":
            await self.on_global_tools_settings(interaction)
        elif custom_id == "model_params_settings":
            await self.on_model_params_settings(interaction)
        elif custom_id == "provider_management":
            await self.on_provider_management(interaction)
        elif custom_id == "model_management":
            await self.on_model_management(interaction)
        elif custom_id == "content_filter":
            await self.on_content_filter(interaction)

        return True

    async def on_global_toggle(self, interaction: Interaction):
        current_state = self.settings.get("global", {}).get("chat_enabled", True)
        new_state = not current_state
        await self.service.db_manager.set_global_setting(
            "chat_enabled", str(new_state)
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
        """切换 API fallback 全局设置。"""
        current_state = self.settings.get("global", {}).get(
            "api_fallback_enabled", True
        )
        new_state = not current_state
        # 更新全局设置
        await self.service.db_manager.set_global_setting(
            "api_fallback_enabled", str(new_state)
        )
        await self._update_view(interaction)

    async def on_feeding_image_toggle(self, interaction: Interaction):
        current_state = self.settings.get("global", {}).get(
            "feeding_image_enabled", True
        )
        new_state = not current_state
        await self.service.db_manager.set_global_setting(
            "feeding_image_enabled", str(new_state)
        )
        await self._update_view(interaction)

    async def on_feeding_command_toggle(self, interaction: Interaction):
        """切换 /投喂 命令的全局开关。"""
        current_state = self.settings.get("global", {}).get(
            "feeding_command_enabled", True
        )
        new_state = not current_state
        await self.service.set_feeding_command_enabled(new_state)
        await self._update_view(interaction)

    async def on_cooldown_settings(self, interaction: Interaction):
        """切换到冷却设置视图。"""
        if not self.message:
            await interaction.response.send_message(
                "无法找到原始消息，请重新打开设置面板。", ephemeral=True
            )
            return

        await interaction.response.defer()
        cooldown_view = await CooldownSettingsView.create(interaction, self.message)
        embed = cooldown_view._create_view_items()
        await interaction.edit_original_response(
            content=None, embed=embed, view=cooldown_view
        )
        self.stop()

    async def on_reply_delay_settings(self, interaction: Interaction):
        """打开回复延迟设置模态框。"""
        from src.chat.features.chat_settings.ui.reply_delay_modal import (
            ReplyDelayModal,
            DEFAULT_REPLY_DELAY_SECONDS,
        )

        current_delay = self.settings.get("global", {}).get(
            "reply_delay_seconds", DEFAULT_REPLY_DELAY_SECONDS
        )

        async def on_submit(submit_interaction: Interaction, seconds: int):
            await self.service.set_reply_delay(seconds)
            # 刷新主面板数据与按钮标签
            await self._initialize()
            await submit_interaction.response.edit_message(view=self)

        modal = ReplyDelayModal(current_delay=current_delay, on_submit_callback=on_submit)
        await interaction.response.send_modal(modal)

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

    async def on_ai_model_settings(self, interaction: Interaction):
        """打开AI模型设置视图。"""
        (
            current_provider,
            current_model,
        ) = await self.service.get_current_ai_model_with_provider()

        view = await AIModelSettingsView.create(
            current_provider=current_provider,
            current_model=current_model,
        )

        # 发送视图
        embed = discord.Embed(
            title="🤖 AI 模型设置",
            description="请选择供应商和模型",
            color=discord.Color.blue(),
        )

        # 显示当前设置
        if current_provider and current_model:
            embed.add_field(
                name="当前设置",
                value=f"供应商: `{current_provider}`\n模型: `{current_model}`",
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed,
            view=view,
            ephemeral=True,
        )

        # 等待视图完成
        await view.wait()

        # 如果用户确认了选择，保存设置
        full_model_id = view.get_selected_full_model_id()
        if full_model_id:
            provider, model = AIModelSettingsView.parse_full_model_id(full_model_id)
            if provider and model:
                # 直接存模型名，不带 provider 前缀
                await self.service.set_ai_model(model)

    async def _open_model_picker(
        self,
        interaction: Interaction,
        title: str,
        description: str,
        getter,
        setter,
        require_tools: bool = False,
    ):
        """通用：打开 AIModelSettingsView 选择并保存模型。"""
        current = await getter()
        current_provider = None
        current_model = current
        if current and ":" in current:
            cp, cm = AIModelSettingsView.parse_full_model_id(current)
            current_provider, current_model = cp, cm

        log.info(
            f"[模型选择] 打开选择器: current={current!r}, "
            f"provider={current_provider!r}, model={current_model!r}, "
            f"require_tools={require_tools}"
        )

        view = await AIModelSettingsView.create(
            current_provider=current_provider,
            current_model=current_model,
            require_tools=require_tools,
        )

        embed = discord.Embed(
            title=title, description=description, color=discord.Color.blue()
        )
        from src.chat.services.ai.config.models import get_model_configs

        model_configs = get_model_configs()
        display = current or "未设置（回退到当前AI模型）"
        if current and current in model_configs:
            display = model_configs[current].display_name or current
        embed.add_field(name="当前设置", value=f"模型: `{display}`", inline=False)

        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )
        await view.wait()

        full_model_id = view.get_selected_full_model_id()
        log.info(
            f"[模型选择] wait返回: confirmed={view.confirmed}, "
            f"selected_provider={view.selected_provider!r}, "
            f"selected_model={view.selected_model!r}, "
            f"full_model_id={full_model_id!r}"
        )
        if full_model_id:
            provider, model = AIModelSettingsView.parse_full_model_id(full_model_id)
            if model:
                save_value = f"{provider}:{model}" if provider else model
                log.info(f"[模型选择] 即将保存: {save_value!r}")
                await setter(save_value)
            else:
                log.warning(f"[模型选择] model 为空，未保存: provider={provider!r}")
        else:
            log.info("[模型选择] 未确认或未选择，不保存")


    async def on_tool_model_settings(self, interaction: Interaction):
        """打开 Stage 1 工具模型设置（仅显示支持工具调用的模型）。"""
        await self._open_model_picker(
            interaction,
            title="🔧 工具模型设置（Stage 1）",
            description="选择用于判断并调用工具的模型（仅显示支持工具调用的模型）",
            getter=self.service.get_tool_model,
            setter=self.service.set_tool_model,
            require_tools=True,
        )

    async def on_writer_model_settings(self, interaction: Interaction):
        """打开 Stage 2 写作模型设置。"""
        await self._open_model_picker(
            interaction,
            title="✍️ 写作模型设置（Stage 2）",
            description="选择用于撰写最终回复的模型（文笔优先，可不支持工具）",
            getter=self.service.get_writer_model,
            setter=self.service.set_writer_model,
            require_tools=False,
        )

    async def on_two_stage_toggle(self, interaction: Interaction):
        """切换两阶段回复管线总开关。"""
        new_state = not await self.service.is_two_stage_enabled()
        await self.service.set_two_stage_enabled(new_state)
        await self._update_view(interaction)

    # --- [DISABLED] 印象总结功能（flash模型）已禁用 ---
    # async def on_summary_model_settings(self, interaction: Interaction):
    #     """打开总结模型设置视图。"""
    #     from src.chat.services.ai.config.models import get_model_configs
    #     current_summary_model = await self.service.get_summary_model()
    #     view = await AIModelSettingsView.create(
    #         current_provider=None,
    #         current_model=current_summary_model,
    #     )
    #     embed = discord.Embed(
    #         title="📝 总结模型设置",
    #         description="选择用于个人记忆摘要的模型",
    #         color=discord.Color.blue(),
    #     )
    #     if current_summary_model:
    #         model_configs = get_model_configs()
    #         display = current_summary_model
    #         if current_summary_model in model_configs:
    #             display = model_configs[current_summary_model].display_name or current_summary_model
    #         embed.add_field(
    #             name="当前设置",
    #             value=f"模型: `{display}`",
    #             inline=False,
    #         )
    #     else:
    #         embed.add_field(
    #             name="当前设置",
    #             value="未设置（使用默认值）",
    #             inline=False,
    #         )
    #     await interaction.response.send_message(
    #         embed=embed,
    #         view=view,
    #         ephemeral=True,
    #     )
    #     await view.wait()
    #     full_model_id = view.get_selected_full_model_id()
    #     if full_model_id:
    #         provider, model = AIModelSettingsView.parse_full_model_id(full_model_id)
    #         if model:
    #             await self.service.set_summary_model(model)

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

    async def on_embedding_settings(self, interaction: Interaction):
        """切换到 Embedding 模型设置视图。"""
        if not self.message:
            await interaction.response.send_message(
                "无法找到原始消息，请重新打开设置面板。", ephemeral=True
            )
            return

        await interaction.response.defer()
        from src.chat.features.chat_settings.ui.embedding_settings_view import (
            EmbeddingSettingsView,
        )

        embedding_view = await EmbeddingSettingsView.create(interaction, self.message)
        embed = embedding_view._create_embed()
        await interaction.edit_original_response(
            content=None, embed=embed, view=embedding_view
        )
        self.stop()

    async def on_global_tools_settings(self, interaction: Interaction):
        """切换到全局工具设置视图。"""
        if not self.message:
            await interaction.response.send_message(
                "无法找到原始消息，请重新打开设置面板。", ephemeral=True
            )
            return

        await interaction.response.defer()
        from src.chat.features.chat_settings.ui.global_tools_settings_view import (
            GlobalToolsSettingsView,
        )

        tools_view = await GlobalToolsSettingsView.create(interaction, self.message)
        embed = tools_view._create_embed()
        await interaction.edit_original_response(
            content=None, embed=embed, view=tools_view
        )
        self.stop()

    async def on_model_params_settings(self, interaction: Interaction):
        """切换到模型参数设置视图。"""
        if not self.message:
            await interaction.response.send_message(
                "无法找到原始消息，请重新打开设置面板。", ephemeral=True
            )
            return

        await interaction.response.defer()
        from src.chat.features.chat_settings.ui.model_params_view import ModelParamsView

        async def back_callback(back_interaction: Interaction):
            """返回主设置面板"""
            await back_interaction.response.defer()
            main_view = await ChatSettingsView.create(back_interaction)
            main_view.message = self.message
            await back_interaction.edit_original_response(
                content=None, embed=None, view=main_view
            )

        model_params_view = await ModelParamsView.create(back_callback)
        model_params_view.message = self.message
        embed = model_params_view._get_params_embed()
        await interaction.edit_original_response(
            content=None, embed=embed, view=model_params_view
        )
        self.stop()

    async def on_provider_management(self, interaction: Interaction):
        """切换到 Provider 管理视图。"""
        if not self.message:
            await interaction.response.send_message(
                "无法找到原始消息，请重新打开设置面板。", ephemeral=True
            )
            return

        await interaction.response.defer()
        from src.chat.features.chat_settings.ui.provider_management_view import (
            ProviderManagementView,
        )

        async def back_callback(back_interaction: Interaction):
            await back_interaction.response.defer()
            main_view = await ChatSettingsView.create(back_interaction)
            main_view.message = self.message
            await back_interaction.edit_original_response(
                content=None, embed=None, view=main_view
            )

        provider_view = await ProviderManagementView.create(back_callback)
        provider_view.message = self.message
        await interaction.edit_original_response(
            content=None, embed=provider_view._get_embed(), view=provider_view
        )
        self.stop()

    async def on_model_management(self, interaction: Interaction):
        """切换到 Model 管理视图。"""
        if not self.message:
            await interaction.response.send_message(
                "无法找到原始消息，请重新打开设置面板。", ephemeral=True
            )
            return

        await interaction.response.defer()
        from src.chat.features.chat_settings.ui.model_management_view import (
            ModelManagementView,
        )

        async def back_callback(back_interaction: Interaction):
            await back_interaction.response.defer()
            main_view = await ChatSettingsView.create(back_interaction)
            main_view.message = self.message
            await back_interaction.edit_original_response(
                content=None, embed=None, view=main_view
            )

        model_view = await ModelManagementView.create(back_callback)
        model_view.message = self.message
        await interaction.edit_original_response(
            content=None, embed=model_view._get_embed(), view=model_view
        )
        self.stop()

    async def on_content_filter(self, interaction: Interaction):
        """切换到文爱过滤关键词管理视图。"""
        if not self.message:
            await interaction.response.send_message(
                "无法找到原始消息，请重新打开设置面板。", ephemeral=True
            )
            return

        await interaction.response.defer()
        from src.chat.features.content_filter.ui.keyword_management_view import (
            KeywordManagementView,
        )

        async def back_callback(back_interaction: Interaction):
            await back_interaction.response.defer()
            main_view = await ChatSettingsView.create(back_interaction)
            main_view.message = self.message
            await back_interaction.edit_original_response(
                content=None, embed=None, view=main_view
            )

        filter_view = await KeywordManagementView.create(back_callback, self.message)
        await interaction.edit_original_response(
            content=None, embed=filter_view._build_embed(), view=filter_view
        )
        self.stop()
