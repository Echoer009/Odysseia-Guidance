# -*- coding: utf-8 -*-

import discord
from discord.ui import Modal, TextInput
from typing import Optional, Dict, Any

from src.guidance.utils.database import guidance_db_manager as db_manager


class ChannelMessageModal(Modal):
    """
    一个用于添加或编辑频道专属**永久**消息的模态框。
    """

    def __init__(
        self,
        interaction: discord.Interaction,
        channel_id: int,
        existing_config: Optional[Dict[str, Any]] = None,
        is_thread: bool = False,
    ):
        self.is_thread = is_thread
        location_type_str = "帖子" if self.is_thread else "频道"
        super().__init__(title="配置永久消息")

        self.interaction = interaction
        self.guild = interaction.guild
        self.channel_id = channel_id
        self.existing_config = existing_config

        # --- 组件定义 ---

        # 1. 显示当前配置的地点
        channel = self.guild.get_channel_or_thread(self.channel_id)
        channel_name = (
            f"#{channel.name}" if channel else f"未知地点 (ID: {self.channel_id})"
        )

        self.channel_display = TextInput(
            label=f"配置{location_type_str} (此项不可修改)", default=channel_name, row=0
        )
        self.add_item(self.channel_display)

        # 2. 永久消息标题
        self.permanent_title = TextInput(
            label="永久消息标题",
            placeholder="例如：欢迎来到 {channel.name}！",
            default=self.get_default_value("permanent", "title"),
            max_length=256,
            required=False,
            row=1,
        )
        self.add_item(self.permanent_title)

        # 3. 永久消息内容
        self.permanent_content = TextInput(
            label="永久消息内容 (Embed描述)",
            placeholder=f"简短介绍这个{location_type_str}是做什么的。",
            default=self.get_default_value("permanent", "description"),
            style=discord.TextStyle.paragraph,
            max_length=4000,
            required=False,
            row=2,
        )
        self.add_item(self.permanent_content)

    def get_default_value(self, message_type: str, field: str) -> Optional[str]:
        """从现有配置中安全地获取默认值。"""
        if not self.existing_config:
            return None

        data_key = f"{message_type}_message_data"
        message_data = self.existing_config.get(data_key)

        if message_data and isinstance(message_data, dict):
            return message_data.get(field)
        return None

    async def on_submit(self, interaction: discord.Interaction):
        # 获取现有的临时消息数据，以防被覆盖
        existing_temp_data = (
            self.existing_config.get("temporary_message_data")
            if self.existing_config
            else None
        )

        # 获取现有的页脚和图片值
        existing_perm_data = (
            self.existing_config.get("permanent_message_data", {})
            if self.existing_config
            else {}
        )

        permanent_data = {
            "title": self.permanent_title.value or None,
            "description": self.permanent_content.value or None,
            "footer": existing_perm_data.get("footer"),
            "image_url": existing_perm_data.get("image_url"),
            "thumbnail_url": existing_perm_data.get("thumbnail_url"),
        }
        # 只有在至少有一个字段被填写时才保存
        permanent_data_to_save = (
            permanent_data
            if any(p for p in permanent_data.values() if p is not None)
            else None
        )

        # 保存到数据库
        await db_manager.set_channel_message(
            guild_id=self.guild.id,
            channel_id=self.channel_id,
            permanent_data=permanent_data_to_save,
            temporary_data=existing_temp_data,  # 保持现有的临时消息数据不变
        )

        location_type_str = "帖子" if self.is_thread else "频道"
        await interaction.response.send_message(
            f"✅ 成功为{location_type_str} <#{self.channel_id}> 保存了永久消息配置！",
            ephemeral=True,
            delete_after=5,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        await interaction.response.send_message(
            f"❌ 保存配置时出错: {error}", ephemeral=True
        )
