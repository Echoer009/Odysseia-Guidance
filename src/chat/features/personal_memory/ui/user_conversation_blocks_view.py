# -*- coding: utf-8 -*-
"""
用户对话块管理视图 - 允许用户管理自己的对话记忆块

功能：
- 查看自己的对话块列表
- 查看对话块详情
- 选择性删除对话块
- 删除所有对话块

用于"黑衣人的记忆消除器"商品。
"""

import logging
from typing import Any, Mapping, Optional, List

import discord

from src.chat.features.personal_memory.services.conversation_block_service import (
    conversation_block_service,
    format_time_description,
)

log = logging.getLogger(__name__)


class UserConversationBlocksView(discord.ui.View):
    """用户对话块管理视图 - 允许用户查看和删除自己的对话块"""

    def __init__(
        self,
        user_id: int,
        message: discord.Message,
        on_complete_callback=None,
    ):
        """
        初始化视图。

        Args:
            user_id: 用户 Discord ID
            message: Discord 消息对象，用于更新视图
            on_complete_callback: 完成后的回调函数（可选）
        """
        super().__init__(timeout=300)
        self.user_id = str(user_id)
        self.discord_user_id = user_id
        self.message = message
        self.on_complete_callback = on_complete_callback
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = 1
        self.current_list_items: List[Any] = []
        self.current_item_id: Optional[str] = None
        self.view_mode = "list"  # "list" or "detail"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """确保只有用户本人可以操作这个视图"""
        if interaction.user.id != self.discord_user_id:
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
        try:
            blocks = await conversation_block_service.get_user_blocks(self.user_id)
            self.current_list_items = blocks
            self.total_pages = max(
                1,
                (len(self.current_list_items) + self.items_per_page - 1)
                // self.items_per_page,
            )
        except Exception as e:
            log.error(f"加载用户 {self.user_id} 的对话块失败: {e}", exc_info=True)
            self.current_list_items = []
            self.total_pages = 1

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
            title="💬 我的对话记忆",
            description="选择你想要删除的对话记忆块",
            color=discord.Color.purple(),
        )

        if not self.current_list_items:
            embed.description = "你目前没有任何对话记忆块。"
        else:
            start_idx = self.current_page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_items = self.current_list_items[start_idx:end_idx]

            list_text = []
            for item in page_items:
                title = self._get_entry_title(item)
                item_id = item.get("id")
                list_text.append(f"**`#{item_id}`** - {title}")

            embed.description = "选择你想要删除的对话记忆块：\n\n" + "\n".join(
                list_text
            )

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
            title=f"💬 对话记忆详情 #{self.current_item_id}",
            description="确认要删除这个对话记忆吗？",
            color=discord.Color.orange(),
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
                label="删除所有记忆",
                emoji="🗑️",
                style=discord.ButtonStyle.danger,
                row=2,
            )
            delete_all_button.callback = self.confirm_delete_all
            self.add_item(delete_all_button)

        # 仅清除个人印象按钮
        clear_impression_button = discord.ui.Button(
            label="仅清除个人印象",
            emoji="🧹",
            style=discord.ButtonStyle.secondary,
            row=2,
        )
        clear_impression_button.callback = self.confirm_clear_impression
        self.add_item(clear_impression_button)

        # 完成按钮
        done_button = discord.ui.Button(
            label="完成", emoji="✅", style=discord.ButtonStyle.success, row=3
        )
        done_button.callback = self.done
        self.add_item(done_button)

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
            label="删除此记忆", emoji="🗑️", style=discord.ButtonStyle.danger, row=0
        )
        delete_button.callback = self.confirm_delete_current
        self.add_item(delete_button)

        # 返回列表
        back_to_list_button = discord.ui.Button(
            label="返回列表", emoji="📋", style=discord.ButtonStyle.primary, row=1
        )
        back_to_list_button.callback = self.back_to_list
        self.add_item(back_to_list_button)

    def _create_block_select(self) -> discord.ui.Select:
        """创建对话块选择下拉菜单"""
        options = []
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.current_list_items[start_idx:end_idx]

        for item in page_items:
            item_id = item.get("id")
            title = self._get_entry_title(item)
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
            placeholder="选择一个对话记忆查看详情...",
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
            title=f"📄 对话记忆 #{self.current_item_id} 原始文本",
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
                if self.current_item_id is None:
                    await interaction.followup.send(
                        "❌ 无法删除：未选择对话块。",
                        ephemeral=True,
                    )
                    return
                deleted = await conversation_block_service.delete_block_by_id(
                    int(self.current_item_id)
                )
                if deleted:
                    log.info(
                        f"用户 {self.user_id} 删除了对话块 #{self.current_item_id}"
                    )
                    await interaction.followup.send(
                        f"✅ 已成功删除对话记忆 **#{self.current_item_id}**。",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        "❌ 删除失败：对话块不存在或无权删除。",
                        ephemeral=True,
                    )

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
            f"**⚠️ 确认操作**\n你确定要永久删除对话记忆 **#{self.current_item_id}** 吗？此操作无法撤销。",
            view=confirm_view,
            ephemeral=True,
        )

    async def confirm_delete_all(self, interaction: discord.Interaction):
        """确认删除所有对话块和个人印象"""
        block_count = len(self.current_list_items)
        if block_count == 0:
            await interaction.response.send_message(
                "你没有对话记忆可删除。", ephemeral=True
            )
            return

        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                # 删除所有对话块
                deleted_count = await conversation_block_service.delete_all_user_blocks(
                    self.user_id
                )

                # 同时清除个人印象（第一层记忆）
                from src.chat.features.personal_memory.services.personal_memory_service import (
                    personal_memory_service,
                )

                await personal_memory_service.clear_personal_memory(int(self.user_id))

                log.info(
                    f"用户 {self.user_id} 删除了所有 {deleted_count} 个对话块，并清除了个人印象。"
                )
                await interaction.followup.send(
                    f"✅ 已成功删除你的 {deleted_count} 个对话记忆，并清除了类脑娘对你的印象。\n"
                    f"你们可以重新开始了！",
                    ephemeral=True,
                )

                # 返回列表视图
                await self._load_user_blocks()
                self.view_mode = "list"
                self.current_page = 0
                self._initialize_components()
                await self.update_view()

            except Exception as e:
                log.error(f"删除用户记忆失败: {e}", exc_info=True)
                await interaction.followup.send(f"❌ 删除失败: {e}", ephemeral=True)

        async def cancel_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(content="操作已取消。", view=None)

        confirm_button = discord.ui.Button(
            label="确认删除全部", style=discord.ButtonStyle.danger
        )
        confirm_button.callback = confirm_callback
        cancel_button = discord.ui.Button(
            label="取消", style=discord.ButtonStyle.secondary
        )
        cancel_button.callback = cancel_callback
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        await interaction.response.send_message(
            f"**⚠️ 确认操作**\n"
            f"你确定要永久删除所有 **{block_count}** 个对话记忆，并清除类脑娘对你的印象吗？\n"
            f"这将删除所有三层记忆，此操作无法撤销。",
            view=confirm_view,
            ephemeral=True,
        )

    async def confirm_clear_impression(self, interaction: discord.Interaction):
        """确认仅清除个人印象（第一层记忆）"""
        confirm_view = discord.ui.View(timeout=60)

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                # 仅清除个人印象（第一层记忆）
                from src.chat.features.personal_memory.services.personal_memory_service import (
                    personal_memory_service,
                )

                await personal_memory_service.clear_personal_memory(int(self.user_id))

                log.info(f"用户 {self.user_id} 清除了个人印象。")
                await interaction.followup.send(
                    "✅ 已成功清除类脑娘对你的印象。\n"
                    "对话记忆（第二层）保留不变，但她会忘记对你的整体印象。",
                    ephemeral=True,
                )

            except Exception as e:
                log.error(f"清除个人印象失败: {e}", exc_info=True)
                await interaction.followup.send(f"❌ 清除失败: {e}", ephemeral=True)

        async def cancel_callback(interaction: discord.Interaction):
            await interaction.response.edit_message(content="操作已取消。", view=None)

        confirm_button = discord.ui.Button(
            label="确认清除", style=discord.ButtonStyle.danger
        )
        confirm_button.callback = confirm_callback
        cancel_button = discord.ui.Button(
            label="取消", style=discord.ButtonStyle.secondary
        )
        cancel_button.callback = cancel_callback
        confirm_view.add_item(confirm_button)
        confirm_view.add_item(cancel_button)

        await interaction.response.send_message(
            "**⚠️ 确认操作**\n"
            "你确定要清除类脑娘对你的**个人印象**吗？\n"
            "这只会删除第一层记忆（她对你的整体印象），对话记录将保留。\n"
            "此操作无法撤销。",
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

    async def done(self, interaction: discord.Interaction):
        """完成操作"""
        await interaction.response.defer()

        # 调用完成回调（如果有）
        if self.on_complete_callback:
            try:
                await self.on_complete_callback()
            except Exception as e:
                log.error(f"完成回调失败: {e}", exc_info=True)

        # 禁用所有组件
        for item in self.children:
            if isinstance(item, discord.ui.Button | discord.ui.Select):
                item.disabled = True

        embed = discord.Embed(
            title="✅ 操作完成",
            description="对话记忆管理面板已关闭。",
            color=discord.Color.green(),
        )
        await self.message.edit(embed=embed, view=self)
        self.stop()

    async def on_timeout(self):
        """超时处理"""
        try:
            # 禁用所有组件
            for item in self.children:
                if isinstance(item, discord.ui.Button | discord.ui.Select):
                    item.disabled = True

            embed = discord.Embed(
                title="⏰ 操作超时",
                description="对话记忆管理面板已超时关闭。",
                color=discord.Color.greyple(),
            )
            await self.message.edit(embed=embed, view=self)
        except Exception as e:
            log.debug(f"超时处理失败: {e}")
