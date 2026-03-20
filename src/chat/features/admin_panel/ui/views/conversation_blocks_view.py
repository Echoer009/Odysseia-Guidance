# -*- coding: utf-8 -*-
"""
对话块管理视图 - 管理用户的对话记忆块

功能：
- UserConversationBlocksView: 单个用户的对话块管理（从用户详情页进入）
- ConversationBlocksView: 全局对话块管理（管理员视图）
"""

import logging
from typing import Any, Mapping, Optional, List

import discord

from src.chat.features.admin_panel.services import db_services
from src.chat.features.admin_panel.ui.views.base_view import BaseTableView
from src.chat.features.personal_memory.services.conversation_block_service import (
    format_time_description,
)

log = logging.getLogger(__name__)


# --- 用户级别对话块管理视图 ---


class UserConversationBlocksView(discord.ui.View):
    """单个用户的对话块管理视图 - 从用户详情页进入"""

    def __init__(
        self,
        author_id: int,
        message: discord.Message,
        parent_view: BaseTableView,
        user_id: str,
        user_name: str,
    ):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.message = message
        self.parent_view = parent_view
        self.user_id = user_id
        self.user_name = user_name
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = 1
        self.current_list_items: List[Any] = []
        self.current_item_id: Optional[str] = None
        self.view_mode = "list"  # "list" or "detail"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "你不能操作这个视图。", ephemeral=True
            )
            return False
        return True

    async def initialize(self):
        """初始化视图，加载用户对话块数据"""
        await self._load_user_blocks()
        self._initialize_components()

    async def _load_user_blocks(self):
        """加载该用户的对话块"""
        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = db_services.get_cursor(conn)
            cursor.execute(
                "SELECT * FROM conversation.conversation_blocks WHERE discord_id = %s ORDER BY start_time DESC",
                (self.user_id,),
            )
            self.current_list_items = cursor.fetchall()
            self.total_pages = max(
                1,
                (len(self.current_list_items) + self.items_per_page - 1)
                // self.items_per_page,
            )
        finally:
            if conn:
                conn.close()

    def _get_db_connection(self):
        """获取数据库连接"""
        from src.chat.features.admin_panel.services.db_services import (
            get_parade_db_connection,
        )

        return get_parade_db_connection()

    def _get_entry_title(self, entry: Mapping[str, Any]) -> str:
        """获取对话块的标题显示"""
        try:
            message_count = entry.get("message_count", 0)
            start_time = entry.get("start_time")

            if start_time:
                from datetime import datetime

                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(
                        start_time.replace("Z", "+00:00")
                    )
                time_desc = format_time_description(start_time, start_time)
            else:
                time_desc = "未知时间"

            return f"{time_desc} ({message_count}条)"
        except Exception as e:
            log.debug(f"获取对话块标题失败: {e}")
            return f"ID: #{entry.get('id', 'N/A')}"

    async def update_view(self):
        """更新视图显示"""
        embed = await self._build_embed()
        await self.message.edit(embed=embed, view=self)

    async def _build_embed(self) -> discord.Embed:
        """构建当前视图的 Embed"""
        if self.view_mode == "detail":
            return await self._build_detail_embed()
        return await self._build_list_embed()

    async def _build_list_embed(self) -> discord.Embed:
        """构建列表视图 Embed"""
        embed = discord.Embed(
            title=f"💬 {self.user_name} 的对话块",
            description=f"用户 ID: `{self.user_id}`",
            color=discord.Color.blue(),
        )

        if not self.current_list_items:
            embed.description = f"用户 ID: `{self.user_id}`\n\n该用户暂无对话块记录。"
        else:
            start_idx = self.current_page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_items = self.current_list_items[start_idx:end_idx]

            list_text = []
            for item in page_items:
                title = self._get_entry_title(dict(item))
                item_id = item.get("id")
                # 向量状态
                bge_status = "🟢" if item.get("bge_embedding") else "⚫"
                qwen_status = "🔵" if item.get("qwen_embedding") else "⚫"
                list_text.append(
                    f"**`#{item_id}`** - {title} {bge_status}{qwen_status}"
                )

            embed.description = f"用户 ID: `{self.user_id}`\n\n" + "\n".join(list_text)

        embed.set_footer(
            text=f"第 {self.current_page + 1} / {self.total_pages} 页 | 共 {len(self.current_list_items)} 个对话块"
        )
        return embed

    async def _build_detail_embed(self) -> discord.Embed:
        """构建详情视图 Embed"""
        if not self.current_item_id:
            return await self._build_list_embed()

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            self.view_mode = "list"
            return await self._build_list_embed()

        embed = discord.Embed(
            title=f"💬 对话块详情 #{self.current_item_id}",
            description=f"用户: {self.user_name} (`{self.user_id}`)",
            color=discord.Color.blue(),
        )

        # 基本信息
        message_count = current_item.get("message_count", 0)
        start_time = current_item.get("start_time")
        end_time = current_item.get("end_time")

        embed.add_field(
            name="📊 基本信息",
            value=f"消息数量: **{message_count}**\n"
            f"开始时间: `{start_time}`\n"
            f"结束时间: `{end_time}`",
            inline=False,
        )

        # 向量嵌入状态
        bge_status = "✅ 已生成" if current_item.get("bge_embedding") else "❌ 未生成"
        qwen_status = "✅ 已生成" if current_item.get("qwen_embedding") else "❌ 未生成"
        embed.add_field(
            name="🧠 向量嵌入",
            value=f"🟢 BGE: {bge_status}\n🔵 Qwen: {qwen_status}",
            inline=False,
        )

        # 对话内容预览
        conversation_text = current_item.get("conversation_text", "")
        preview = (
            conversation_text[:500] + "..."
            if len(conversation_text) > 500
            else conversation_text
        )
        embed.add_field(
            name="💬 对话预览",
            value=f"```\n{preview}\n```",
            inline=False,
        )

        return embed

    def _get_item_by_id(self, item_id: str) -> Optional[Any]:
        """根据 ID 获取对话块"""
        for item in self.current_list_items:
            if str(item.get("id")) == str(item_id):
                return item
        return None

    def _initialize_components(self):
        """初始化 UI 组件"""
        self.clear_items()

        if self.view_mode == "list":
            self._add_list_components()
        else:
            self._add_detail_components()

    def _add_list_components(self):
        """添加列表视图组件"""
        # 分页按钮
        if self.total_pages > 1:
            prev_button = discord.ui.Button(
                label="上一页", emoji="⬅️", style=discord.ButtonStyle.secondary, row=0
            )
            prev_button.callback = self.prev_page
            self.add_item(prev_button)

            next_button = discord.ui.Button(
                label="下一页", emoji="➡️", style=discord.ButtonStyle.secondary, row=0
            )
            next_button.callback = self.next_page
            self.add_item(next_button)

        # 选择对话块下拉菜单
        if self.current_list_items:
            select = self._create_block_select()
            self.add_item(select)

        # 删除所有对话块按钮
        if self.current_list_items:
            delete_all_button = discord.ui.Button(
                label="删除所有对话块",
                emoji="🗑️",
                style=discord.ButtonStyle.danger,
                row=2,
            )
            delete_all_button.callback = self.confirm_delete_all
            self.add_item(delete_all_button)

        # 返回按钮
        back_button = discord.ui.Button(
            label="返回用户详情", emoji="↩️", style=discord.ButtonStyle.primary, row=3
        )
        back_button.callback = self.go_back
        self.add_item(back_button)

    def _add_detail_components(self):
        """添加详情视图组件"""
        # 查看原始文本
        view_raw_button = discord.ui.Button(
            label="查看原始文本", emoji="📄", style=discord.ButtonStyle.secondary, row=0
        )
        view_raw_button.callback = self.view_raw_text
        self.add_item(view_raw_button)

        # 删除当前对话块
        delete_button = discord.ui.Button(
            label="删除此对话块", emoji="🗑️", style=discord.ButtonStyle.danger, row=0
        )
        delete_button.callback = self.confirm_delete_current
        self.add_item(delete_button)

        # 返回列表
        back_to_list_button = discord.ui.Button(
            label="返回列表", emoji="📋", style=discord.ButtonStyle.primary, row=1
        )
        back_to_list_button.callback = self.back_to_list
        self.add_item(back_to_list_button)

        # 返回用户详情
        back_button = discord.ui.Button(
            label="返回用户详情", emoji="↩️", style=discord.ButtonStyle.secondary, row=1
        )
        back_button.callback = self.go_back
        self.add_item(back_button)

    def _create_block_select(self) -> discord.ui.Select:
        """创建对话块选择下拉菜单"""
        options = []
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.current_list_items[start_idx:end_idx]

        for item in page_items:
            item_id = item.get("id")
            title = self._get_entry_title(dict(item))
            # 截断过长的标题
            if len(title) > 50:
                title = title[:47] + "..."
            options.append(
                discord.SelectOption(
                    label=f"#{item_id} - {title}",
                    value=str(item_id),
                )
            )

        select = discord.ui.Select(
            placeholder="选择一个对话块查看详情...",
            options=options,
        )
        select.callback = self.on_block_select
        return select

    async def prev_page(self, interaction: discord.Interaction):
        """上一页"""
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            self._initialize_components()
            await self.update_view()

    async def next_page(self, interaction: discord.Interaction):
        """下一页"""
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._initialize_components()
            await self.update_view()

    async def on_block_select(self, interaction: discord.Interaction):
        """选择对话块"""
        await interaction.response.defer()

        selected_value = ""
        if interaction.data and isinstance(interaction.data, dict):
            values = interaction.data.get("values", [])
            if values:
                selected_value = values[0]

        if selected_value:
            self.current_item_id = selected_value
            self.view_mode = "detail"
            self._initialize_components()
            await self.update_view()

    async def view_raw_text(self, interaction: discord.Interaction):
        """查看对话块原始文本"""
        if not self.current_item_id:
            return

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            await interaction.response.send_message("找不到该对话块。", ephemeral=True)
            return

        conversation_text = current_item.get("conversation_text", "")

        # 截断过长的文本
        if len(conversation_text) > 1900:
            conversation_text = conversation_text[:1900] + "\n... (已截断)"

        embed = discord.Embed(
            title=f"📄 对话块 #{self.current_item_id} 原始文本",
            description=f"```\n{conversation_text}\n```",
            color=discord.Color.greyple(),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def confirm_delete_current(self, interaction: discord.Interaction):
        """确认删除当前对话块"""
        if not self.current_item_id:
            return

        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                conn = self._get_db_connection()
                if not conn:
                    await interaction.followup.send("数据库连接失败。", ephemeral=True)
                    return

                try:
                    cursor = db_services.get_cursor(conn)
                    cursor.execute(
                        "DELETE FROM conversation.conversation_blocks WHERE id = %s",
                        (self.current_item_id,),
                    )
                    conn.commit()
                    log.info(
                        f"管理员 {interaction.user.display_name} 删除了对话块 #{self.current_item_id}"
                    )
                    await interaction.followup.send(
                        f"✅ 已成功删除对话块 **#{self.current_item_id}**。",
                        ephemeral=True,
                    )
                finally:
                    if conn:
                        conn.close()

                # 返回列表视图
                await self._load_user_blocks()
                self.view_mode = "list"
                self.current_item_id = None
                self.current_page = 0
                self._initialize_components()
                await self.update_view()

            except Exception as e:
                log.error(f"删除对话块失败: {e}", exc_info=True)
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
            f"**⚠️ 确认操作**\n你确定要永久删除对话块 **#{self.current_item_id}** 吗？此操作无法撤销。",
            view=confirm_view,
            ephemeral=True,
        )

    async def confirm_delete_all(self, interaction: discord.Interaction):
        """确认删除该用户所有对话块"""
        block_count = len(self.current_list_items)
        if block_count == 0:
            await interaction.response.send_message(
                "该用户没有对话块可删除。", ephemeral=True
            )
            return

        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                conn = self._get_db_connection()
                if not conn:
                    await interaction.followup.send("数据库连接失败。", ephemeral=True)
                    return

                try:
                    cursor = db_services.get_cursor(conn)
                    cursor.execute(
                        "DELETE FROM conversation.conversation_blocks WHERE discord_id = %s",
                        (self.user_id,),
                    )
                    conn.commit()
                    log.info(
                        f"管理员 {interaction.user.display_name} 删除了用户 {self.user_name} ({self.user_id}) 的所有 {block_count} 个对话块。"
                    )
                    await interaction.followup.send(
                        f"✅ 已成功删除用户 **{self.user_name}** 的 {block_count} 个对话块。",
                        ephemeral=True,
                    )
                finally:
                    if conn:
                        conn.close()

                # 返回列表视图
                await self._load_user_blocks()
                self.view_mode = "list"
                self.current_page = 0
                self._initialize_components()
                await self.update_view()

            except Exception as e:
                log.error(f"删除用户对话块失败: {e}", exc_info=True)
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
            f"**⚠️ 确认操作**\n你确定要永久删除用户 **{self.user_name}** 的所有 **{block_count}** 个对话块吗？此操作无法撤销。",
            view=confirm_view,
            ephemeral=True,
        )

    async def back_to_list(self, interaction: discord.Interaction):
        """返回列表视图"""
        await interaction.response.defer()
        self.view_mode = "list"
        self.current_item_id = None
        self._initialize_components()
        await self.update_view()

    async def go_back(self, interaction: discord.Interaction):
        """返回用户详情视图"""
        await interaction.response.defer()
        # 恢复父视图
        self.parent_view._initialize_components()
        embed = await self.parent_view._build_embed()
        await self.message.edit(embed=embed, view=self.parent_view)


