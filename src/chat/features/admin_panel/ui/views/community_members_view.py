# -*- coding: utf-8 -*-

import json
import logging
from typing import Any, Mapping, Optional

import discord

from src.chat.features.admin_panel.services import db_services
from src.chat.features.admin_panel.services.profile_formatter import (
    format_member_profile,
)

from .base_view import BaseTableView
from ..modals.edit_modals import EditCommunityMemberModal, EditMemoryModal
from ..modals.search_modals import SearchUserModal, SearchCommunityMemberModal
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)

log = logging.getLogger(__name__)


class CommunityMembersView(BaseTableView):
    def __init__(
        self, author_id: int, message: discord.Message, parent_view: discord.ui.View
    ):
        super().__init__(author_id, message, parent_view)
        self.current_table = "community.member_profiles"
        self.db_type = "parade"

    def _get_entry_title(self, entry: Mapping[str, Any]) -> str:
        try:
            title = entry.get("title")
            if title and str(title).strip():
                return str(title)
            return f"ID: #{entry.get('id', 'N/A')}"
        except (KeyError, TypeError):
            return f"ID: #{entry.get('id', 'N/A')}"

    def _add_search_buttons(self):
        self.search_user_button = discord.ui.Button(
            label="ID搜索", emoji="🆔", style=discord.ButtonStyle.success, row=1
        )
        self.search_user_button.callback = self.search_user
        self.add_item(self.search_user_button)

        if not self.search_mode:
            self.search_member_button = discord.ui.Button(
                label="关键词搜索",
                emoji="🔍",
                style=discord.ButtonStyle.primary,
                row=1,
            )
            self.search_member_button.callback = self.search_community_member
            self.add_item(self.search_member_button)

    def _add_detail_view_components(self):
        super()._add_detail_view_components()
        self.view_memory_button = discord.ui.Button(
            label="查看/编辑记忆", emoji="🧠", style=discord.ButtonStyle.success
        )
        self.view_memory_button.callback = self.view_memory
        self.add_item(self.view_memory_button)

    async def search_user(self, interaction: discord.Interaction):
        modal = SearchUserModal(self)
        await interaction.response.send_modal(modal)

    async def search_community_member(self, interaction: discord.Interaction):
        modal = SearchCommunityMemberModal(self)
        await interaction.response.send_modal(modal)

    async def view_memory(self, interaction: discord.Interaction):
        if not self.current_item_id:
            return

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item or "discord_id" not in current_item.keys():
            await interaction.response.send_message(
                "无法获取该成员的 Discord ID。", ephemeral=True
            )
            return

        discord_id = current_item["discord_id"]
        if not discord_id:
            await interaction.response.send_message(
                "该成员未记录 Discord ID，无法查询记忆。", ephemeral=True
            )
            return

        try:
            user_id = int(discord_id)
            current_summary = await personal_memory_service.get_memory_summary(user_id)
            member_name = (
                self._get_entry_title(dict(current_item)) or f"ID: {discord_id}"
            ).replace("社区成员档案 - ", "")

            modal = EditMemoryModal(self, user_id, member_name, current_summary or "")
            await interaction.response.send_modal(modal)

        except ValueError:
            await interaction.response.send_message(
                f"无效的 Discord ID 格式: `{discord_id}`", ephemeral=True
            )
        except Exception as e:
            log.error(f"打开记忆编辑模态框时出错: {e}", exc_info=True)
            await interaction.response.send_message(
                f"处理请求时发生错误: {e}", ephemeral=True
            )

    async def edit_item(self, interaction: discord.Interaction):
        if not self.current_item_id:
            return

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            await interaction.response.send_message("找不到该条目。", ephemeral=True)
            return

        modal = EditCommunityMemberModal(self, self.current_item_id, current_item)
        await interaction.response.send_modal(modal)

    def _get_item_by_id(self, item_id: str) -> Optional[Any]:
        conn = self._get_db_connection()
        if not conn:
            return None
        try:
            cursor = db_services.get_cursor(conn)
            cursor.execute(
                "SELECT * FROM community.member_profiles WHERE id = %s", (item_id,)
            )
            return cursor.fetchone()
        finally:
            if conn:
                conn.close()

    async def _build_list_embed(self) -> discord.Embed:
        conn = self._get_db_connection()
        if not conn:
            return discord.Embed(title="错误", description="数据库连接失败。")

        try:
            cursor = db_services.get_cursor(conn)
            if self.search_mode:
                start_idx = self.current_page * self.items_per_page
                end_idx = start_idx + self.items_per_page
                page_items = self.current_list_items[start_idx:end_idx]
                embed = discord.Embed(
                    title=f"搜索社区成员 (关键词: '{self.search_keyword}')",
                    color=discord.Color.gold(),
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM community.member_profiles")
                count_result = cursor.fetchone()
                total_rows = count_result["count"] if count_result else 0
                self.total_pages = (
                    total_rows + self.items_per_page - 1
                ) // self.items_per_page
                offset = self.current_page * self.items_per_page
                cursor.execute(
                    "SELECT * FROM community.member_profiles ORDER BY id DESC LIMIT %s OFFSET %s",
                    (self.items_per_page, offset),
                )
                page_items = cursor.fetchall()
                self.current_list_items = page_items
                embed = discord.Embed(
                    title="浏览：社区成员档案", color=discord.Color.green()
                )

            if not page_items:
                embed.description = "没有找到任何社区成员档案。"
            else:
                list_text = "\n".join(
                    [
                        f"**`#{item['id']}`** - {self._get_entry_title(dict(item))}"
                        for item in page_items
                    ]
                )
                embed.description = list_text

            total_display = (
                f"(共 {len(self.current_list_items)} 条结果)"
                if self.search_mode
                else ""
            )
            embed.set_footer(
                text=f"第 {self.current_page + 1} / {self.total_pages or 1} 页 {total_display}"
            )
            return embed
        finally:
            if conn:
                conn.close()

    async def _build_detail_embed(self) -> discord.Embed:
        if not self.current_item_id:
            return await self._build_list_embed()

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            self.view_mode = "list"
            return await self._build_list_embed()

        # 核心修复：调用新的格式化服务来获取规范化的数据
        formatted_data = format_member_profile(current_item)

        # 使用格式化后的数据来构建 Embed
        title = formatted_data["source_metadata"].get("name") or self._get_entry_title(
            dict(current_item)
        )
        embed = discord.Embed(
            title=f"查看详情: {title}",
            description=f"表: `community.member_profiles` | 外部ID: `#{self.current_item_id}`",
            color=discord.Color.blue(),
        )

        # 1. 显示格式化后的 Full Text
        # 将格式化文本中的 "键: 值" 分割，并应用样式
        full_text_lines = formatted_data["full_text"].split("\n")
        styled_full_text_lines = []
        for line in full_text_lines:
            if ": " in line:
                key, value = line.split(": ", 1)
                styled_full_text_lines.append(f"**{key}**: `{value}`")
            else:
                styled_full_text_lines.append(line)

        embed.add_field(
            name="Full Text",
            value=self._truncate_field_value("\n".join(styled_full_text_lines)),
            inline=False,
        )

        # 2. 显示格式化后的 Source Metadata
        formatted_metadata_str = f"```json\n{json.dumps(formatted_data['source_metadata'], indent=2, ensure_ascii=False)}\n```"
        embed.add_field(
            name="Source Metadata",
            value=self._truncate_field_value(formatted_metadata_str),
            inline=False,
        )

        # 3. 显示其他数据库原始元数据以供参考
        other_metadata_to_display = ["id", "external_id", "created_at", "updated_at"]
        for col in other_metadata_to_display:
            if col in current_item:
                value = current_item[col]
                if value is None or str(value).strip() == "":
                    value = "_(空)_"
                embed.add_field(
                    name=col.replace("_", " ").title(),
                    value=f"`{value}`",
                    inline=True,
                )

        return embed
