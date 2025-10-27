# -*- coding: utf-8 -*-

import discord
from typing import List, Dict, Any, Callable, Optional

from src.guidance.utils.helpers import create_embed_from_template_data


class MessageCycleView(discord.ui.View):
    """
    一个健壮的、可复用的视图，用于循环浏览消息列表。
    它可以被用于发送新消息，或在现有消息上进行编辑。
    """

    def __init__(
        self,
        messages: List[Dict[str, Any]],
        format_args: Dict[str, Any],
        channel: Optional[discord.abc.GuildChannel] = None,
        *,
        add_tag_select_on_last_page: bool = False,
        tag_select_factory: Optional[Callable[[], discord.ui.Select]] = None,
        add_start_button_on_last_page: bool = False,
        start_button_factory: Optional[Callable[[], discord.ui.Button]] = None,
    ):
        super().__init__(timeout=None)
        self.messages = messages
        self.format_args = format_args
        self.channel = channel
        self.current_index = 0

        self.add_tag_select = add_tag_select_on_last_page
        self.tag_select_factory = tag_select_factory
        self.add_start_button = add_start_button_on_last_page
        self.start_button_factory = start_button_factory

        # Do not call update_view() here. It will be called by start() or refresh_message().

    def create_embed(self) -> discord.Embed:
        """为当前页面创建 Embed。"""
        return create_embed_from_template_data(
            self.messages[self.current_index], channel=self.channel, **self.format_args
        )

    def update_view(self):
        """根据当前状态清空并重新创建所有UI组件。"""
        self.clear_items()

        # 添加导航按钮
        is_first_page = self.current_index == 0
        is_last_page = self.current_index >= len(self.messages) - 1

        self.add_item(self.PrevButton(is_disabled=is_first_page))
        self.add_item(self.NextButton(is_disabled=is_last_page))

        # 如果是最后一页，添加额外组件
        if is_last_page:
            if self.add_start_button and self.start_button_factory:
                self.add_item(self.start_button_factory())
            if self.add_tag_select and self.tag_select_factory:
                self.add_item(self.tag_select_factory())

    async def start(self, interaction: discord.Interaction, ephemeral: bool = False):
        """通过发送一条新消息来启动视图。"""
        self.update_view()
        embed = self.create_embed()
        await interaction.followup.send(embed=embed, view=self, ephemeral=ephemeral)

    async def refresh_message(self, interaction: discord.Interaction):
        """使用新的 Embed 和 View 更新现有消息。"""
        self.update_view()
        embed = self.create_embed()
        # defer() 应该在 callback 中被调用, 这里直接编辑
        await interaction.edit_original_response(embed=embed, view=self)

    # --- 子组件定义 ---

    class PrevButton(discord.ui.Button):
        def __init__(self, is_disabled: bool):
            super().__init__(
                label="上一条",
                style=discord.ButtonStyle.primary,
                emoji="⬅️",
                disabled=is_disabled,
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()  # 立即响应交互
            view: "MessageCycleView" = self.view
            if view.current_index > 0:
                view.current_index -= 1
                # 现在 refresh_message 内部使用 edit_original_response
                await view.refresh_message(interaction)

    class NextButton(discord.ui.Button):
        def __init__(self, is_disabled: bool):
            super().__init__(
                label="下一条",
                style=discord.ButtonStyle.primary,
                emoji="➡️",
                disabled=is_disabled,
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()  # 立即响应交互
            view: "MessageCycleView" = self.view
            if view.current_index < len(view.messages) - 1:
                view.current_index += 1
                await view.refresh_message(interaction)
