# -*- coding: utf-8 -*-
"""
AI 模型设置视图

提供 Provider + Model 双下拉选择界面
"""

import discord
from discord.ui import View, Select, Button
from discord import ButtonStyle, Interaction, SelectOption
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.chat.services.ai.config.models import ModelConfig


class AIModelSettingsView(View):
    """
    AI 模型设置视图

    通过两个级联下拉框选择模型：
    1. Provider 下拉框 - 选择供应商
    2. Model 下拉框 - 选择该供应商下的模型
    """

    def __init__(
        self,
        current_provider: Optional[str] = None,
        current_model: Optional[str] = None,
    ):
        super().__init__(timeout=300)
        self.selected_provider: Optional[str] = current_provider
        self.selected_model: Optional[str] = current_model
        self.confirmed = False

        self._models_by_provider: Dict[str, Dict[str, "ModelConfig"]] = {}

    async def _initialize(self):
        self._models_by_provider = await self._get_models_by_provider()
        self._create_provider_select()
        self._create_model_select()
        self._create_buttons()

    @classmethod
    async def create(
        cls,
        current_provider: Optional[str] = None,
        current_model: Optional[str] = None,
    ) -> "AIModelSettingsView":
        view = cls(current_provider, current_model)
        await view._initialize()
        return view

    async def _get_models_by_provider(self) -> Dict[str, Dict[str, "ModelConfig"]]:
        grouped: Dict[str, Dict[str, "ModelConfig"]] = {}

        try:
            from src.database.database import AsyncSessionLocal
            from src.database.services.ai_config_service import ai_config_service
            from src.chat.services.ai.config.models import (
                ModelConfig,
                GenerationConfigParams,
                PromptConfig,
            )

            async with AsyncSessionLocal() as session:
                models = await ai_config_service.get_all_models(
                    session, enabled_only=True
                )

                for m in models:
                    gen_dict = m.generation_config or {}
                    prompt_dict = m.prompt_config or {}

                    gen_config = GenerationConfigParams(
                        temperature=gen_dict.get("temperature", 1.0),
                        top_p=gen_dict.get("top_p", 0.95),
                        top_k=gen_dict.get("top_k"),
                        max_output_tokens=gen_dict.get(
                            "max_output_tokens", m.max_output_tokens
                        ),
                        presence_penalty=gen_dict.get("presence_penalty", 0.0),
                        frequency_penalty=gen_dict.get("frequency_penalty", 0.0),
                        thinking_budget_tokens=gen_dict.get("thinking_budget_tokens"),
                    )

                    prompt_config = PromptConfig(
                        system_prompt=prompt_dict.get("system_prompt"),
                        jailbreak_user_prompt=prompt_dict.get("jailbreak_user_prompt"),
                        jailbreak_model_response=prompt_dict.get(
                            "jailbreak_model_response"
                        ),
                        jailbreak_final_instruction=prompt_dict.get(
                            "jailbreak_final_instruction"
                        ),
                        use_cache_optimized_build=prompt_dict.get(
                            "use_cache_optimized_build"
                        ),
                    )

                    provider_name = m.provider.name if m.provider else "unknown"

                    config = ModelConfig(
                        display_name=m.display_name,
                        provider=provider_name,
                        actual_model=m.actual_model,
                        description=m.description or "",
                        supports_vision=bool(m.supports_vision),
                        supports_tools=bool(m.supports_tools),
                        supports_thinking=bool(m.supports_thinking),
                        max_output_tokens=m.max_output_tokens,
                        generation_config=gen_config,
                        prompt_config=prompt_config,
                    )

                    if provider_name not in grouped:
                        grouped[provider_name] = {}
                    grouped[provider_name][m.model_name] = config

            if grouped:
                return grouped

        except Exception:
            pass

        from src.chat.services.ai.config.models import get_model_configs

        model_configs = get_model_configs()
        for model_name, config in model_configs.items():
            provider = config.provider or "unknown"
            if provider not in grouped:
                grouped[provider] = {}
            grouped[provider][model_name] = config

        return grouped

    def _get_provider_display_name(self, provider_name: str) -> str:
        provider_names = {
            "gemini_official": "📦 Gemini 官方",
            "deepseek": "📦 DeepSeek",
            "openai_compatible": "📦 OpenAI 兼容",
            "unknown": "📦 未知",
        }

        if provider_name.startswith("gemini_custom_"):
            endpoint_name = provider_name.replace("gemini_custom_", "")
            return f"📦 Gemini 自定义 ({endpoint_name})"

        return provider_names.get(provider_name, f"📦 {provider_name}")

    def _create_provider_select(self):
        options = []

        for provider_name in sorted(self._models_by_provider.keys()):
            display_name = self._get_provider_display_name(provider_name)
            is_default = provider_name == self.selected_provider
            options.append(
                SelectOption(
                    label=display_name[:100],
                    value=provider_name,
                    default=is_default,
                )
            )

        if not options:
            options.append(
                SelectOption(label="无可用 Provider", value="none", default=True)
            )

        self.provider_select = Select(
            placeholder="选择供应商...",
            options=options[:25],
            custom_id="provider_select",
            row=0,
        )
        self.provider_select.callback = self._on_provider_select
        self.add_item(self.provider_select)

    def _create_model_select(self, provider_name: Optional[str] = None):
        for item in self.children:
            if isinstance(item, Select) and item.custom_id == "model_select":
                self.remove_item(item)
                break

        options = []
        provider = provider_name or self.selected_provider

        if provider and provider in self._models_by_provider:
            models = self._models_by_provider[provider]
            for model_name, config in models.items():
                display_name = config.display_name or model_name
                is_default = model_name == self.selected_model
                options.append(
                    SelectOption(
                        label=display_name[:100],
                        value=model_name,
                        description=config.description[:100]
                        if config.description
                        else None,
                        default=is_default,
                    )
                )

        if not options:
            options.append(
                SelectOption(label="请先选择供应商", value="none", default=True)
            )

        self.model_select = Select(
            placeholder="选择模型...",
            options=options[:25],
            custom_id="model_select",
            row=1,
        )
        self.model_select.callback = self._on_model_select
        self.add_item(self.model_select)

    def _create_buttons(self):
        self.confirm_button = Button(
            label="✅ 确认",
            style=ButtonStyle.green,
            custom_id="confirm",
            row=2,
            disabled=True,
        )
        self.confirm_button.callback = self._on_confirm
        self.add_item(self.confirm_button)

        self.cancel_button = Button(
            label="❌ 取消",
            style=ButtonStyle.red,
            custom_id="cancel",
            row=2,
        )
        self.cancel_button.callback = self._on_cancel
        self.add_item(self.cancel_button)

    async def _on_provider_select(self, interaction: Interaction):
        self.selected_provider = self.provider_select.values[0]
        self.selected_model = None
        self._create_model_select(self.selected_provider)
        self.confirm_button.disabled = True
        await interaction.response.edit_message(view=self)

    async def _on_model_select(self, interaction: Interaction):
        self.selected_model = self.model_select.values[0]
        self.confirm_button.disabled = False
        await interaction.response.edit_message(view=self)

    async def _on_confirm(self, interaction: Interaction):
        self.confirmed = True
        self.stop()

        display_name = self.selected_model or ""
        if (
            self.selected_provider
            and self.selected_provider in self._models_by_provider
        ):
            if (
                self.selected_model
                and self.selected_model
                in self._models_by_provider[self.selected_provider]
            ):
                config = self._models_by_provider[self.selected_provider][
                    self.selected_model
                ]
                display_name = config.display_name or self.selected_model

        provider_display = self._get_provider_display_name(
            self.selected_provider or "unknown"
        )

        embed = discord.Embed(
            title="✅ 模型已更新",
            description=f"供应商: **{provider_display}**\n模型: **{display_name}**",
            color=discord.Color.green(),
        )

        await interaction.response.edit_message(embed=embed, view=None)

    async def _on_cancel(self, interaction: Interaction):
        self.stop()

        embed = discord.Embed(
            title="❌ 已取消",
            description="模型设置未更改",
            color=discord.Color.red(),
        )

        await interaction.response.edit_message(embed=embed, view=None)

    def get_selected_full_model_id(self) -> Optional[str]:
        if self.confirmed and self.selected_provider and self.selected_model:
            return f"{self.selected_provider}:{self.selected_model}"
        return None

    @classmethod
    def parse_full_model_id(
        cls, full_model_id: str
    ) -> tuple[Optional[str], Optional[str]]:
        if not full_model_id:
            return None, None

        if ":" in full_model_id:
            parts = full_model_id.split(":", 1)
            return parts[0], parts[1]

        from src.chat.services.ai.config.models import get_model_configs

        model_configs = get_model_configs()

        if full_model_id in model_configs:
            return model_configs[full_model_id].provider, full_model_id

        return None, full_model_id
