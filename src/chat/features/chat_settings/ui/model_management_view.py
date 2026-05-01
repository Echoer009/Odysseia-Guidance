# -*- coding: utf-8 -*-
"""
Model 管理视图

通过 Discord UI 管理 AI Model 的添加、编辑、删除。
每个 Model 关联到一个 Provider。
"""

import discord
from discord.ui import View, Button, Select, Modal, TextInput
from discord import ButtonStyle, SelectOption, Interaction
from typing import Optional, Callable, Awaitable, List, Dict, Any

from src.database.database import AsyncSessionLocal
from src.database.services.ai_config_service import ai_config_service
from src.database.models import AiProvider


async def _reload_ai_service():
    from src.chat.services.ai.service import ai_service
    from src.chat.services.ai.config.models import reload_model_configs_async
    await ai_service.reload_providers()
    await reload_model_configs_async()


DEFAULT_GEN_CONFIG = {
    "temperature": 1.0,
    "top_p": 0.95,
    "max_output_tokens": 8192,
}


class AddModelModal(Modal):
    def __init__(
        self,
        providers: List[AiProvider],
        on_save: Callable[[Interaction, dict], Awaitable[None]],
    ):
        super().__init__(title="添加 Model (1/2 基础信息)")
        self.on_save = on_save
        self.providers = providers

        provider_hint = ", ".join([f"{p.name}(id:{p.id})" for p in providers[:3]])
        self.provider_id_input = TextInput(
            label="Provider ID",
            placeholder=f"例: {provider_hint}",
            custom_id="provider_id",
            required=True,
            max_length=10,
        )
        self.add_item(self.provider_id_input)

        self.model_name_input = TextInput(
            label="模型标识(唯一英文ID)",
            placeholder="例: deepseek-chat, gemini-2.5-flash",
            custom_id="model_name",
            required=True,
            max_length=200,
        )
        self.add_item(self.model_name_input)

        self.display_name_input = TextInput(
            label="显示名称",
            placeholder="例: DeepSeek Chat",
            custom_id="display_name",
            required=True,
            max_length=200,
        )
        self.add_item(self.display_name_input)

        self.actual_model_input = TextInput(
            label="实际模型名(API调用)",
            placeholder="通常和模型标识相同",
            custom_id="actual_model",
            required=True,
            max_length=200,
        )
        self.add_item(self.actual_model_input)

        self.description_input = TextInput(
            label="描述(可选)",
            placeholder="模型的简短描述",
            custom_id="description",
            required=False,
            max_length=500,
        )
        self.add_item(self.description_input)

    async def on_submit(self, interaction: Interaction):
        try:
            provider_id = int(self.provider_id_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Provider ID 必须是数字", ephemeral=True
            )
            return

        data = {
            "provider_id": provider_id,
            "model_name": self.model_name_input.value.strip(),
            "display_name": self.display_name_input.value.strip(),
            "actual_model": self.actual_model_input.value.strip(),
            "description": self.description_input.value.strip() or None,
        }
        await interaction.response.send_modal(
            AddModelAbilitiesModal(data=data, on_save=self.on_save)
        )


class AddModelAbilitiesModal(Modal):
    def __init__(
        self,
        data: dict,
        on_save: Callable[[Interaction, dict], Awaitable[None]],
    ):
        super().__init__(title="添加 Model (2/2 能力与参数)")
        self.base_data = data
        self.on_save = on_save

        self.capabilities_input = TextInput(
            label="能力开关 (vision,tools,thinking)",
            placeholder="例: vision=true,tools=true,thinking=false",
            default="vision=true,tools=true,thinking=false",
            custom_id="capabilities",
            required=True,
            max_length=200,
        )
        self.add_item(self.capabilities_input)

        self.max_tokens_input = TextInput(
            label="最大输出 tokens",
            placeholder="例: 8192",
            default="8192",
            custom_id="max_output_tokens",
            required=True,
            max_length=10,
        )
        self.add_item(self.max_tokens_input)

        self.gen_config_input = TextInput(
            label="生成参数 (JSON, 可选)",
            default='{"temperature":1.0,"top_p":0.95,"max_output_tokens":8192}',
            placeholder='{"temperature":1.0,"top_p":0.95,"max_output_tokens":8192}',
            custom_id="gen_config",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )
        self.add_item(self.gen_config_input)

    def _parse_capabilities(self, raw: str) -> dict:
        caps = {"supports_vision": False, "supports_tools": True, "supports_thinking": False}
        for part in raw.split(","):
            part = part.strip().lower()
            if "=" not in part:
                continue
            key, val = part.split("=", 1)
            key = key.strip()
            val = val.strip() == "true"
            if key == "vision":
                caps["supports_vision"] = val
            elif key == "tools":
                caps["supports_tools"] = val
            elif key == "thinking":
                caps["supports_thinking"] = val
        return caps

    async def on_submit(self, interaction: Interaction):
        import json

        caps = self._parse_capabilities(self.capabilities_input.value)

        try:
            max_output_tokens = int(self.max_tokens_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ 最大输出 tokens 必须是数字", ephemeral=True
            )
            return

        gen_config = None
        if self.gen_config_input.value.strip():
            try:
                gen_config = json.loads(self.gen_config_input.value.strip())
            except json.JSONDecodeError:
                await interaction.response.send_message(
                    "❌ 生成参数 JSON 格式错误", ephemeral=True
                )
                return

        self.base_data.update(caps)
        self.base_data["max_output_tokens"] = max_output_tokens
        self.base_data["generation_config"] = gen_config or dict(DEFAULT_GEN_CONFIG)
        await self.on_save(interaction, self.base_data)


