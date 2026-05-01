# -*- coding: utf-8 -*-
"""
Provider 管理视图

通过 Discord UI 管理 AI Provider 的添加、编辑、删除。
"""

import discord
from discord.ui import View, Button, Select, Modal, TextInput
from discord import ButtonStyle, SelectOption, Interaction
from typing import Optional, Callable, Awaitable, List

from src.database.database import AsyncSessionLocal
from src.database.services.ai_config_service import ai_config_service

PROVIDER_TYPES = ["gemini", "deepseek", "openai_compatible", "gemini_custom"]


async def _reload_ai_service():
    from src.chat.services.ai.service import ai_service
    from src.chat.services.ai.config.models import reload_model_configs_async
    await ai_service.reload_providers()
    await reload_model_configs_async()


class AddProviderModal(Modal):
    def __init__(self, on_save: Callable[[Interaction, dict], Awaitable[None]]):
        super().__init__(title="添加 Provider")
        self.on_save = on_save

        self.name_input = TextInput(
            label="Provider名称(英文唯一标识)",
            placeholder="例: my_gemini, deepseek_main",
            custom_id="name",
            required=True,
            max_length=100,
        )
        self.add_item(self.name_input)

        self.type_input = TextInput(
            label="类型",
            placeholder="gemini/deepseek/openai_compatible/gemini_custom",
            custom_id="provider_type",
            required=True,
            max_length=50,
        )
        self.add_item(self.type_input)

        self.display_name_input = TextInput(
            label="显示名称",
            placeholder="例: 我的Gemini端点",
            custom_id="display_name",
            required=True,
            max_length=200,
        )
        self.add_item(self.display_name_input)

        self.api_key_input = TextInput(
            label="API Key",
            placeholder="输入你的API Key",
            custom_id="api_key",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=2000,
        )
        self.add_item(self.api_key_input)

        self.base_url_input = TextInput(
            label="Base URL(可选)",
            placeholder="自定义端点URL,留空用默认",
            custom_id="base_url",
            required=False,
            max_length=500,
        )
        self.add_item(self.base_url_input)

    async def on_submit(self, interaction: Interaction):
        ptype = self.type_input.value.strip().lower()
        if ptype not in PROVIDER_TYPES:
            await interaction.response.send_message(
                f"❌ 不支持的 Provider 类型: `{ptype}`，请使用: {', '.join(PROVIDER_TYPES)}",
                ephemeral=True,
            )
            return

        data = {
            "name": self.name_input.value.strip(),
            "provider_type": ptype,
            "display_name": self.display_name_input.value.strip(),
            "api_key": self.api_key_input.value.strip(),
            "base_url": self.base_url_input.value.strip() or None,
        }
        await self.on_save(interaction, data)


class EditProviderModal(Modal):
    def __init__(
        self,
        provider_name: str,
        display_name: str,
        base_url: Optional[str],
        on_save: Callable[[Interaction, dict], Awaitable[None]],
    ):
        super().__init__(title=f"编辑 Provider: {provider_name}")
        self.on_save = on_save
        self.provider_name = provider_name

        self.display_name_input = TextInput(
            label="显示名称",
            default=display_name,
            custom_id="display_name",
            required=True,
            max_length=200,
        )
        self.add_item(self.display_name_input)

        self.api_key_input = TextInput(
            label="API Key(留空不修改)",
            placeholder="输入新Key或留空",
            custom_id="api_key",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=2000,
        )
        self.add_item(self.api_key_input)

        self.base_url_input = TextInput(
            label="Base URL",
            default=base_url or "",
            placeholder="自定义端点URL",
            custom_id="base_url",
            required=False,
            max_length=500,
        )
        self.add_item(self.base_url_input)

    async def on_submit(self, interaction: Interaction):
        data = {
            "provider_name": self.provider_name,
            "display_name": self.display_name_input.value.strip(),
            "api_key": self.api_key_input.value.strip() or None,
            "base_url": self.base_url_input.value.strip() or None,
        }
        await self.on_save(interaction, data)


