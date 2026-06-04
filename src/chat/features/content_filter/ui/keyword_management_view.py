# -*- coding: utf-8 -*-

import json
import logging
from typing import List, Optional

import discord
from discord.ui import View, Button, Modal, TextInput
from discord import ButtonStyle, Interaction, TextStyle

from src.chat.utils.database import chat_db_manager
from src.chat.features.content_filter.services.content_filter_service import (
    _invalidate_cache,
    _load_custom_keywords,
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

        current = await _load_custom_keywords()
        if keyword.lower() in [k.lower() for k in current]:
            await interaction.response.send_message(
                f"关键词 `{keyword}` 已存在", ephemeral=True
            )
            return

        current.append(keyword)
        await chat_db_manager.set_global_setting(
            "content_filter_keywords", json.dumps(current, ensure_ascii=False)
        )
        _invalidate_cache()
        self.parent_view._keywords = current
        self.parent_view._create_view_items()
        await interaction.response.edit_message(
            embed=self.parent_view._build_embed(), view=self.parent_view
        )
        log.info(f"已添加关键词: {keyword}")


class KeywordManagementView(View):
    def __init__(
        self,
        back_callback,
        message: Optional[discord.Message] = None,
    ):
        super().__init__(timeout=600)
        self.message = message
        self.back_callback = back_callback
        self._keywords: List[str] = []

    @classmethod
    async def create(cls, back_callback, message: Optional[discord.Message] = None):
        view = cls(back_callback, message)
        view._keywords = await _load_custom_keywords()
        view._create_view_items()
        return view

    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🛡️ 文爱关键词管理",
            description="管理自定义检测关键词。基础关键词不可删除，仅支持追加自定义词。",
            color=discord.Color.blue(),
        )
        if self._keywords:
            keyword_list = "\n".join(
                f"• `{kw}`" for kw in sorted(self._keywords, key=str.lower)
            )
            embed.add_field(
                name=f"📋 自定义关键词 ({len(self._keywords)} 个)",
                value=keyword_list[:1024] if len(keyword_list) <= 1024 else keyword_list[:1020] + "...",
                inline=False,
            )
        else:
            embed.add_field(
                name="📋 自定义关键词",
                value="暂未添加自定义关键词",
                inline=False,
            )
        return embed

    def _create_view_items(self):
        self.clear_items()

        self.add_item(
            Button(
                label="➕ 添加关键词",
                style=ButtonStyle.primary,
                custom_id="add_keyword",
                row=0,
            )
        )

        if self._keywords:
            self.add_item(
                Button(
                    label="➖ 删除关键词",
                    style=ButtonStyle.danger,
                    custom_id="delete_keyword",
                    row=0,
                )
            )

        self.add_item(
            Button(
                label="↩️ 返回",
                style=ButtonStyle.secondary,
                custom_id="back",
                row=1,
            )
        )

    async def _update_view(self, interaction: Interaction):
        self._keywords = await _load_custom_keywords()
        self._create_view_items()
        await interaction.response.edit_message(
            embed=self._build_embed(), view=self
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        custom_id = interaction.data.get("custom_id") if interaction.data else None
        if custom_id == "add_keyword":
            await interaction.response.send_modal(AddKeywordModal(self))
        elif custom_id == "delete_keyword":
            await self._show_delete_select(interaction)
        elif custom_id == "back":
            await interaction.response.defer()
            await self.back_callback(interaction)
        return True

    async def _show_delete_select(self, interaction: Interaction):
        if not self._keywords:
            await interaction.response.send_message(
                "没有可删除的关键词", ephemeral=True
            )
            return

        options = []
        for kw in sorted(self._keywords, key=str.lower):
            options.append(
                discord.SelectOption(label=kw[:100], value=kw, emoji="❌")
            )

        outer_view = self

        class DeleteSelect(discord.ui.Select):
            def __init__(self_):
                super().__init__(
                    placeholder="选择要删除的关键词...",
                    options=options[:25],
                    min_values=1,
                    max_values=1,
                )

            async def callback(self_, interaction: Interaction):
                await interaction.response.defer()
                kw_to_delete = self_.values[0]
                current_kws = await _load_custom_keywords()
                current_kws = [k for k in current_kws if k != kw_to_delete]
                await chat_db_manager.set_global_setting(
                    "content_filter_keywords",
                    json.dumps(current_kws, ensure_ascii=False),
                )
                _invalidate_cache()
                log.info(f"已删除关键词: {kw_to_delete}")
                outer_view._keywords = current_kws
                outer_view._create_view_items()
                await interaction.edit_original_response(
                    embed=outer_view._build_embed(), view=outer_view
                )

        delete_view = View(timeout=60)
        delete_view.add_item(DeleteSelect())
        await interaction.response.send_message(
            "选择要删除的关键词:", view=delete_view, ephemeral=True
        )
