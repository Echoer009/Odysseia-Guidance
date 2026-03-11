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
from src.chat.features.community_member.ui.community_member_modal import (
    CommunityMemberUploadModal,
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

        # 添加"创建新名片"按钮（管理员功能）
        self.create_profile_button = discord.ui.Button(
            label="创建新名片", emoji="💳", style=discord.ButtonStyle.success, row=1
        )
        self.create_profile_button.callback = self.add_profile
        self.add_item(self.create_profile_button)

    def _add_detail_view_components(self):
        super()._add_detail_view_components()
        # Row 1
        self.view_memory_button = discord.ui.Button(
            label="查看/编辑记忆", emoji="🧠", style=discord.ButtonStyle.success, row=1
        )
        self.view_memory_button.callback = self.view_memory
        self.add_item(self.view_memory_button)

        # Row 2
        self.reset_memory_button = discord.ui.Button(
            label="重置记忆与历史", emoji="🔄", style=discord.ButtonStyle.danger, row=2
        )
        self.reset_memory_button.callback = self.confirm_reset_memory
        self.add_item(self.reset_memory_button)

        self.delete_history_button = discord.ui.Button(
            label="仅删除历史", emoji="🗑️", style=discord.ButtonStyle.secondary, row=2
        )
        self.delete_history_button.callback = self.confirm_delete_history
        self.add_item(self.delete_history_button)

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

    def _get_current_user_id_and_name(
        self,
    ) -> tuple[Optional[int], Optional[str], Optional[str]]:
        if not self.current_item_id:
            return None, None, None

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item or "discord_id" not in current_item.keys():
            return None, None, None

        discord_id_str = current_item["discord_id"]
        if not discord_id_str:
            return None, None, None

        try:
            user_id = int(discord_id_str)
            member_name = (
                self._get_entry_title(dict(current_item)) or f"ID: {discord_id_str}"
            ).replace("社区成员档案 - ", "")
            return user_id, member_name, discord_id_str
        except (ValueError, TypeError):
            return None, None, None

    async def confirm_reset_memory(self, interaction: discord.Interaction):
        user_id, member_name, discord_id = self._get_current_user_id_and_name()

        if not user_id or not member_name:
            await interaction.response.send_message(
                f"无法从此档案中获取有效的 Discord ID: `{discord_id}`", ephemeral=True
            )
            return

        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                await personal_memory_service.reset_memory_and_delete_history(user_id)
                log.info(
                    f"管理员 {interaction.user.display_name} 重置了用户 {member_name} ({user_id}) 的记忆和历史。"
                )
                await interaction.followup.send(
                    f"✅ 已成功重置用户 **{member_name}** 的记忆和对话历史。",
                    ephemeral=True,
                )
                # Disable buttons on the original message
                for item in confirm_view.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
                await interaction.edit_original_response(view=confirm_view)
            except Exception as e:
                log.error(f"重置用户 {user_id} 记忆失败: {e}", exc_info=True)
                await interaction.followup.send(f"❌ 重置失败: {e}", ephemeral=True)

        async def cancel_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(content="操作已取消。", view=None)

        confirm_button = discord.ui.Button(
            label="确认重置", style=discord.ButtonStyle.danger
        )
        confirm_button.callback = confirm_callback
        cancel_button = discord.ui.Button(
            label="取消", style=discord.ButtonStyle.secondary
        )
        cancel_button.callback = cancel_callback
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        await interaction.response.send_message(
            f"**⚠️ 确认操作**\n你确定要永久重置用户 **{member_name}** 的记忆和对话历史吗？此操作无法撤销。",
            view=confirm_view,
            ephemeral=True,
        )

    async def confirm_delete_history(self, interaction: discord.Interaction):
        user_id, member_name, discord_id = self._get_current_user_id_and_name()

        if not user_id or not member_name:
            await interaction.response.send_message(
                f"无法从此档案中获取有效的 Discord ID: `{discord_id}`", ephemeral=True
            )
            return

        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                await personal_memory_service.delete_conversation_history(user_id)
                log.info(
                    f"管理员 {interaction.user.display_name} 删除了用户 {member_name} ({user_id}) 的历史。"
                )
                await interaction.followup.send(
                    f"✅ 已成功删除用户 **{member_name}** 的对话历史。", ephemeral=True
                )
                for item in confirm_view.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
                await interaction.edit_original_response(view=confirm_view)
            except Exception as e:
                log.error(f"删除用户 {user_id} 历史失败: {e}", exc_info=True)
                await interaction.followup.send(f"❌ 删除失败: {e}", ephemeral=True)

        async def cancel_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(content="操作已取消。", view=None)

        confirm_button = discord.ui.Button(
            label="确认删除", style=discord.ButtonStyle.danger
        )
        confirm_button.callback = confirm_callback
        cancel_button = discord.ui.Button(
            label="取消", style=discord.ButtonStyle.secondary
        )
        cancel_button.callback = cancel_callback
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        await interaction.response.send_message(
            f"**⚠️ 确认操作**\n你确定要永久删除用户 **{member_name}** 的对话历史吗？记忆摘要将不受影响。此操作无法撤销。",
            view=confirm_view,
            ephemeral=True,
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

    async def add_profile(self, interaction: discord.Interaction):
        """打开添加名片模态框（管理员免费创建）"""
        # 管理员创建名片，使用免费的 purchase_info（item_id=0, price=0）
        purchase_info = {"item_id": 0, "price": 0, "is_admin_create": True}
        modal = CommunityMemberUploadModal(purchase_info)
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

                # 查询 member_chunks 表的 embedding 统计
                cursor.execute("SELECT COUNT(*) FROM community.member_chunks")
                chunks_result = cursor.fetchone()
                total_chunks = chunks_result["count"] if chunks_result else 0

                cursor.execute(
                    "SELECT COUNT(*) FROM community.member_chunks WHERE bge_embedding IS NOT NULL"
                )
                bge_result = cursor.fetchone()
                bge_count = bge_result["count"] if bge_result else 0

                cursor.execute(
                    "SELECT COUNT(*) FROM community.member_chunks WHERE qwen_embedding IS NOT NULL"
                )
                qwen_result = cursor.fetchone()
                qwen_count = qwen_result["count"] if qwen_result else 0

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

                # 添加 embedding 统计信息
                embed.add_field(
                    name="📊 Embedding 统计 (Chunks)",
                    value=f"🟢 BGE: {bge_count}/{total_chunks} | 🔵 Qwen: {qwen_count}/{total_chunks}",
                    inline=False,
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

        # 查询该成员的向量统计信息
        conn = self._get_db_connection()
        bge_count = 0
        qwen_count = 0
        total_chunks = 0
        if conn:
            try:
                cursor = db_services.get_cursor(conn)
                # 查询该成员的 chunks 总数
                cursor.execute(
                    "SELECT COUNT(*) FROM community.member_chunks WHERE profile_id = %s",
                    (self.current_item_id,),
                )
                chunks_result = cursor.fetchone()
                total_chunks = chunks_result["count"] if chunks_result else 0

                # 查询该成员的 BGE embedding 数量
                cursor.execute(
                    "SELECT COUNT(*) FROM community.member_chunks WHERE profile_id = %s AND bge_embedding IS NOT NULL",
                    (self.current_item_id,),
                )
                bge_result = cursor.fetchone()
                bge_count = bge_result["count"] if bge_result else 0

                # 查询该成员的 Qwen embedding 数量
                cursor.execute(
                    "SELECT COUNT(*) FROM community.member_chunks WHERE profile_id = %s AND qwen_embedding IS NOT NULL",
                    (self.current_item_id,),
                )
                qwen_result = cursor.fetchone()
                qwen_count = qwen_result["count"] if qwen_result else 0
            finally:
                if conn:
                    conn.close()

        # 添加 Embedding 统计信息到详情页
        embed.add_field(
            name="📊 Embedding 统计 (Chunks)",
            value=f"🟢 BGE: {bge_count}/{total_chunks} | 🔵 Qwen: {qwen_count}/{total_chunks}",
            inline=False,
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