class ProviderManagementView(View):
    def __init__(
        self,
        on_back_callback: Callable[[Interaction], Awaitable[None]],
    ):
        super().__init__(timeout=300)
        self.on_back_callback = on_back_callback
        self.providers: list = []
        self.selected_provider_id: Optional[int] = None
        self.message: Optional[discord.Message] = None

    async def _initialize(self):
        async with AsyncSessionLocal() as session:
            self.providers = await ai_config_service.get_all_providers(session)
        self._build_view()

    @classmethod
    async def create(
        cls, on_back_callback: Callable[[Interaction], Awaitable[None]]
    ) -> "ProviderManagementView":
        view = cls(on_back_callback)
        await view._initialize()
        return view

    def _build_view(self):
        self.clear_items()

        if self.providers:
            options = []
            for p in self.providers[:25]:
                status = "✅" if p.enabled else "❌"
                model_count = len(p.models) if hasattr(p, "models") else 0
                options.append(
                    SelectOption(
                        label=f"{status} {p.display_name} ({p.name})",
                        description=f"类型: {p.provider_type} | 模型数: {model_count}",
                        value=str(p.id),
                        default=self.selected_provider_id == p.id,
                    )
                )
            provider_select = Select(
                placeholder="选择一个 Provider...",
                options=options,
                custom_id="provider_select",
                row=0,
            )
            provider_select.callback = self._on_provider_select
            self.add_item(provider_select)

        add_button = Button(
            label="➕ 添加 Provider",
            style=ButtonStyle.success,
            custom_id="add_provider",
            row=1,
        )
        add_button.callback = self._on_add
        self.add_item(add_button)

        if self.selected_provider_id:
            edit_button = Button(
                label="✏️ 编辑",
                style=ButtonStyle.primary,
                custom_id="edit_provider",
                row=1,
            )
            edit_button.callback = self._on_edit
            self.add_item(edit_button)

            toggle_button = Button(
                label="🔄 启/禁用",
                style=ButtonStyle.secondary,
                custom_id="toggle_provider",
                row=1,
            )
            toggle_button.callback = self._on_toggle
            self.add_item(toggle_button)

            delete_button = Button(
                label="🗑️ 删除",
                style=ButtonStyle.danger,
                custom_id="delete_provider",
                row=1,
            )
            delete_button.callback = self._on_delete
            self.add_item(delete_button)

        back_button = Button(
            label="🔙 返回",
            style=ButtonStyle.secondary,
            custom_id="back",
            row=2,
        )
        back_button.callback = self._on_back
        self.add_item(back_button)

    def _get_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔌 Provider 管理",
            description="管理 AI 服务提供商。添加、编辑或删除 Provider。\n\n"
            "支持类型: `gemini` / `deepseek` / `openai_compatible`",
            color=discord.Color.blue(),
        )

        if self.providers:
            lines = []
            for p in self.providers:
                status = "✅" if p.enabled else "❌"
                model_count = len(p.models) if hasattr(p, "models") else 0
                base_url_display = f"\n  URL: `{p.base_url}`" if p.base_url else ""
                lines.append(
                    f"{status} **{p.display_name}** (`{p.name}`)\n"
                    f"  类型: `{p.provider_type}` | 模型数: {model_count}{base_url_display}"
                )
            embed.add_field(
                name=f"已配置 Provider ({len(self.providers)})",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="暂无 Provider",
                value='点击下方「➕ 添加 Provider」按钮添加你的第一个 AI 服务提供商。',
                inline=False,
            )

        return embed

    async def _on_provider_select(self, interaction: Interaction):
        select = [i for i in self.children if isinstance(i, Select)][0]
        self.selected_provider_id = int(select.values[0])
        self._build_view()
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    async def _on_add(self, interaction: Interaction):
        async def on_save(save_interaction: Interaction, data: dict):
            async with AsyncSessionLocal() as session:
                existing = await ai_config_service.get_provider_by_name(
                    session, data["name"]
                )
                if existing:
                    await save_interaction.response.send_message(
                        f"❌ Provider `{data['name']}` 已存在", ephemeral=True
                    )
                    return

                await ai_config_service.create_provider(
                    session,
                    name=data["name"],
                    provider_type=data["provider_type"],
                    display_name=data["display_name"],
                    api_key=data["api_key"],
                    base_url=data.get("base_url"),
                )
            await save_interaction.response.send_message(
                f"✅ Provider `{data['name']}` 添加成功！", ephemeral=True
            )
            await self._refresh(save_interaction)

        modal = AddProviderModal(on_save)
        await interaction.response.send_modal(modal)

    async def _on_edit(self, interaction: Interaction):
        if not self.selected_provider_id:
            await interaction.response.send_message("请先选择一个 Provider", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            from src.database.services.ai_config_service import ai_config_service as svc
            from sqlalchemy.future import select
            from src.database.models import AiProvider

            stmt = select(AiProvider).where(AiProvider.id == self.selected_provider_id)
            result = await session.execute(stmt)
            provider = result.scalars().first()

        if not provider:
            await interaction.response.send_message("Provider 不存在", ephemeral=True)
            return

        async def on_save(save_interaction: Interaction, data: dict):
            async with AsyncSessionLocal() as session:
                kwargs = {
                    "display_name": data["display_name"],
                    "base_url": data.get("base_url"),
                }
                if data.get("api_key"):
                    kwargs["api_key"] = data["api_key"]
                await ai_config_service.update_provider(
                    session, self.selected_provider_id, **kwargs
                )
            await save_interaction.response.send_message(
                f"✅ Provider `{data['provider_name']}` 已更新！", ephemeral=True
            )
            await self._refresh(save_interaction)

        modal = EditProviderModal(
            provider_name=provider.name,
            display_name=provider.display_name,
            base_url=provider.base_url,
            on_save=on_save,
        )
        await interaction.response.send_modal(modal)

    async def _on_toggle(self, interaction: Interaction):
        if not self.selected_provider_id:
            return

        async with AsyncSessionLocal() as session:
            from sqlalchemy.future import select
            from src.database.models import AiProvider

            stmt = select(AiProvider).where(AiProvider.id == self.selected_provider_id)
            result = await session.execute(stmt)
            provider = result.scalars().first()
            if provider:
                new_enabled = 0 if provider.enabled else 1
                await ai_config_service.update_provider(
                    session, self.selected_provider_id, enabled=new_enabled
                )

        await interaction.response.defer()
        await self._refresh(interaction)

    async def _on_delete(self, interaction: Interaction):
        if not self.selected_provider_id:
            return

        async with AsyncSessionLocal() as session:
            await ai_config_service.delete_provider(session, self.selected_provider_id)
        self.selected_provider_id = None

        await interaction.response.defer()
        await self._refresh(interaction)

    async def _on_back(self, interaction: Interaction):
        self.stop()
        await self.on_back_callback(interaction)

    async def _refresh(self, interaction: Interaction):
        async with AsyncSessionLocal() as session:
            self.providers = await ai_config_service.get_all_providers(session)
        self._build_view()
        await _reload_ai_service()
        if self.message:
            await self.message.edit(embed=self._get_embed(), view=self)
