# -*- coding: utf-8 -*-

import discord
from discord.ui import View, Button, Select
from typing import List, Dict, Optional, Any
import uuid

from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.ui.modals.temporary_message_modal import TemporaryMessageModal
from src import config as root_config


class TemporaryMessagesEditView(View):
    """
    一个用于编辑、添加、删除多条临时消息的视图。
    """

    def __init__(
        self,
        parent_interaction: discord.Interaction,
        channel_id: int,
        existing_data: List[Dict[str, Any]],
    ):
        super().__init__(timeout=300)
        self.parent_interaction = parent_interaction
        self.channel_id = channel_id
        # 为每个消息添加一个唯一的内部ID，以便于跟踪
        self.messages = [
            dict(item, internal_id=str(uuid.uuid4())) for item in existing_data
        ]
        self.selected_message_id: Optional[str] = None

        self.create_components()

    def create_components(self):
        """动态创建或更新视图组件。"""
        # 清空现有组件
        self.clear_items()

        # 1. 添加消息选择器
        self.add_item(self.MessageSelect(self.messages, self.selected_message_id))

        # 2. 添加按钮
        self.add_item(self.AddButton())
        self.add_item(self.EditButton(disabled=self.selected_message_id is None))
        self.add_item(self.DeleteButton(disabled=self.selected_message_id is None))
        self.add_item(self.BackButton())

    async def update_view(self, save: bool = False):
        """
        根据当前状态刷新整个视图。
        :param save: 如果为 True，则在刷新前将更改保存到数据库。
        """
        if save:
            await self._save_changes()

        self.create_components()
        embed = self.create_embed()
        # 始终使用父交互来编辑原始消息
        await self.parent_interaction.edit_original_response(embed=embed, view=self)

    def create_embed(self) -> discord.Embed:
        """创建或更新用于显示消息列表的 Embed。"""
        channel = self.parent_interaction.guild.get_channel_or_thread(self.channel_id)
        channel_name = channel.name if channel else f"未知 (ID: {self.channel_id})"

        embed = discord.Embed(
            title=f"正在编辑 #{channel_name} 的临时消息",
            description="在这里管理当用户点击“了解详情”后，按顺序显示的临时消息。",
            color=root_config.EMBED_COLOR_INFO,
        )

        if not self.messages:
            embed.add_field(
                name="当前没有临时消息",
                value="点击“添加新消息”来创建第一条。",
                inline=False,
            )
        else:
            msg_list = ""
            for i, msg in enumerate(self.messages):
                is_selected = (
                    "🔹" if msg["internal_id"] == self.selected_message_id else "▪️"
                )
                msg_list += f"{i + 1}. {is_selected} **{msg.get('title', '无标题')}**\n"
            embed.add_field(name="消息顺序", value=msg_list, inline=False)

        embed.set_footer(text="使用下拉菜单选择一条消息以进行编辑或删除。")
        return embed

    async def _save_changes(self):
        """将当前的消息列表保存到数据库。"""
        # 移除内部ID后保存
        data_to_save = [
            {k: v for k, v in msg.items() if k != "internal_id"}
            for msg in self.messages
        ]

        # 获取现有的永久消息数据，以防被覆盖
        config = await db_manager.get_channel_message(self.channel_id)
        permanent_data = config.get("permanent_message_data") if config else None

        await db_manager.set_channel_message(
            guild_id=self.parent_interaction.guild_id,
            channel_id=self.channel_id,
            permanent_data=permanent_data,
            temporary_data=data_to_save,
        )

    # --- 子组件定义 ---

    class MessageSelect(Select):
        def __init__(self, messages: List[Dict[str, Any]], selected_id: Optional[str]):
            options = []
            if not messages:
                options.append(
                    discord.SelectOption(
                        label="没有可选择的消息", value="placeholder", emoji="🤷"
                    )
                )
            else:
                for i, msg in enumerate(messages):
                    options.append(
                        discord.SelectOption(
                            label=f"{i + 1}. {msg.get('title', '无标题')}",
                            value=msg["internal_id"],
                            default=msg["internal_id"] == selected_id,
                        )
                    )

            super().__init__(
                placeholder="选择一条消息进行操作...",
                min_values=1,
                max_values=1,
                options=options,
                row=0,
                disabled=not messages,
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            self.view.selected_message_id = self.values[0]
            await self.view.update_view()  # 选择操作不需要保存

    class AddButton(Button):
        def __init__(self):
            super().__init__(
                label="添加新消息", style=discord.ButtonStyle.success, emoji="➕", row=1
            )

        async def callback(self, interaction: discord.Interaction):
            # 将视图的引用传递给模态框，让模态框来处理后续逻辑
            modal = TemporaryMessageModal(parent_view=self.view)
            await interaction.response.send_modal(modal)

    class EditButton(Button):
        def __init__(self, disabled: bool):
            super().__init__(
                label="编辑所选消息",
                style=discord.ButtonStyle.primary,
                emoji="✏️",
                row=1,
                disabled=disabled,
            )

        async def callback(self, interaction: discord.Interaction):
            selected_msg = next(
                (
                    m
                    for m in self.view.messages
                    if m["internal_id"] == self.view.selected_message_id
                ),
                None,
            )
            if not selected_msg:
                await interaction.response.send_message(
                    "❌ 错误：找不到所选消息。", ephemeral=True
                )
                return

            modal = TemporaryMessageModal(
                existing_data=selected_msg, parent_view=self.view
            )
            await interaction.response.send_modal(modal)

    class DeleteButton(Button):
        def __init__(self, disabled: bool):
            super().__init__(
                label="删除所选消息",
                style=discord.ButtonStyle.danger,
                emoji="🗑️",
                row=1,
                disabled=disabled,
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            self.view.messages = [
                m
                for m in self.view.messages
                if m["internal_id"] != self.view.selected_message_id
            ]
            self.view.selected_message_id = None
            # 删除后立即保存并更新视图
            await self.view.update_view(save=True)

    class BackButton(Button):
        def __init__(self):
            super().__init__(
                label="返回", style=discord.ButtonStyle.grey, emoji="↩️", row=2
            )

        async def callback(self, interaction: discord.Interaction):
            """停止当前视图，让父视图的 wait() 继续执行以返回上一级菜单。"""
            await interaction.response.defer()
            self.view.stop()