class EditModelModal(Modal):
    def __init__(
        self,
        model_name: str,
        display_name: str,
        actual_model: str,
        description: Optional[str],
        gen_config: Optional[Dict[str, Any]],
        supports_vision: bool,
        supports_tools: bool,
        supports_thinking: bool,
        max_output_tokens: int,
        on_save: Callable[[Interaction, dict], Awaitable[None]],
    ):
        super().__init__(title=f"编辑 Model: {model_name}")
        self.on_save = on_save
        self.model_name = model_name

        self.display_name_input = TextInput(
            label="显示名称",
            default=display_name,
            custom_id="display_name",
            required=True,
            max_length=200,
        )
        self.add_item(self.display_name_input)

        self.actual_model_input = TextInput(
            label="实际模型名",
            default=actual_model,
            custom_id="actual_model",
            required=True,
            max_length=200,
        )
        self.add_item(self.actual_model_input)

        vision = "true" if supports_vision else "false"
        tools = "true" if supports_tools else "false"
        thinking = "true" if supports_thinking else "false"
        self.capabilities_input = TextInput(
            label="能力 (vision,tools,thinking)",
            default=f"vision={vision},tools={tools},thinking={thinking}",
            placeholder="vision=true,tools=true,thinking=false",
            custom_id="capabilities",
            required=True,
            max_length=200,
        )
        self.add_item(self.capabilities_input)

        self.params_input = TextInput(
            label="生成参数 (JSON)",
            default=self._gen_config_str(gen_config, max_output_tokens),
            placeholder='{"temperature":1.0,"top_p":0.95,"max_output_tokens":8192}',
            custom_id="params",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )
        self.add_item(self.params_input)

        self.description_input = TextInput(
            label="描述",
            default=description or "",
            custom_id="description",
            required=False,
            max_length=500,
        )
        self.add_item(self.description_input)

    @staticmethod
    def _gen_config_str(gen_config: Optional[Dict[str, Any]], max_tokens: int) -> str:
        import json
        gc = gen_config or {}
        gc.setdefault("temperature", 1.0)
        gc.setdefault("top_p", 0.95)
        gc["max_output_tokens"] = max_tokens
        return json.dumps(gc, ensure_ascii=False)

    def _parse_capabilities(self, raw: str) -> dict:
        caps = {"supports_vision": False, "supports_tools": True, "supports_thinking": False}
        for part in raw.split(","):
            part = part.strip().lower()
            if "=" not in part:
                continue
            key, val = part.split("=", 1)
            key = key.strip()
            val = val.strip() == "true"
            if key == "vision":
                caps["supports_vision"] = val
            elif key == "tools":
                caps["supports_tools"] = val
            elif key == "thinking":
                caps["supports_thinking"] = val
        return caps

    async def on_submit(self, interaction: Interaction):
        import json

        caps = self._parse_capabilities(self.capabilities_input.value)

        gen_config = None
        if self.params_input.value.strip():
            try:
                gen_config = json.loads(self.params_input.value.strip())
            except json.JSONDecodeError:
                await interaction.response.send_message(
                    "❌ 生成参数 JSON 格式错误", ephemeral=True
                )
                return

        data = {
            "model_name": self.model_name,
            "display_name": self.display_name_input.value.strip(),
            "actual_model": self.actual_model_input.value.strip(),
            "description": self.description_input.value.strip() or None,
            "generation_config": gen_config,
        }
        data.update(caps)
        await self.on_save(interaction, data)


