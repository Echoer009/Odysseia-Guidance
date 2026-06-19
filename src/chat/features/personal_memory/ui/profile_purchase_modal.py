# -*- coding: utf-8 -*-
import discord
import logging
from typing import Dict, Any

from src.chat.services.submission_service import submission_service

log = logging.getLogger(__name__)


class PersonalProfilePurchaseModal(discord.ui.Modal, title="📝 创建或更新名片~这个会发到公屏让大家审核哦!"):
    def __init__(self, purchase_info: Dict[str, Any]):
        super().__init__(timeout=300)
        self.purchase_info = purchase_info

        self.name = discord.ui.TextInput(
            label="名称",
            placeholder="你的名称或昵称（填写后将发到公屏让大家审核）",
            required=True,
            style=discord.TextStyle.short,
            max_length=50,
        )
        self.personality = discord.ui.TextInput(
            label="性格特点",
            placeholder="描述你的性格，如热情、勇敢…（这些内容大家都能看到哦）",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )
        self.background = discord.ui.TextInput(
            label="背景信息 (可选)",
            placeholder="简单介绍背景故事（会公开展示给社区成员）",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1500,
        )
        self.preferences = discord.ui.TextInput(
            label="喜好偏好 (可选)",
            placeholder="喜欢/讨厌什么？（会公开展示给社区成员）",
            required=False,
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )

        self.add_item(self.name)
        self.add_item(self.personality)
        self.add_item(self.background)
        self.add_item(self.preferences)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        profile_data = {
            "name": self.name.value.strip(),
            "personality": self.personality.value.strip(),
            "background": self.background.value.strip(),
            "preferences": self.preferences.value.strip(),
            "discord_id": str(interaction.user.id),
            "discord_number_id": interaction.user.id,
            "uploaded_by": interaction.user.id,
            "uploaded_by_name": interaction.user.display_name,
            "update_target_id": str(interaction.user.id),
        }

        # 验证基本信息
        if not profile_data["name"] or not profile_data["personality"]:
            await interaction.followup.send(
                "❌ 名称和性格特点不能为空，本次提交无效。", ephemeral=True
            )
            return

        # 调用 SubmissionService 处理复杂的购买和提交逻辑
        # 注意：这里我们需要一个新的方法来处理这个流程
        (
            success,
            message,
        ) = await submission_service.submit_personal_profile_from_purchase(
            interaction=interaction,
            profile_data=profile_data,
            purchase_info=self.purchase_info,
        )
        await interaction.followup.send(message, ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        log.error(f"PersonalProfilePurchaseModal 发生错误: {error}", exc_info=True)
        await interaction.followup.send(
            "处理你的请求时发生了一个意想不到的错误。", ephemeral=True
        )
