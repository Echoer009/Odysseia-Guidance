# -*- coding: utf-8 -*-

import discord
from discord.ui import Modal, TextInput
import logging
from src import config
from typing import Dict, Optional

from src.guidance.utils.database import guidance_db_manager as db_manager

log = logging.getLogger(__name__)


class TemplateModal(Modal):
    """用于编辑消息模板的通用模态框"""

    def __init__(
        self,
        template_name: str,
        current_data: Optional[Dict],
        parent_view: discord.ui.View,
    ):
        self.template_name = template_name
        self.parent_view = parent_view

        # 从字典中获取模板的显示名称
        title = f"编辑: {config.TEMPLATE_TYPES[template_name]['label']}"
        super().__init__(title=title, timeout=300)

        # 安全地获取当前数据
        current_data = current_data or {}
        embed_data = current_data.get("embed_data", {})

        # 添加输入字段 (最多5个)
        self.add_item(
            TextInput(
                label="Embed 标题",
                placeholder="卡片标题，支持 {user_name}, {server_name} 等变量。",
                default=embed_data.get("title"),
                max_length=256,
                required=True,
            )
        )
        self.add_item(
            TextInput(
                label="Embed 描述",
                placeholder="卡片的主要内容。支持 Markdown 和所有变量。",
                default=embed_data.get("description"),
                style=discord.TextStyle.paragraph,
                max_length=4000,
                required=True,
            )
        )
        # 作者字段已根据用户反馈移除
        self.add_item(
            TextInput(
                label="Embed 底部文字",
                placeholder="显示在卡片底部的小字。",
                default=embed_data.get("footer_text"),
                max_length=2048,
                required=False,
            )
        )
        self.add_item(
            TextInput(
                label="Embed 大图 URL",
                placeholder="可选，在卡片底部显示一张大图的图片URL。",
                default=embed_data.get("image_url"),
                required=False,
            )
        )
        self.add_item(
            TextInput(
                label="Embed 缩略图 URL",
                placeholder="可选，在卡片右上角显示的小图URL。留空则默认使用服务器头像。",
                default=embed_data.get("thumbnail_url"),
                required=False,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # 从表单中提取数据
        title = self.children[0].value
        description = self.children[1].value
        # author_text 已移除，调整索引
        footer_text = self.children[2].value
        image_url = self.children[3].value
        thumbnail_url = self.children[4].value

        # 构建 embed 数据字典
        # 注意：颜色字段暂时移除，以容纳其他更重要的字段
        embed_data = {
            "title": title,
            "description": description,
            "footer_text": footer_text,
            "image_url": image_url,
            "thumbnail_url": thumbnail_url,
        }

        try:
            # 将字典转换为 JSON 字符串存入数据库
            await db_manager.set_message_template(
                guild_id=interaction.guild_id,
                template_name=self.template_name,
                template_data=embed_data,
            )
            await interaction.followup.send("✅ 消息模板已成功保存！", ephemeral=True)

            # 刷新父视图以更新状态
            if hasattr(self.parent_view, "refresh"):
                await self.parent_view.refresh(interaction)

        except Exception as e:
            log.error(
                f"保存在服务器 {interaction.guild_id} 的模板 {self.template_name} 时出错: {e}",
                exc_info=True,
            )
            await interaction.followup.send(
                "❌ 保存失败，发生了一个内部错误。", ephemeral=True
            )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error(f"处理模板模态框时发生错误: {error}", exc_info=True)
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "处理您的请求时发生错误，请重试。", ephemeral=True
            )
        else:
            await interaction.followup.send(
                "处理您的请求时发生错误，请重试。", ephemeral=True
            )
