# -*- coding: utf-8 -*-

import discord
from typing import Optional
from discord.ui import View, Button, button
import logging

from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.ui.modals.tag_modal import TagModal
from src.guidance.ui.views.ui_elements import BackButton
from src import config as root_config

log = logging.getLogger(__name__)


class TagManagementView(View):
    """标签管理界面的视图"""

    def __init__(self, main_interaction: discord.Interaction):
        super().__init__(timeout=180)
        self.main_interaction = main_interaction
        self.guild_id = main_interaction.guild.id
        self.tags = []
        self.default_tag_id = None

        self.add_item(BackButton())
        self.add_item(AddTagButton())
        # populate_buttons 将在 async_init 中被调用

    async def async_init(self):
        """异步加载数据并填充视图。"""
        guild_config = await db_manager.get_guild_config(self.guild_id)
        if guild_config:
            self.default_tag_id = guild_config["default_tag_id"]
        await self.populate_buttons()
        return self

    async def populate_buttons(self):
        """从数据库加载标签并创建按钮"""
        # 在重新加载前清除旧的标签按钮
        for item in self.children[:]:
            if isinstance(item, TagButton):
                self.remove_item(item)

        self.tags = await db_manager.get_all_tags(self.guild_id)
        for tag in self.tags:
            is_default = (
                self.default_tag_id is not None and tag["tag_id"] == self.default_tag_id
            )
            # 将主视图的引用传递给按钮
            self.add_item(TagButton(tag, is_default=is_default, parent_view=self))

    def get_embed(self) -> discord.Embed:
        """生成标签管理的 Embed"""
        embed = discord.Embed(
            title="🏷️ 标签管理",
            description="在这里管理用于分类引导路径的标签。\n点击下方按钮新增标签，或点击已有标签进行编辑/删除。",
            color=root_config.EMBED_COLOR_INFO,
        )
        if not self.tags:
            embed.add_field(name="暂无标签", value="点击“新增标签”来创建第一个标签吧！")
        else:
            tag_list = []
            for tag in self.tags:
                desc = f"> {tag['description']}" if tag["description"] else "> *无描述*"
                is_default = (
                    self.default_tag_id is not None
                    and tag["tag_id"] == self.default_tag_id
                )
                prefix = "⭐ " if is_default else ""
                tag_list.append(f"**{prefix}{tag['tag_name']}**\n{desc}")
            embed.add_field(
                name="已创建的标签", value="\n\n".join(tag_list), inline=False
            )
            embed.set_footer(
                text="⭐ 表示默认标签，所有新成员都将自动获得此标签的引导路径。"
            )
        return embed

    async def refresh(self):
        """
        就地刷新视图和Embed，而不是创建一个新实例。
        """
        # 重新从数据库获取最新的标签列表
        guild_config = await db_manager.get_guild_config(self.guild_id)
        if guild_config:
            self.default_tag_id = guild_config["default_tag_id"]
        self.tags = await db_manager.get_all_tags(self.guild_id)

        # 更新Embed
        embed = self.get_embed()

        # 清除旧的标签按钮
        for item in self.children[:]:
            if isinstance(item, TagButton):
                self.remove_item(item)

        # 重新添加按钮
        # 注意：需要保持返回和新增按钮在前面
        children_to_keep = [
            item for item in self.children if not isinstance(item, TagButton)
        ]
        self.clear_items()
        for item in children_to_keep:
            self.add_item(item)

        for tag in self.tags:
            is_default = (
                self.default_tag_id is not None and tag["tag_id"] == self.default_tag_id
            )
            self.add_item(TagButton(tag, is_default=is_default, parent_view=self))

        # 使用原始交互来编辑消息
        await self.main_interaction.edit_original_response(embed=embed, view=self)


