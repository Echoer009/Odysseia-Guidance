# -*- coding: utf-8 -*-
import discord
import logging
from typing import Dict, Any
from src.chat.services.submission_service import submission_service

log = logging.getLogger(__name__)


class SellBodySubmissionModal(discord.ui.Modal, title="拉皮条！"):
    """用于用户提交自定义卖屁股事件的模态窗口"""

    def __init__(self, purchase_info: Dict[str, Any] = None):
        super().__init__()
        self.purchase_info = purchase_info

        self.event_name_input = discord.ui.TextInput(
            label="服务项目",
            placeholder="例如: '午夜牛郎', '后庭花开'",
            max_length=50,
            required=True,
        )
        self.add_item(self.event_name_input)

        self.description_input = discord.ui.TextInput(
            label="服务描述",
            placeholder="详细描述服务细节...",
            style=discord.TextStyle.paragraph,
            max_length=100,
            required=True,
        )
        self.add_item(self.description_input)

        self.base_reward_input = discord.ui.TextInput(
            label="基础肉金范围 (最小-最大)",
            placeholder="例如: 200-500",
            max_length=10,
            required=True,
        )
        self.add_item(self.base_reward_input)

        self.good_event_input = discord.ui.TextInput(
            label="客人很满意 (可选)",
            placeholder="格式: 描述 # 奖励倍率 (例如: 客人很满意, 并给了小费 # 1.5)",
            style=discord.TextStyle.paragraph,
            max_length=100,
            required=False,
        )
        self.add_item(self.good_event_input)

        self.bad_event_input = discord.ui.TextInput(
            label="服务翻车了 (可选)",
            placeholder="格式: 描述 # 奖励倍率 (例如: 被警察查房了 # -1.0)",
            style=discord.TextStyle.paragraph,
            max_length=100,
            required=False,
        )
        self.add_item(self.bad_event_input)

    async def on_submit(self, interaction: discord.Interaction):
        """当用户提交模态窗口时调用"""
        await interaction.response.defer(ephemeral=True)

        # --- 验证基础奖励范围 ---
        try:
            reward_range_str = self.base_reward_input.value.replace(" ", "")
            parts = reward_range_str.split("-")
            if len(parts) != 2:
                parts = reward_range_str.split(",")
                if len(parts) != 2:
                    raise ValueError("格式必须为 `最小-最大` 或 `最小,最大`。")

            reward_min = int(parts[0])
            reward_max = int(parts[1])

            if not (200 <= reward_min <= 500 and 200 <= reward_max <= 500):
                await interaction.followup.send(
                    "❌ **错误**: 基础肉金的最小和最大值都必须在 200 到 500 之间。",
                    ephemeral=True,
                )
                return
            if reward_min > reward_max:
                await interaction.followup.send(
                    "❌ **错误**: 基础肉金的最小值不能大于最大值。", ephemeral=True
                )
                return

        except (ValueError, IndexError) as e:
            await interaction.followup.send(
                f"❌ **基础肉金格式错误**: {e}\n请输入有效的范围，例如 `200-500`。",
                ephemeral=True,
            )
            return

        # --- 解析并验证好事和坏事事件 ---
        good_event_description = None
        good_event_modifier = None
        bad_event_description = None
        bad_event_modifier = None

        try:
            if self.good_event_input.value:
                parts = self.good_event_input.value.strip().split("#")
                if len(parts) != 2:
                    raise ValueError("“客人很满意”的格式必须是 `描述 # 倍率`。")
                good_event_description = parts[0].strip()
                good_event_modifier = float(parts[1].strip())
                if abs(good_event_modifier) > 2.5:
                    raise ValueError("“客人很满意”的奖励倍率绝对值不能超过 2.5。")

            if self.bad_event_input.value:
                parts = self.bad_event_input.value.strip().split("#")
                if len(parts) != 2:
                    raise ValueError("“服务翻车了”的格式必须是 `描述 # 倍率`。")
                bad_event_description = parts[0].strip()
                bad_event_modifier = float(parts[1].strip())
                if abs(bad_event_modifier) > 2.5:
                    raise ValueError("“服务翻车了”的奖励倍率绝对值不能超过 2.5。")

        except (ValueError, IndexError) as e:
            await interaction.followup.send(
                f"❌ **格式或数值错误**: {e}\n请检查您的输入。",
                ephemeral=True,
            )
            return

        event_data = {
            "event_type": "sell_body",
            "name": self.event_name_input.value.strip(),
            "description": self.description_input.value.strip(),
            "reward_range_min": reward_min,
            "reward_range_max": reward_max,
            "good_event_description": good_event_description,
            "good_event_modifier": good_event_modifier,
            "bad_event_description": bad_event_description,
            "bad_event_modifier": bad_event_modifier,
            "contributor_id": interaction.user.id,
            "contributor_name": interaction.user.display_name,
        }

        # 开发者后门 (暂不实现直接添加)

        # --- 提交审核 ---
        pending_id = await submission_service.submit_work_event(
            interaction, event_data, self.purchase_info
        )

        if pending_id:
            await interaction.followup.send(
                f"✅ 您的自定义事件 **{event_data['name']}** 已成功提交审核！\n请关注频道内的公开投票。",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "❌ 提交审核时发生错误，请稍后再试。", ephemeral=True
            )
