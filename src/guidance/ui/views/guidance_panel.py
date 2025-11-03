# -*- coding: utf-8 -*-

import discord
from discord.ui import View, Select, Button
import logging
from typing import Optional

from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.utils.helpers import create_embed_from_template

log = logging.getLogger(__name__)


class GuidancePanelView(View):
    """
    这是部署后，普通用户看到的引导面板视图。
    它是一个持久化视图，通过 custom_id 来识别。
    """

    PERSISTENT_VIEW_CUSTOM_ID = "guidance_panel_view_v1"

    def __init__(
        self, guild_id: Optional[int] = None, selected_tag_id: Optional[int] = None
    ):
        super().__init__(timeout=None)
        self.custom_id = self.PERSISTENT_VIEW_CUSTOM_ID
        self.guild_id = guild_id
        self.selected_tag_id = selected_tag_id

        # 只有在 guild_id 存在时（即不是在 setup_hook 中被空实例化时）才添加组件
        if self.guild_id:
            self.add_item(
                TagSelect(guild_id=self.guild_id, selected_tag_id=self.selected_tag_id)
            )

            if self.selected_tag_id:
                paths = db_manager.get_paths_for_tag(
                    self.guild_id, self.selected_tag_id
                )
                for path in paths:
                    # 假设 path['name'] 是频道名, path['url'] 是跳转链接
                    self.add_item(PathButton(label=path["name"], url=path["url"]))

    @staticmethod
    def get_initial_embed(guild: discord.Guild) -> discord.Embed:
        """获取部署时发送的初始欢迎消息 Embed"""
        template = db_manager.get_message_template(guild.id, "welcome_message")
        # 注意：这里我们没有 user 对象，所以无法显示用户头像
        return create_embed_from_template(template, guild, server_name=guild.name)

    @staticmethod
    def get_tag_selected_embed(guild: discord.Guild, tag_name: str) -> discord.Embed:
        """获取用户选择标签后的提示消息 Embed"""
        template = db_manager.get_message_template(guild.id, "prompt_message")
        # 注意：这里我们同样没有 user 对象
        return create_embed_from_template(template, guild, tag_name=tag_name)


class TagSelect(Select):
    """让用户选择引导标签的下拉菜单"""

    def __init__(self, guild_id: int, selected_tag_id: Optional[int] = None):
        tags = db_manager.get_all_tags(guild_id)
        options = [
            discord.SelectOption(
                label=tag["name"],
                value=str(tag["id"]),
                description=tag.get("description"),
                emoji=tag.get("emoji"),
            )
            for tag in tags
        ]

        super().__init__(
            placeholder="请选择一个你感兴趣的引导方向...",
            options=options,
            min_values=1,
            max_values=1,
            row=0,
        )
        # 如果有已选标签，设置默认值
        if selected_tag_id:
            self.default_values = [
                discord.SelectOption(label="", value=str(selected_tag_id))
            ]

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        selected_id = int(self.values[0])
        tag = db_manager.get_tag_by_id(selected_id)

        if not tag:
            await interaction.followup.send(
                "抱歉，该标签似乎已不存在。", ephemeral=True
            )
            return

        # 创建新的视图和 Embed
        new_view = GuidancePanelView(
            guild_id=interaction.guild_id, selected_tag_id=selected_id
        )
        embed = GuidancePanelView.get_tag_selected_embed(interaction.guild, tag["name"])

        await interaction.edit_original_response(embed=embed, view=new_view)


class PathButton(Button):
    """一个简单的链接按钮，指向引导路径中的一个频道或帖子"""

    def __init__(self, label: str, url: str):
        # 按钮标签不能超过80个字符
        super().__init__(
            style=discord.ButtonStyle.link, label=label[:80], url=url, emoji="➡️"
        )
