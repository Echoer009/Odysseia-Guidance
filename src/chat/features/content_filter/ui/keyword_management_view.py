# -*- coding: utf-8 -*-

import logging
from typing import List, Tuple, Optional, Callable, Awaitable

import discord
from discord.ui import View, Button, Modal, TextInput, Select
from discord import ButtonStyle, Interaction, TextStyle

from src.chat.features.content_filter.services.content_filter_service import (
    add_keyword,
    remove_keyword,
    unignore_keyword,
    get_all_keywords_with_status,
)

log = logging.getLogger(__name__)


class AddKeywordModal(Modal, title="添加关键词"):
    keyword_input = TextInput(
        label="输入要添加的关键词",
        placeholder="例如: 涩涩",
        style=TextStyle.short,
        max_length=50,
        required=True,
    )

    def __init__(self, view: "KeywordManagementView"):
        super().__init__()
        self.parent_view = view

    async def on_submit(self, interaction: Interaction):
        keyword = self.keyword_input.value.strip()
        if not keyword:
            await interaction.response.send_message("关键词不能为空", ephemeral=True)
            return

        success = await add_keyword(keyword)
        if not success:
            await interaction.response.send_message(
                f"关键词 `{keyword}` 已存在", ephemeral=True
            )
            return

        await self.parent_view._reload()
        await interaction.response.edit_message(
            embed=self.parent_view._build_embed(), view=self.parent_view
        )
        log.info(f"已添加关键词: {keyword}")