class ConversationBlocksView(BaseTableView):
    """对话块管理视图"""

    def __init__(
        self, author_id: int, message: discord.Message, parent_view: discord.ui.View
    ):
        super().__init__(author_id, message, parent_view)
        self.current_table = "conversation.conversation_blocks"
        self.db_type = "parade"
        self.items_per_page = 8  # 对话块内容较长，减少每页数量

    def _get_entry_title(self, entry: Mapping[str, Any]) -> str:
        """获取对话块的标题显示"""
        try:
            discord_id = entry.get("discord_id", "N/A")
            message_count = entry.get("message_count", 0)
            start_time = entry.get("start_time")

            # 格式化时间描述
            if start_time:
                from datetime import datetime

                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(
                        start_time.replace("Z", "+00:00")
                    )
                time_desc = format_time_description(start_time, start_time)
            else:
                time_desc = "未知时间"

            return f"用户 {discord_id} - {time_desc} ({message_count}条)"
        except Exception as e:
            log.debug(f"获取对话块标题失败: {e}")
            return f"ID: #{entry.get('id', 'N/A')}"

    def _add_search_buttons(self):
        """添加搜索按钮"""
        # 按用户 ID 搜索
        self.search_user_button = discord.ui.Button(
            label="用户ID搜索",
            emoji="🆔",
            style=discord.ButtonStyle.success,
            row=1,
        )
        self.search_user_button.callback = self.search_by_user_id
        self.add_item(self.search_user_button)

        # 按内容关键词搜索
        if not self.search_mode:
            self.search_content_button = discord.ui.Button(
                label="内容搜索",
                emoji="🔍",
                style=discord.ButtonStyle.primary,
                row=1,
            )
            self.search_content_button.callback = self.search_by_content
            self.add_item(self.search_content_button)

        # 统计按钮
        self.stats_button = discord.ui.Button(
            label="统计信息",
            emoji="📊",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.stats_button.callback = self.show_stats
        self.add_item(self.stats_button)

    def _add_detail_view_components(self):
        """添加详情视图组件"""
        # 调用父类方法添加基本按钮（返回、修改、删除）
        super()._add_detail_view_components()

        # 添加查看原始文本按钮
        self.view_raw_button = discord.ui.Button(
            label="查看原始文本",
            emoji="📄",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        self.view_raw_button.callback = self.view_raw_text
        self.add_item(self.view_raw_button)

        # 添加删除该用户所有对话块按钮
        self.delete_user_blocks_button = discord.ui.Button(
            label="删除该用户所有对话块",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
            row=2,
        )
        self.delete_user_blocks_button.callback = self.confirm_delete_user_blocks
        self.add_item(self.delete_user_blocks_button)

    async def search_by_user_id(self, interaction: discord.Interaction):
        """按用户 ID 搜索对话块"""
        modal = SearchUserBlocksModal(self)
        await interaction.response.send_modal(modal)

    async def search_by_content(self, interaction: discord.Interaction):
        """按内容关键词搜索对话块"""
        modal = SearchContentModal(self)
        await interaction.response.send_modal(modal)

    async def show_stats(self, interaction: discord.Interaction):
        """显示对话块统计信息"""
        await interaction.response.defer()

        conn = self._get_db_connection()
        if not conn:
            await interaction.followup.send("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = db_services.get_cursor(conn)

            # 总对话块数
            cursor.execute("SELECT COUNT(*) FROM conversation.conversation_blocks")
            total_result = cursor.fetchone()
            total_blocks = total_result["count"] if total_result else 0

            # 用户数
            cursor.execute(
                "SELECT COUNT(DISTINCT discord_id) FROM conversation.conversation_blocks"
            )
            users_result = cursor.fetchone()
            total_users = users_result["count"] if users_result else 0

            # 总消息数
            cursor.execute(
                "SELECT SUM(message_count) FROM conversation.conversation_blocks"
            )
            msg_result = cursor.fetchone()
            total_messages = (
                msg_result["sum"] if msg_result and msg_result["sum"] else 0
            )

            # BGE 向量数
            cursor.execute(
                "SELECT COUNT(*) FROM conversation.conversation_blocks WHERE bge_embedding IS NOT NULL"
            )
            bge_result = cursor.fetchone()
            bge_count = bge_result["count"] if bge_result else 0

            # Qwen 向量数
            cursor.execute(
                "SELECT COUNT(*) FROM conversation.conversation_blocks WHERE qwen_embedding IS NOT NULL"
            )
            qwen_result = cursor.fetchone()
            qwen_count = qwen_result["count"] if qwen_result else 0

            # 最早和最新的对话块
            cursor.execute(
                "SELECT MIN(start_time) as oldest, MAX(start_time) as newest FROM conversation.conversation_blocks"
            )
            time_result = cursor.fetchone()
            oldest = time_result["oldest"] if time_result else None
            newest = time_result["newest"] if time_result else None

            # 用户平均对话块数
            avg_blocks = total_blocks / total_users if total_users > 0 else 0

            embed = discord.Embed(
                title="📊 对话块统计信息",
                color=discord.Color.blue(),
            )

            embed.add_field(
                name="📈 总体统计",
                value=f"对话块总数: **{total_blocks}**\n"
                f"用户总数: **{total_users}**\n"
                f"消息总数: **{total_messages}**\n"
                f"平均每人对话块: **{avg_blocks:.1f}**",
                inline=False,
            )

            embed.add_field(
                name="🧠 向量嵌入状态",
                value=f"🟢 BGE: **{bge_count}/{total_blocks}**\n"
                f"🔵 Qwen: **{qwen_count}/{total_blocks}**",
                inline=False,
            )

            time_info = ""
            if oldest:
                time_info += f"最早: {oldest}\n"
            if newest:
                time_info += f"最新: {newest}"
            if time_info:
                embed.add_field(
                    name="⏰ 时间范围",
                    value=time_info,
                    inline=False,
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            log.error(f"获取统计信息失败: {e}", exc_info=True)
            await interaction.followup.send(f"获取统计信息失败: {e}", ephemeral=True)
        finally:
            if conn:
                conn.close()

    async def view_raw_text(self, interaction: discord.Interaction):
        """查看对话块原始文本"""
        if not self.current_item_id:
            return

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            await interaction.response.send_message("找不到该对话块。", ephemeral=True)
            return

        conversation_text = current_item.get("conversation_text", "")

        # 截断过长的文本
        if len(conversation_text) > 1900:
            conversation_text = conversation_text[:1900] + "\n... (已截断)"

        embed = discord.Embed(
            title=f"📄 对话块 #{self.current_item_id} 原始文本",
            description=f"```\n{conversation_text}\n```",
            color=discord.Color.greyple(),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def confirm_delete_user_blocks(self, interaction: discord.Interaction):
        """确认删除该用户所有对话块"""
        if not self.current_item_id:
            return

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            await interaction.response.send_message("找不到该对话块。", ephemeral=True)
            return

        discord_id = current_item.get("discord_id")
        if not discord_id:
            await interaction.response.send_message("无法获取用户 ID。", ephemeral=True)
            return

        # 先查询该用户的对话块数量
        conn = self._get_db_connection()
        if not conn:
            await interaction.response.send_message("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = db_services.get_cursor(conn)
            cursor.execute(
                "SELECT COUNT(*) FROM conversation.conversation_blocks WHERE discord_id = %s",
                (discord_id,),
            )
            count_result = cursor.fetchone()
            block_count = count_result["count"] if count_result else 0
        finally:
            if conn:
                conn.close()

        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                conn = self._get_db_connection()
                if not conn:
                    await interaction.followup.send("数据库连接失败。", ephemeral=True)
                    return

                try:
                    cursor = db_services.get_cursor(conn)
                    cursor.execute(
                        "DELETE FROM conversation.conversation_blocks WHERE discord_id = %s",
                        (discord_id,),
                    )
                    conn.commit()
                    log.info(
                        f"管理员 {interaction.user.display_name} 删除了用户 {discord_id} 的所有 {block_count} 个对话块。"
                    )
                    await interaction.followup.send(
                        f"✅ 已成功删除用户 **{discord_id}** 的 {block_count} 个对话块。",
                        ephemeral=True,
                    )
                finally:
                    if conn:
                        conn.close()

                # 返回列表视图
                self.view_mode = "list"
                await self.update_view()

            except Exception as e:
                log.error(f"删除用户对话块失败: {e}", exc_info=True)
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
            f"**⚠️ 确认操作**\n你确定要永久删除用户 **{discord_id}** 的所有 **{block_count}** 个对话块吗？此操作无法撤销。",
            view=confirm_view,
            ephemeral=True,
        )

    async def edit_item(self, interaction: discord.Interaction):
        """对话块不支持编辑，显示提示"""
        await interaction.response.send_message(
            "对话块不支持编辑操作。如需修改，请删除后重新生成。",
            ephemeral=True,
        )

    def _get_item_by_id(self, item_id: str) -> Optional[Any]:
        """根据 ID 获取对话块"""
        conn = self._get_db_connection()
        if not conn:
            return None
        try:
            cursor = db_services.get_cursor(conn)
            cursor.execute(
                "SELECT * FROM conversation.conversation_blocks WHERE id = %s",
                (item_id,),
            )
            return cursor.fetchone()
        finally:
            if conn:
                conn.close()

    async def _build_list_embed(self) -> discord.Embed:
        """构建列表视图 Embed"""
        conn = self._get_db_connection()
        if not conn:
            return discord.Embed(title="错误", description="数据库连接失败。")

        try:
            cursor = db_services.get_cursor(conn)

            if self.search_mode:
                # 搜索模式
                start_idx = self.current_page * self.items_per_page
                end_idx = start_idx + self.items_per_page
                page_items = self.current_list_items[start_idx:end_idx]

                embed = discord.Embed(
                    title=f"搜索对话块 (关键词: '{self.search_keyword}')",
                    color=discord.Color.gold(),
                )
                self.total_pages = (
                    len(self.current_list_items) + self.items_per_page - 1
                ) // self.items_per_page
            else:
                # 正常浏览模式
                cursor.execute("SELECT COUNT(*) FROM conversation.conversation_blocks")
                count_result = cursor.fetchone()
                total_rows = count_result["count"] if count_result else 0

                self.total_pages = (
                    total_rows + self.items_per_page - 1
                ) // self.items_per_page
                offset = self.current_page * self.items_per_page

                cursor.execute(
                    "SELECT * FROM conversation.conversation_blocks ORDER BY start_time DESC LIMIT %s OFFSET %s",
                    (self.items_per_page, offset),
                )
                page_items = cursor.fetchall()
                self.current_list_items = page_items

                embed = discord.Embed(
                    title="浏览：对话块管理",
                    color=discord.Color.green(),
                )

            if not page_items:
                embed.description = "没有找到任何对话块。"
            else:
                list_text = []
                for item in page_items:
                    title = self._get_entry_title(dict(item))
                    item_id = item.get("id")
                    list_text.append(f"**`#{item_id}`** - {title}")

                embed.description = "\n".join(list_text)

            total_display = (
                f"(共 {len(self.current_list_items)} 条结果)"
                if self.search_mode
                else f"(共 {total_rows} 条记录)"
            )
            embed.set_footer(
                text=f"第 {self.current_page + 1} / {self.total_pages or 1} 页 {total_display}"
            )
            return embed

        finally:
            if conn:
                conn.close()

    async def _build_detail_embed(self) -> discord.Embed:
        """构建详情视图 Embed"""
        if not self.current_item_id:
            return await self._build_list_embed()

        current_item = self._get_item_by_id(self.current_item_id)
        if not current_item:
            self.view_mode = "list"
            return await self._build_list_embed()

        discord_id = current_item.get("discord_id", "N/A")
        embed = discord.Embed(
            title=f"对话块详情 #{self.current_item_id}",
            description=f"用户: `{discord_id}`",
            color=discord.Color.blue(),
        )

        # 基本信息
        message_count = current_item.get("message_count", 0)
        start_time = current_item.get("start_time")
        end_time = current_item.get("end_time")

        embed.add_field(
            name="📊 基本信息",
            value=f"消息数量: **{message_count}**\n"
            f"开始时间: `{start_time}`\n"
            f"结束时间: `{end_time}`",
            inline=False,
        )

        # 向量嵌入状态
        bge_status = "✅ 已生成" if current_item.get("bge_embedding") else "❌ 未生成"
        qwen_status = "✅ 已生成" if current_item.get("qwen_embedding") else "❌ 未生成"
        embed.add_field(
            name="🧠 向量嵌入",
            value=f"🟢 BGE: {bge_status}\n🔵 Qwen: {qwen_status}",
            inline=False,
        )

        # 对话内容预览
        conversation_text = current_item.get("conversation_text", "")
        preview = (
            conversation_text[:500] + "..."
            if len(conversation_text) > 500
            else conversation_text
        )
        embed.add_field(
            name="💬 对话预览",
            value=f"```\n{preview}\n```",
            inline=False,
        )

        # 时间戳
        created_at = current_item.get("created_at")
        updated_at = current_item.get("updated_at")
        if created_at or updated_at:
            embed.set_footer(text=f"创建: {created_at} | 更新: {updated_at}")

        return embed


# --- 搜索模态框 ---


class SearchUserBlocksModal(discord.ui.Modal, title="按用户 ID 搜索对话块"):
    """按用户 ID 搜索对话块的模态框"""

    user_id_input = discord.ui.TextInput(
        label="用户 Discord ID",
        placeholder="输入用户的 Discord ID",
        required=True,
        max_length=50,
    )

    def __init__(self, parent_view: ConversationBlocksView):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = self.user_id_input.value.strip()

        conn = self.parent_view._get_db_connection()
        if not conn:
            await interaction.followup.send("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = db_services.get_cursor(conn)
            cursor.execute(
                "SELECT * FROM conversation.conversation_blocks WHERE discord_id = %s ORDER BY start_time DESC",
                (user_id,),
            )
            results = cursor.fetchall()

            if not results:
                await interaction.followup.send(
                    f"未找到用户 `{user_id}` 的对话块。", ephemeral=True
                )
                return

            self.parent_view.search_mode = True
            self.parent_view.search_keyword = f"用户ID: {user_id}"
            self.parent_view.current_list_items = results
            self.parent_view.current_page = 0
            await self.parent_view.update_view()

        except Exception as e:
            log.error(f"搜索对话块失败: {e}", exc_info=True)
            await interaction.followup.send(f"搜索失败: {e}", ephemeral=True)
        finally:
            if conn:
                conn.close()


class SearchContentModal(discord.ui.Modal, title="按内容搜索对话块"):
    """按内容关键词搜索对话块的模态框"""

    keyword_input = discord.ui.TextInput(
        label="搜索关键词",
        placeholder="输入要搜索的关键词",
        required=True,
        max_length=200,
    )

    def __init__(self, parent_view: ConversationBlocksView):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        keyword = self.keyword_input.value.strip()

        conn = self.parent_view._get_db_connection()
        if not conn:
            await interaction.followup.send("数据库连接失败。", ephemeral=True)
            return

        try:
            cursor = db_services.get_cursor(conn)
            # 使用 ILIKE 进行模糊搜索
            cursor.execute(
                "SELECT * FROM conversation.conversation_blocks WHERE conversation_text ILIKE %s ORDER BY start_time DESC",
                (f"%{keyword}%",),
            )
            results = cursor.fetchall()

            if not results:
                await interaction.followup.send(
                    f"未找到包含关键词 `{keyword}` 的对话块。", ephemeral=True
                )
                return

            self.parent_view.search_mode = True
            self.parent_view.search_keyword = keyword
            self.parent_view.current_list_items = results
            self.parent_view.current_page = 0
            await self.parent_view.update_view()

        except Exception as e:
            log.error(f"搜索对话块失败: {e}", exc_info=True)
            await interaction.followup.send(f"搜索失败: {e}", ephemeral=True)
        finally:
            if conn:
                conn.close()
