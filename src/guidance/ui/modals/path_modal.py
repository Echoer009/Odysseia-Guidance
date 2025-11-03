# -*- coding: utf-8 -*-

import discord
from discord.ui import Modal, TextInput
import logging
import re

from src.guidance.utils.database import guidance_db_manager

log = logging.getLogger(__name__)


class PathModal(Modal, title="批量添加路径点"):
    """
    一个模态窗口，用于通过链接批量添加新的路径点。
    """

    link_input = TextInput(
        label="频道或帖子链接 (可一次性粘贴多个)",
        style=discord.TextStyle.long,
        placeholder="请粘贴一个或多个链接，每行一个或用空格隔开。\n例如：\nhttps://discord.com/channels/...\nhttps://discord.com/channels/...",
        required=True,
    )

    def __init__(self, guild_id: int, tag_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.tag_id = tag_id
        self.callback_view = None

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        links_text = self.link_input.value
        message = ""  # 自定义消息功能已从此模态框中移除，默认为空

        # 使用正则表达式分割链接，可以按空格、换行、逗号等分隔
        links = re.split(r"[\s,;\n]+", links_text)

        success_count = 0
        fail_count = 0
        error_messages = []
        new_paths_data = []

        for link in links:
            if not link:
                continue

            match = re.match(
                r"https?://(?:www\.)?discord\.com/channels/(\d+)/(\d+)(?:/(\d+))?", link
            )
            if not match:
                fail_count += 1
                error_messages.append(f"格式错误: `{link}`")
                continue

            guild_id, location_id, _ = match.groups()
            if int(guild_id) != self.guild_id:
                fail_count += 1
                error_messages.append(f"来自其他服务器: `{link}`")
                continue

            location = interaction.guild.get_channel(
                int(location_id)
            ) or interaction.guild.get_thread(int(location_id))
            if not location:
                fail_count += 1
                error_messages.append(f"找不到频道/帖子: `{link}`")
                continue

            location_type = (
                "THREAD" if isinstance(location, discord.Thread) else "CHANNEL"
            )
            new_paths_data.append(
                {
                    "location_id": location.id,
                    "location_type": location_type,
                    "message": message,
                }
            )
            success_count += 1

        try:
            if success_count > 0:
                existing_paths = await guidance_db_manager.get_path_for_tag(self.tag_id)
                paths_to_set_dicts = [dict(p) for p in existing_paths] + new_paths_data
                await guidance_db_manager.set_path_for_tag(
                    self.tag_id, paths_to_set_dicts
                )

            # 构建最终的反馈消息
            report = f"✅ **批量添加完成**\n- 成功添加 **{success_count}** 个路径点。"
            if fail_count > 0:
                report += (
                    f"\n- 失败 **{fail_count}** 个。\n**失败详情:**\n- "
                    + "\n- ".join(error_messages)
                )

            await interaction.followup.send(report, ephemeral=True)

            if self.callback_view:
                await self.callback_view.refresh()

        except Exception as e:
            log.error(f"批量添加路径点时出错: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ 批量添加路径点时发生数据库错误。", ephemeral=True
            )