class KeywordManagementView(View):
    def __init__(
        self,
        back_callback: Callable[[Interaction], Awaitable[None]],
        message: Optional[discord.Message] = None,
    ):
        super().__init__(timeout=600)
        self.message = message
        self.back_callback = back_callback
        self._active: List[str] = []
        self._ignored: List[str] = []
        self._show_ignored = False

    @classmethod
    async def create(
        cls,
        back_callback: Callable[[Interaction], Awaitable[None]],
        message: Optional[discord.Message] = None,
    ):
        view = cls(back_callback, message)
        await view._reload()
        return view

    async def _reload(self):
        all_kws = await get_all_keywords_with_status()
        self._active = [kw for kw, ignored in all_kws if not ignored]
        self._ignored = [kw for kw, ignored in all_kws if ignored]
        self._build_items()

    def _build_embed(self) -> discord.Embed:
        if self._show_ignored:
            return self._build_ignored_embed()
        return self._build_active_embed()

    def _build_active_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🛡️ 文爱关键词管理",
            description=f"当前共 **{len(self._active)}** 个活跃关键词，**{len(self._ignored)}** 个已忽略。",
            color=discord.Color.blue(),
        )
        if self._active:
            keyword_list = "\n".join(
                f"• `{kw}`" for kw in sorted(self._active, key=str.lower)
            )
            text = keyword_list[:1024] if len(keyword_list) <= 1024 else keyword_list[:1020] + "..."
            embed.add_field(
                name=f"📋 活跃关键词 ({len(self._active)} 个)",
                value=text,
                inline=False,
            )
        else:
            embed.add_field(
                name="📋 活跃关键词",
                value="暂无活跃关键词",
                inline=False,
            )
        return embed

    def _build_ignored_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🔕 已忽略关键词",
            description=f"以下关键词已被永久忽略，不会再触发警报。\n共 **{len(self._ignored)}** 个已忽略关键词。",
            color=discord.Color.dark_grey(),
        )
        if self._ignored:
            keyword_list = "\n".join(
                f"• `{kw}`" for kw in sorted(self._ignored, key=str.lower)
            )
            text = keyword_list[:1024] if len(keyword_list) <= 1024 else keyword_list[:1020] + "..."
            embed.add_field(
                name=f"🔕 已忽略 ({len(self._ignored)} 个)",
                value=text,
                inline=False,
            )
        else:
            embed.add_field(
                name="🔕 已忽略",
                value="暂无被忽略的关键词",
                inline=False,
            )
        return embed

    def _build_items(self):
        self.clear_items()

        if self._show_ignored:
            if self._ignored:
                self.add_item(
                    Button(
                        label="🔄 恢复关键词",
                        style=ButtonStyle.success,
                        custom_id="unignore_keyword",
                        row=0,
                    )
                )
            self.add_item(
                Button(
                    label="📋 查看活跃",
                    style=ButtonStyle.secondary,
                    custom_id="show_active",
                    row=1,
                )
            )
        else:
            self.add_item(
                Button(
                    label="➕ 添加关键词",
                    style=ButtonStyle.primary,
                    custom_id="add_keyword",
                    row=0,
                )
            )
            if self._active:
                self.add_item(
                    Button(
                        label="➖ 删除关键词",
                        style=ButtonStyle.danger,
                        custom_id="delete_keyword",
                        row=0,
                    )
                )
            if self._ignored:
                self.add_item(
                    Button(
                        label=f"🔕 已忽略 ({len(self._ignored)})",
                        style=ButtonStyle.secondary,
                        custom_id="show_ignored",
                        row=1,
                    )
                )

        self.add_item(
            Button(
                label="↩️ 返回",
                style=ButtonStyle.secondary,
                custom_id="back",
                row=2,
            )
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        custom_id = interaction.data.get("custom_id") if interaction.data else None
        if custom_id == "add_keyword":
            await interaction.response.send_modal(AddKeywordModal(self))
        elif custom_id == "delete_keyword":
            await self._show_delete_select(interaction)
        elif custom_id == "show_ignored":
            self._show_ignored = True
            self._build_items()
            await interaction.response.edit_message(
                embed=self._build_embed(), view=self
            )
        elif custom_id == "show_active":
            self._show_ignored = False
            self._build_items()
            await interaction.response.edit_message(
                embed=self._build_embed(), view=self
            )
        elif custom_id == "unignore_keyword":
            await self._show_unignore_select(interaction)
        elif custom_id == "back":
            await self.back_callback(interaction)
        return True

    async def _show_delete_select(self, interaction: Interaction):
        if not self._active:
            await interaction.response.send_message(
                "没有可删除的关键词", ephemeral=True
            )
            return

        options = [
            discord.SelectOption(label=kw[:100], value=kw, emoji="❌")
            for kw in sorted(self._active, key=str.lower)
        ]

        outer_view = self

        class DeleteSelect(discord.ui.Select):
            def __init__(sel):
                super().__init__(
                    placeholder="选择要删除的关键词...",
                    options=options[:25],
                    min_values=1,
                    max_values=1,
                )

            async def callback(sel, interaction: Interaction):
                await interaction.response.defer()
                kw_to_delete = sel.values[0]
                await remove_keyword(kw_to_delete)
                log.info(f"已删除关键词: {kw_to_delete}")
                await outer_view._reload()
                if outer_view.message:
                    await outer_view.message.edit(
                        embed=outer_view._build_embed(), view=outer_view
                    )
                await interaction.edit_original_response(
                    content="✅ 已删除", view=None
                )

        delete_view = View(timeout=60)
        delete_view.add_item(DeleteSelect())
        await interaction.response.send_message(
            "选择要删除的关键词:", view=delete_view, ephemeral=True
        )

    async def _show_unignore_select(self, interaction: Interaction):
        if not self._ignored:
            await interaction.response.send_message(
                "没有被忽略的关键词", ephemeral=True
            )
            return

        options = [
            discord.SelectOption(label=kw[:100], value=kw, emoji="🔄")
            for kw in sorted(self._ignored, key=str.lower)
        ]

        outer_view = self

        class UnignoreSelect(discord.ui.Select):
            def __init__(sel):
                super().__init__(
                    placeholder="选择要恢复的关键词...",
                    options=options[:25],
                    min_values=1,
                    max_values=1,
                )

            async def callback(sel, interaction: Interaction):
                await interaction.response.defer()
                kw_to_restore = sel.values[0]
                await unignore_keyword(kw_to_restore)
                log.info(f"已恢复关键词: {kw_to_restore}")
                await outer_view._reload()
                if outer_view.message:
                    await outer_view.message.edit(
                        embed=outer_view._build_embed(), view=outer_view
                    )
                await interaction.edit_original_response(
                    content="✅ 已恢复", view=None
                )

        restore_view = View(timeout=60)
        restore_view.add_item(UnignoreSelect())
        await interaction.response.send_message(
            "选择要恢复的关键词:", view=restore_view, ephemeral=True
        )
