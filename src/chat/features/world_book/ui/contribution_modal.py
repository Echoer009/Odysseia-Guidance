import discord
import logging
from typing import Dict, Any
from src import config
from src.chat.services.submission_service import submission_service
from src.chat.features.world_book.services.world_book_service import world_book_service

log = logging.getLogger(__name__)

# 定义可用的类别列表
AVAILABLE_CATEGORIES = ["社区信息", "社区文化", "社区大事件", "俚语", "社区知识"]


class WorldBookContributionModal(discord.ui.Modal, title="贡献知识"):
    """用于用户提交世界书知识条目的模态窗口（已重构）"""

    def __init__(self, purchase_info: Dict[str, Any] = None):
        super().__init__()
        self.purchase_info = purchase_info

        self.category_input = discord.ui.TextInput(
            label="类别",
            placeholder=f"请输入类别，例如：{', '.join(AVAILABLE_CATEGORIES)}",
            max_length=50,
            required=True,
        )
        self.add_item(self.category_input)

        self.title_input = discord.ui.TextInput(
            label="标题",
            placeholder="请输入知识条目的标题",
            max_length=100,
            required=True,
        )
        self.add_item(self.title_input)

        self.content_input = discord.ui.TextInput(
            label="内容",
            placeholder="请输入详细内容",
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True,
        )
        self.add_item(self.content_input)

    async def on_submit(self, interaction: discord.Interaction):
        """当用户提交模态窗口时调用（已重构）"""
        # 步骤 1: 延迟响应以处理后续操作
        await interaction.response.defer(ephemeral=True)

        # 步骤 2: (如果适用) 处理购买和扣款
        if self.purchase_info:
            from src.chat.features.odysseia_coin.service.coin_service import (
                coin_service,
            )

            price = self.purchase_info.get("price", 0)
            if price > 0:
                new_balance = await coin_service.remove_coins(
                    user_id=interaction.user.id,
                    amount=price,
                    reason=f"购买知识纸条 (item_id: {self.purchase_info.get('item_id')})",
                )
                if new_balance is None:
                    await interaction.followup.send(
                        "抱歉，你的余额似乎不足，购买失败。", ephemeral=True
                    )
                    return

        # 步骤 3: 收集和验证输入
        category = self.category_input.value.strip()
        title = self.title_input.value.strip()
        content = self.content_input.value.strip()

        if category not in AVAILABLE_CATEGORIES:
            await interaction.followup.send(
                f"无效的类别。请从以下选项中选择: {', '.join(AVAILABLE_CATEGORIES)}",
                ephemeral=True,
            )
            return

        if not all([category, title, content]):
            await interaction.followup.send(
                "类别、标题和内容均不能为空。", ephemeral=True
            )
            return

        # 步骤 4: 处理开发者后门
        if interaction.user.id in config.DEVELOPER_USER_IDS:
            await self.developer_direct_add(interaction, category, title, content)
            return

        # 步骤 5: 构造数据并调用 SubmissionService
        knowledge_data = {
            "category_name": category,
            "title": title,
            "name": title,
            "content_text": content,
            "contributor_id": interaction.user.id,
            "contributor_name": interaction.user.display_name,
        }

        pending_id = await submission_service.submit_general_knowledge(
            interaction, knowledge_data, self.purchase_info
        )

        # 步骤 6: 根据提交结果向用户发送最终反馈
        if pending_id:
            await interaction.followup.send(
                f"✅ 您的知识贡献 **{title}** 已成功提交审核！\n请关注频道内的公开投票。",
                ephemeral=True,
            )
        else:
            # 如果提交失败，需要处理退款
            if self.purchase_info:
                from src.chat.features.odysseia_coin.service.coin_service import (
                    coin_service,
                )

                await coin_service.add_coins(
                    user_id=interaction.user.id,
                    amount=self.purchase_info.get("price", 0),
                    reason=f"知识纸条提交失败自动退款 (item_id: {self.purchase_info.get('item_id')})",
                )
                await interaction.followup.send(
                    "提交审核时发生错误，已自动退款，请稍后再试。", ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "提交审核时发生错误，请稍后再试。", ephemeral=True
                )

    async def developer_direct_add(
        self,
        interaction: discord.Interaction,
        category_name: str,
        title: str,
        content_text: str,
    ):
        """开发者直接添加知识条目，无需审核（已重构）"""
        success = world_book_service.add_general_knowledge(
            title=title,
            name=title,
            content_text=content_text,
            category_name=category_name,
            contributor_id=interaction.user.id,
        )

        if success:
            # 异步触发RAG更新
            # 注意：add_general_knowledge 内部现在不返回 entry_id，这是一个待改进点。
            # 暂时我们无法精确更新，但可以触发一个更广泛的更新或忽略。
            # 为了简单起见，我们暂时在这里不调用RAG更新，依赖于定期的全局更新。
            await interaction.followup.send(
                f"✅ **开发者后门**: 知识条目 **{title}** 已成功添加，无需审核。",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "❌ 添加时发生内部错误，请检查日志。", ephemeral=True
            )
