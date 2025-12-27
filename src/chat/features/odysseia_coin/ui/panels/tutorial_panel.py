from __future__ import annotations
from typing import TYPE_CHECKING, List
import discord
from datetime import datetime, timedelta
from enum import Enum, auto
from .base_panel import BasePanel
from src.chat.features.odysseia_coin.ui.components.shop_components import (
    AddTutorialButton,
    ManageTutorialsButton,
    BackToShopButton,
    TutorialActionSelect,
    EditTutorialButton,
    DeleteTutorialButton,
    BackToTutorialListButton,
)

if TYPE_CHECKING:
    from src.chat.features.odysseia_coin.ui.shop_ui import TutorialManagementView


class TutorialPanelState(Enum):
    LISTING = auto()
    MANAGING = auto()


class TutorialPanel(BasePanel["TutorialManagementView"]):
    def __init__(self, view: "TutorialManagementView"):
        super().__init__(view)
        self._state = TutorialPanelState.LISTING
        self.selected_tutorial_id: int | None = None

    def enter_management_mode(self):
        self._state = TutorialPanelState.MANAGING

    def enter_listing_mode(self):
        self._state = TutorialPanelState.LISTING
        self.selected_tutorial_id = None

    async def create_embed(self) -> discord.Embed:
        if self._state == TutorialPanelState.MANAGING:
            return self._create_management_embed()
        return await self._create_listing_embed()

    async def _create_listing_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="知识库管理",
            description="在这里管理你提交的教程。",
            color=discord.Color.blue(),
        )
        tutorials = self.shop_data.tutorials
        if not tutorials:
            embed.add_field(
                name="你的教程", value="你还没有提交任何教程。", inline=False
            )
        else:
            for tutorial in tutorials:
                created_at_utc = tutorial.get("created_at")
                if created_at_utc and isinstance(created_at_utc, datetime):
                    created_at_beijing = created_at_utc + timedelta(hours=8)
                    created_at_str = created_at_beijing.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    created_at_str = "日期未知"
                embed.add_field(
                    name=f"📝 {tutorial['title']}",
                    value=f"创建于: {created_at_str}",
                    inline=False,
                )
        return embed

    def _create_management_embed(self) -> discord.Embed:
        return discord.Embed(
            title="管理现有知识库",
            description="请从下方的下拉菜单中选择一个教程，然后选择你要执行的操作（编辑或删除）。",
            color=discord.Color.dark_orange(),
        )

    def get_components(self) -> List[discord.ui.Item]:
        if self._state == TutorialPanelState.MANAGING:
            return self._get_management_components()
        return self._get_listing_components()

    def _get_listing_components(self) -> List[discord.ui.Item]:
        return [
            AddTutorialButton(),
            ManageTutorialsButton(),
            BackToShopButton(),
        ]

    def _get_management_components(self) -> List[discord.ui.Item]:
        tutorials = self.shop_data.tutorials

        edit_button = EditTutorialButton()
        delete_button = DeleteTutorialButton()

        if self.selected_tutorial_id:
            edit_button.disabled = False
            delete_button.disabled = False

        return [
            TutorialActionSelect(tutorials),
            edit_button,
            delete_button,
            BackToTutorialListButton(),
        ]
