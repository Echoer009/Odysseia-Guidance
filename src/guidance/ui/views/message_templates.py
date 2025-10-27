# -*- coding: utf-8 -*-

import discord
from discord.ui import View, Button, button
import logging
from typing import Dict
from typing import Optional

from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.ui.views.ui_elements import BackButton
from src.guidance import config as guidance_config
from src import config as app_config

log = logging.getLogger(__name__)


class MessageTemplatesView(View):
    """消息模板配置的主视图"""

    def __init__(
        self, main_interaction: discord.Interaction, guild: discord.Guild = None
    ):
        super().__init__(timeout=180)
        self.main_interaction = main_interaction
        guild = guild if guild else main_interaction.guild
        self.guild_id = guild.id
        self.templates = {}

        # BackButton 将在 populate_buttons 的末尾被添加

    async def async_init(self):
        """异步加载数据并填充视图。"""
        await self.populate_buttons()
        return self

    async def populate_buttons(self):
        """动态添加模板编辑按钮，并确保返回按钮在最后。"""
        # 清空所有旧的按钮
        self.clear_items()

        self.templates = await db_manager.get_all_message_templates(self.guild_id)

        # 添加模板编辑按钮，将它们成对排列以节省空间
        for i, (name, details) in enumerate(guidance_config.TEMPLATE_TYPES.items()):
            is_set = self.templates.get(name) is not None
            style = (
                discord.ButtonStyle.success if is_set else discord.ButtonStyle.secondary
            )

            # 计算行号，每行最多2个按钮
            row = i // 2

            self.add_item(
                TemplateEditButton(
                    template_name=name,
                    label=details["label"],
                    style=style,
                    emoji=details["emoji"],
                    row=row,
                )
            )

        # 在所有模板按钮之后添加返回按钮，确保它在安全的新一行
        # 5个模板会占用 0, 1, 2 行。所以返回按钮放在第 3 行是安全的。
        self.add_item(BackButton(row=3))

    def get_embed(self) -> discord.Embed:
        """生成消息模板配置的 Embed"""
        embed = discord.Embed(
            title="📝 消息模板配置",
            description="在这里，您可以自定义机器人在引导流程中发送给用户的各类消息。\n点击下方按钮以编辑对应的消息模板。",
            color=app_config.EMBED_COLOR_INFO,
        )

        for name, details in guidance_config.TEMPLATE_TYPES.items():
            status = "✅ 已设置" if self.templates.get(name) else "❌ 未设置"
            embed.add_field(
                name=f"{details['emoji']} {details['label']}",
                value=f"状态: {status}\n{details['description']}",
                inline=False,
            )

        return embed

    async def refresh(self, interaction: Optional[discord.Interaction] = None):
        """
        刷新视图以显示最新状态。
        """
        await self.populate_buttons()
        embed = self.get_embed()
        await self.main_interaction.edit_original_response(embed=embed, view=self)


class TemplateEditButton(Button):
    """编辑模板的按钮"""

    def __init__(
        self,
        template_name: str,
        label: str,
        style: discord.ButtonStyle,
        emoji: str,
        row: int,
    ):
        super().__init__(label=label, style=style, emoji=emoji, row=row)
        self.template_name = template_name

    async def callback(self, interaction: discord.Interaction):
        """根据模板类型打开不同的编辑视图。"""
        template_info = guidance_config.TEMPLATE_TYPES.get(self.template_name, {})
        is_multiple = template_info.get("multiple", False)

        current_template = await db_manager.get_message_template(
            interaction.guild_id, self.template_name
        )

        if is_multiple:
            # 启动支持多消息的编辑视图
            from .template_message_editor import TemplateMessagesEditView

            edit_view = TemplateMessagesEditView(
                parent_interaction=interaction,
                main_view=self.view,  # 传递主视图的引用
                template_name=self.template_name,
                existing_data=current_template,
            )
            embed = edit_view.create_embed()
            await interaction.response.edit_message(embed=embed, view=edit_view)
            await edit_view.wait()

            # 当 edit_view 停止后，控制权返回到这里。
            # 我们需要使用原始的 interaction 来刷新主菜单，以完成交互周期。
            await self.view.refresh(interaction)

        else:
            # 启动传统的模态框编辑器
            from ..modals.template_modal import TemplateModal

            modal = TemplateModal(
                template_name=self.template_name,
                current_data=current_template,
                parent_view=self.view,
            )
            try:
                await interaction.response.send_modal(modal)
            except discord.NotFound:
                try:
                    await interaction.followup.send(
                        "❌ 操作超时，此次交互已失效。请重新打开管理面板再试一次。",
                        ephemeral=True,
                    )
                except discord.HTTPException:
                    pass
