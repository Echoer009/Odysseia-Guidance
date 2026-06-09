# -*- coding: utf-8 -*-

import discord
import logging
from typing import Optional, cast

from src.chat.features.admin_panel.ui.coin_management_view import CoinManagementView
from .community_members_view import CommunityMembersView
from .general_knowledge_view import GeneralKnowledgeView
from .work_events_view import WorkEventsView
from .vector_db_view import VectorDBView
from src.config import CURRENCY_NAME

log = logging.getLogger(__name__)


# --- 确认编辑记忆的视图 ---
# --- 数据库浏览器视图 ---
class DBManagementView(discord.ui.View):
    """数据库管理面板的导航视图"""

    def __init__(self, author_id: int):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.message: Optional[discord.Message] = None
        self.current_table: Optional[str] = None
        self._initialize_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """确保只有命令发起者才能与视图交互"""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "你不能操作这个视图。", ephemeral=True
            )
            return False
        return True

    def _initialize_components(self):
        """构建UI组件"""
        self.clear_items()
        self.add_item(self._create_table_select())

    def _create_table_select(self) -> discord.ui.Select:
        """创建表格选择下拉菜单"""
        options = [
            discord.SelectOption(
                label="社区成员档案", value="community_members", emoji="👥"
            ),
            discord.SelectOption(
                label="通用知识", value="general_knowledge", emoji="📚"
            ),
            discord.SelectOption(
                label=f"{CURRENCY_NAME}管理", value="coin_management", emoji="🪙"
            ),
            discord.SelectOption(label="工作管理", value="work_events", emoji="💼"),
            discord.SelectOption(
                label="向量库元数据", value="vector_db_metadata", emoji="🧠"
            ),
        ]
        for option in options:
            if option.value == self.current_table:
                option.default = True

        select = discord.ui.Select(placeholder="请选择要管理的模块...", options=options)
        select.callback = self.on_table_select
        return select

    async def on_table_select(self, interaction: discord.Interaction):
        """处理表格选择事件，启动对应的管理视图"""
        await interaction.response.defer()

        # Safely get the selected value
        selected_value = ""
        if interaction.data and isinstance(interaction.data, dict):
            values = cast(list, interaction.data.get("values", []))
            if values:
                selected_value = values[0]

        if not selected_value:
            return

        self.current_table = selected_value
        view: Optional[discord.ui.View] = None

        if self.message is None:
            log.error("DBView's message is None, cannot switch to a child view.")
            return

        if selected_value == "community_members":
            view = CommunityMembersView(self.author_id, self.message, self)
        elif selected_value == "general_knowledge":
            view = GeneralKnowledgeView(self.author_id, self.message, self)
        elif selected_value == "work_events":
            view = WorkEventsView(self.author_id, self.message, self)
        elif selected_value == "vector_db_metadata":
            view = VectorDBView(self.author_id, self.message, self)
        elif selected_value == "coin_management":
            view = CoinManagementView(interaction, self.message)

        if view and self.message:
            await view.update_view()
        else:
            await self.update_view()

    async def update_view(self):
        """更新导航视图本身"""
        embed = discord.Embed(
            title="🗂️ 数据库管理中心",
            description="请从下方的菜单中选择一个模块进行管理。",
            color=discord.Color.blurple(),
        )
        self._initialize_components()
        if self.message:
            await self.message.edit(embed=embed, view=self)