# --- 确认删除视图 ---
class ConfirmDeleteView(View):
    def __init__(self, tag: dict, parent_view: "TagManagementView"):
        super().__init__(timeout=60)
        self.tag = tag
        self.parent_view = parent_view
        self.message: Optional[discord.Message] = None

    @button(label="确认删除", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        try:
            await db_manager.delete_tag(self.tag["tag_id"])
            await interaction.response.send_message(
                f"✅ 成功删除标签 **{self.tag['tag_name']}**。", ephemeral=True
            )
            await self.parent_view.refresh()
        except Exception as e:
            log.error(f"删除标签失败: {e}", exc_info=True)
            await interaction.response.send_message(
                "❌ 删除失败，发生未知错误。", ephemeral=True
            )

        # 停止视图并清理消息
        self.stop()
        if self.message:
            await self.message.delete()

    @button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        self.stop()
        if self.message:
            await self.message.edit(content="操作已取消。", view=None)


# --- 标签操作视图 ---
class TagActionView(View):
    def __init__(self, tag: dict, is_default: bool, parent_view: "TagManagementView"):
        super().__init__(timeout=180)
        self.tag = tag
        self.is_default = is_default
        self.parent_view = parent_view
        # 在初始化时就添加按钮，以便控制它们的顺序和状态
        self.add_item(self.create_edit_button())
        self.add_item(self.create_delete_button())
        self.add_item(self.create_set_default_button())
        self.add_item(self.create_back_button())

    def create_edit_button(self):
        return Button(
            label="编辑标签",
            style=discord.ButtonStyle.primary,
            emoji="✏️",
            row=0,
            custom_id="edit_button",
        )

    def create_delete_button(self):
        return Button(
            label="删除标签",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            row=0,
            custom_id="delete_button",
        )

    def create_set_default_button(self):
        label = "取消默认" if self.is_default else "设为默认"
        style = (
            discord.ButtonStyle.danger
            if self.is_default
            else discord.ButtonStyle.success
        )
        emoji = "❌" if self.is_default else "⭐"
        return Button(
            label=label, style=style, emoji=emoji, row=1, custom_id="set_default_button"
        )

    def create_back_button(self):
        return Button(
            label="返回列表",
            style=discord.ButtonStyle.secondary,
            emoji="↩️",
            row=2,
            custom_id="back_button",
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # 统一处理回调
        custom_id = interaction.data.get("custom_id")
        if custom_id == "edit_button":
            await self.edit_button_callback(interaction)
        elif custom_id == "delete_button":
            await self.delete_button_callback(interaction)
        elif custom_id == "set_default_button":
            await self.set_default_button_callback(interaction)
        elif custom_id == "back_button":
            await self.back_button_callback(interaction)
        return True

    async def edit_button_callback(self, interaction: discord.Interaction):
        modal = TagModal(guild_id=interaction.guild.id, existing_tag=self.tag)
        modal.callback_view = self.parent_view
        await interaction.response.send_modal(modal)
        self.stop()

    async def delete_button_callback(self, interaction: discord.Interaction):
        confirm_view = ConfirmDeleteView(self.tag, self.parent_view)
        msg_content = f"你确定要删除标签 **{self.tag['tag_name']}** 吗？\n> ⚠️ **此操作不可逆**，与此标签关联的所有引导路径也将被删除。"
        if self.is_default:
            msg_content += "\n> **此标签是默认标签，删除后将取消默认设置。**"
        await interaction.response.send_message(
            msg_content, view=confirm_view, ephemeral=True
        )
        confirm_view.message = await interaction.original_response()
        self.stop()

    async def set_default_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        new_default_id = None if self.is_default else self.tag["tag_id"]
        try:
            await db_manager.set_default_tag(self.parent_view.guild_id, new_default_id)
            action_text = "取消默认设置" if self.is_default else "设为默认"
            await interaction.followup.send(
                f"✅ 已成功为标签 **{self.tag['tag_name']}** {action_text}。",
                ephemeral=True,
            )
            await self.parent_view.refresh()
        except Exception as e:
            log.error(f"设置默认标签失败: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ 操作失败，发生未知错误。", ephemeral=True
            )
        self.stop()

    async def back_button_callback(self, interaction: discord.Interaction):
        # Defer the interaction response
        await interaction.response.defer()
        await self.parent_view.refresh()
        self.stop()


# --- 动态生成的按钮 ---
class TagButton(Button):
    def __init__(self, tag: dict, is_default: bool, parent_view: "TagManagementView"):
        style = (
            discord.ButtonStyle.success if is_default else discord.ButtonStyle.primary
        )
        label = f"⭐ {tag['tag_name']}" if is_default else tag["tag_name"]
        super().__init__(label=label, style=style)
        self.tag = tag
        self.is_default = is_default
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # 创建操作视图
        action_view = TagActionView(self.tag, self.is_default, self.parent_view)

        # 创建一个新的 embed 来显示正在管理哪个标签
        embed = discord.Embed(
            title=f"管理标签: {self.tag['tag_name']}",
            description=f"你正在管理标签 **{self.tag['tag_name']}**。\n> {self.tag['description'] or '*无描述*'}",
            color=root_config.EMBED_COLOR_INFO,
        )

        # 编辑原消息以显示新视图和 embed
        await interaction.response.edit_message(embed=embed, view=action_view)


# --- 固定功能按钮 ---
class AddTagButton(Button):
    def __init__(self):
        super().__init__(
            label="新增标签", style=discord.ButtonStyle.success, emoji="➕"
        )

    async def callback(self, interaction: discord.Interaction):
        # self.view 是按钮所在的视图实例
        modal = TagModal(guild_id=interaction.guild_id)
        # 将视图的 refresh 方法作为回调传递给 modal
        modal.callback_view = self.view
        await interaction.response.send_modal(modal)
