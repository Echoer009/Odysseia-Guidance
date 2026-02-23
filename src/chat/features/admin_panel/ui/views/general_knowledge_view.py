# -*- coding: utf-8 -*-

import json
import logging
from typing import Any, Mapping, Optional

import discord

from src.chat.features.admin_panel.services import db_services
from .base_view import BaseTableView
from ..modals.edit_modals import EditModal
from ..modals.search_modals import SearchKnowledgeModal
from src.chat.features.world_book.ui.contribution_modal import (
    WorldBookContributionModal,
)

log = logging.getLogger(__name__)


class GeneralKnowledgeView(BaseTableView):
    def __init__(
        self, author_id: int, message: discord.Message, parent_view: discord.ui.View
    ):
        super().__init__(author_id, message, parent_view)
        self.current_table = "general_knowledge.knowledge_documents"  # 新的表名
        self.db_type = "parade"

    def _get_entry_title(self, entry: Mapping[str, Any]) -> str:
        try:
            # 新表使用 title 字段
            title = entry.get("title")
            if title and str(title).strip():
                return str(title)
            # 如果 title 不存在，使用 id
            return f"ID: #{entry.get('id', 'N/A')}"
        except (KeyError, TypeError):
            # 如果 title 不存在，使用 id
            return f"ID: #{entry.get('id', 'N/A')}"

    def _add_search_buttons(self):
        if not self.search_mode:
            self.search_button = discord.ui.Button(
                label="关键词搜索",
                emoji="🔍",
                style=discord.ButtonStyle.primary,
                row=1,
            )
            self.search_button.callback = self.search_knowledge
            self.add_item(self.search_button)

            # 添加通用知识按钮（管理员免审核直接创建）
            self.add_knowledge_button = discord.ui.Button(
                label="添加知识",
                emoji="📝",
                style=discord.ButtonStyle.success,
                row=1,
            )
            self.add_knowledge_button.callback = self.add_knowledge
            self.add_item(self.add_knowledge_button)

    async def search_knowledge(self, interaction: discord.Interaction):
        modal = SearchKnowledgeModal(self)
        await interaction.response.send_modal(modal)

    async def add_knowledge(self, interaction: discord.Interaction):
        """打开添加通用知识模态框（管理员免审核直接创建）"""
        purchase_info = {"item_id": 0, "price": 0, "is_admin_create": True}
        modal = WorldBookContributionModal(purchase_info)
        await interaction.response.send_modal(modal)

    async def edit_item(self, interaction: discord.Interaction):
        if not self.current_item_id:
            return

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            await interaction.response.send_message("找不到该条目。", ephemeral=True)
            return

        assert self.current_table is not None
        modal = EditModal(self, self.current_table, self.current_item_id, current_item)
        await interaction.response.send_modal(modal)

    def _get_item_by_id(self, item_id: str) -> Optional[Any]:
        conn = self._get_db_connection()
        if not conn:
            return None
        try:
            cursor = db_services.get_cursor(conn)
            # 查询新的表结构：general_knowledge.knowledge_documents，使用 id 列
            cursor.execute(
                "SELECT * FROM general_knowledge.knowledge_documents WHERE id = %s",
                (item_id,),
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
                    title=f"搜索通用知识 (关键词: '{self.search_keyword}')",
                    color=discord.Color.gold(),
                )
            else:
                # 查询新的表结构：general_knowledge.knowledge_documents
                cursor.execute(
                    "SELECT COUNT(*) FROM general_knowledge.knowledge_documents"
                )
                count_result = cursor.fetchone()
                total_rows = count_result["count"] if count_result else 0
                self.total_pages = (
                    total_rows + self.items_per_page - 1
                ) // self.items_per_page
                offset = self.current_page * self.items_per_page
                cursor.execute(
                    "SELECT * FROM general_knowledge.knowledge_documents ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                    (self.items_per_page, offset),
                )
                page_items = cursor.fetchall()
                self.current_list_items = page_items
                embed = discord.Embed(
                    title="浏览：通用知识", color=discord.Color.green()
                )

            if not page_items:
                embed.description = "没有找到任何通用知识。"
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

        title = self._get_entry_title(dict(current_item))
        embed = discord.Embed(
            title=f"查看详情: {title}",
            description=f"表: `general_knowledge.knowledge_documents` | ID: `#{self.current_item_id}`",
            color=discord.Color.blue(),
        )

        def _try_parse_json(data: Any) -> Any:
            if isinstance(data, str):
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    pass
            return data

        # 1. 深度解析 source_metadata
        source_metadata = _try_parse_json(current_item.get("source_metadata"))
        if isinstance(source_metadata, dict) and "content_json" in source_metadata:
            source_metadata["content_json"] = _try_parse_json(
                source_metadata["content_json"]
            )

        # 2. 解析 full_text
        full_text_json = _try_parse_json(current_item.get("full_text"))

        # 3. 构建 Embed
        fields_to_display = {
            "Id": current_item.get("id"),
            "External Id": current_item.get("external_id"),
            "Title": current_item.get("title"),
            "Full Text": f"```json\n{json.dumps(full_text_json, indent=2, ensure_ascii=False)}\n```"
            if isinstance(full_text_json, dict)
            else f"```\n{current_item.get('full_text', '')}\n```",
            "Source Metadata": f"```json\n{json.dumps(source_metadata, indent=2, ensure_ascii=False)}\n```"
            if isinstance(source_metadata, dict)
            else f"```\n{current_item.get('source_metadata', '')}\n```",
            "Created At": current_item.get("created_at"),
            "Updated At": current_item.get("updated_at"),
        }

        for name, value in fields_to_display.items():
            if value is None or str(value).strip() == "":
                value = "_(空)_"

            embed.add_field(
                name=name,
                value=self._truncate_field_value(str(value)),
                inline=False,
            )

        return embed