class ModelManagementView(View):
    def __init__(
        self,
        on_back_callback: Callable[[Interaction], Awaitable[None]],
    ):
        super().__init__(timeout=300)
        self.on_back_callback = on_back_callback
        self.models: list = []
        self.providers: List[AiProvider] = []
        self.selected_model_id: Optional[int] = None
        self.message: Optional[discord.Message] = None

    async def _initialize(self):
        async with AsyncSessionLocal() as session:
            self.models = await ai_config_service.get_all_models(session)
            self.providers = await ai_config_service.get_all_providers(session)
        self._build_view()

    @classmethod
    async def create(
        cls, on_back_callback: Callable[[Interaction], Awaitable[None]]
    ) -> "ModelManagementView":
        view = cls(on_back_callback)
        await view._initialize()
        return view

    def _build_view(self):
        self.clear_items()

        if self.models:
            options = []
            for m in self.models[:25]:
                status = "✅" if m.enabled else "❌"
                provider_name = m.provider.name if m.provider else "?"
                options.append(
                    SelectOption(
                        label=f"{status} {m.display_name} ({m.model_name})",
                        description=f"Provider: {provider_name} | 实际模型: {m.actual_model}",
                        value=str(m.id),
                        default=self.selected_model_id == m.id,
                    )
                )
            model_select = Select(
                placeholder="选择一个 Model...",
                options=options,
                custom_id="model_select",
                row=0,
            )
            model_select.callback = self._on_model_select
            self.add_item(model_select)

        add_button = Button(
            label="➕ 添加 Model",
            style=ButtonStyle.success,
            custom_id="add_model",
            row=1,
        )
        add_button.callback = self._on_add
        self.add_item(add_button)

        if self.selected_model_id:
            edit_button = Button(
                label="✏️ 编辑",
                style=ButtonStyle.primary,
                custom_id="edit_model",
                row=1,
            )
            edit_button.callback = self._on_edit
            self.add_item(edit_button)

            toggle_button = Button(
                label="🔄 启/禁用",
                style=ButtonStyle.secondary,
                custom_id="toggle_model",
                row=1,
            )
            toggle_button.callback = self._on_toggle
            self.add_item(toggle_button)

            delete_button = Button(
                label="🗑️ 删除",
                style=ButtonStyle.danger,
                custom_id="delete_model",
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
            title="🤖 Model 管理",
            description="管理 AI 模型。添加、编辑或删除模型。\n\n"
            "每个 Model 必须关联到一个 Provider。",
            color=discord.Color.purple(),
        )

        if not self.providers:
            embed.add_field(
                name="⚠️ 请先添加 Provider",
                value="当前没有任何 Provider，请先到 Provider 管理页面添加。",
                inline=False,
            )
            return embed

        provider_hint = "\n".join(
            [f"• **{p.display_name}** (ID: `{p.id}`, 类型: `{p.provider_type}`)" for p in self.providers[:10]]
        )
        embed.add_field(
            name=f"可用 Provider ({len(self.providers)})",
            value=provider_hint,
            inline=False,
        )

        if self.models:
            lines = []
            for m in self.models[:15]:
                status = "✅" if m.enabled else "❌"
                provider_name = m.provider.name if m.provider else "?"
                gen = m.generation_config or {}
                temp = gen.get("temperature", "?")
                vision = "👁" if m.supports_vision else ""
                tools = "🔧" if m.supports_tools else ""
                thinking = "💭" if m.supports_thinking else ""
                caps = " ".join(filter(None, [vision, tools, thinking])) or "—"
                lines.append(
                    f"{status} **{m.display_name}** (`{m.model_name}`)\n"
                    f"  Provider: `{provider_name}` | 实际: `{m.actual_model}` | temp={temp} | {caps}"
                )
            embed.add_field(
                name=f"已配置 Model ({len(self.models)})",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="暂无 Model",
                value='点击下方「➕ 添加 Model」按钮添加。',
                inline=False,
            )

        return embed

    async def _on_model_select(self, interaction: Interaction):
        select = [i for i in self.children if isinstance(i, Select)][0]
        self.selected_model_id = int(select.values[0])
        self._build_view()
        await interaction.response.edit_message(embed=self._get_embed(), view=self)

    async def _on_add(self, interaction: Interaction):
        if not self.providers:
            await interaction.response.send_message(
                "❌ 请先添加至少一个 Provider", ephemeral=True
            )
            return

        async def on_save(save_interaction: Interaction, data: dict):
            async with AsyncSessionLocal() as session:
                existing = await ai_config_service.get_model_by_name(
                    session, data["model_name"]
                )
                if existing:
                    await save_interaction.response.send_message(
                        f"❌ Model `{data['model_name']}` 已存在", ephemeral=True
                    )
                    return

                provider_id = data["provider_id"]
                valid_ids = [p.id for p in self.providers]
                if provider_id not in valid_ids:
                    await save_interaction.response.send_message(
                        f"❌ Provider ID `{provider_id}` 不存在。可用: {valid_ids}",
                        ephemeral=True,
                    )
                    return

                await ai_config_service.create_model(
                    session,
                    model_name=data["model_name"],
                    display_name=data["display_name"],
                    provider_id=provider_id,
                    actual_model=data["actual_model"],
                    description=data.get("description"),
                    supports_vision=data.get("supports_vision", False),
                    supports_tools=data.get("supports_tools", True),
                    supports_thinking=data.get("supports_thinking", False),
                    max_output_tokens=data.get("max_output_tokens", 8192),
                    generation_config=data.get("generation_config", dict(DEFAULT_GEN_CONFIG)),
                )
            await save_interaction.response.send_message(
                f"✅ Model `{data['model_name']}` 添加成功！", ephemeral=True
            )
            await self._refresh(save_interaction)

        modal = AddModelModal(self.providers, on_save)
        await interaction.response.send_modal(modal)

    async def _on_edit(self, interaction: Interaction):
        if not self.selected_model_id:
            return

        async with AsyncSessionLocal() as session:
            from sqlalchemy.future import select
            from src.database.models import AiModel
            from sqlalchemy.orm import selectinload

            stmt = (
                select(AiModel)
                .options(selectinload(AiModel.provider))
                .where(AiModel.id == self.selected_model_id)
            )
            result = await session.execute(stmt)
            model = result.scalars().unique().first()

        if not model:
            await interaction.response.send_message("Model 不存在", ephemeral=True)
            return

        async def on_save(save_interaction: Interaction, data: dict):
            if not self.selected_model_id:
                return
            async with AsyncSessionLocal() as session:
                kwargs = {
                    "display_name": data["display_name"],
                    "actual_model": data["actual_model"],
                    "description": data.get("description"),
                    "supports_vision": data.get("supports_vision", False),
                    "supports_tools": data.get("supports_tools", True),
                    "supports_thinking": data.get("supports_thinking", False),
                }
                if data.get("generation_config") is not None:
                    kwargs["generation_config"] = data["generation_config"]
                await ai_config_service.update_model(
                    session, self.selected_model_id, **kwargs
                )
            await save_interaction.response.send_message(
                f"✅ Model `{data['model_name']}` 已更新！", ephemeral=True
            )
            await self._refresh(save_interaction)

        modal = EditModelModal(
            model_name=model.model_name,
            display_name=model.display_name,
            actual_model=model.actual_model,
            description=model.description,
            gen_config=model.generation_config,
            supports_vision=bool(model.supports_vision),
            supports_tools=bool(model.supports_tools),
            supports_thinking=bool(model.supports_thinking),
            max_output_tokens=model.max_output_tokens or 8192,
            on_save=on_save,
        )
        await interaction.response.send_modal(modal)

    async def _on_toggle(self, interaction: Interaction):
        if not self.selected_model_id:
            return

        async with AsyncSessionLocal() as session:
            from sqlalchemy.future import select
            from src.database.models import AiModel

            stmt = select(AiModel).where(AiModel.id == self.selected_model_id)
            result = await session.execute(stmt)
            model = result.scalars().first()
            if model:
                new_enabled = 0 if model.enabled else 1
                await ai_config_service.update_model(
                    session, self.selected_model_id, enabled=new_enabled
                )

        await interaction.response.defer()
        await self._refresh(interaction)

    async def _on_delete(self, interaction: Interaction):
        if not self.selected_model_id:
            return

        async with AsyncSessionLocal() as session:
            await ai_config_service.delete_model(session, self.selected_model_id)
        self.selected_model_id = None

        await interaction.response.defer()
        await self._refresh(interaction)

    async def _on_back(self, interaction: Interaction):
        self.stop()
        await self.on_back_callback(interaction)

    async def _refresh(self, interaction: Interaction):
        async with AsyncSessionLocal() as session:
            self.models = await ai_config_service.get_all_models(session)
            self.providers = await ai_config_service.get_all_providers(session)
        self._build_view()
        await _reload_ai_service()
        if self.message:
            await self.message.edit(embed=self._get_embed(), view=self)
