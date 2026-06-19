import discord
import logging
from typing import List, Dict, Any
from discord.ext import commands

from src.chat.features.odysseia_coin.service.shop_service import (
    ShopData,
    shop_service,
)
from src.chat.features.events.ui.event_panel_view import EventPanelView
from .panels.shop_panel import ShopPanel
from .panels.daily_panel import DailyPanel
from .panels.tutorial_panel import TutorialPanel
from .components.shop_components import (
    CategorySelect,
    PurchaseButton,
    RefreshBalanceButton,
    LoanButton,
    WorkButton,
    SellBodyButton,
    LeaderboardButton,
    EventButton,
    KnowledgeBaseButton,
    DailyReportButton,
    DiaryButton,
    ChatGuidelinesButton,
    ToolListButton,
    FeedbackButton,
)

log = logging.getLogger(__name__)


def create_event_promo_embed(event_data: Dict[str, Any]) -> discord.Embed:
    """创建一个吸引人的活动推广Embed"""
    embed = discord.Embed(
        title=f"🎉 正在进行中: {event_data['event_name']} 🎉",
        description=event_data.get("description", "快来参加我们的特别活动吧！"),
        color=discord.Color.purple(),
    )
    if event_data.get("thumbnail_url"):
        embed.set_thumbnail(url=event_data["thumbnail_url"])
    embed.set_footer(text="点击下方的 '节日活动' 按钮加入我们！")
    return embed


class SimpleShopView(discord.ui.View):
    """简化版的商店视图，直接显示所有商品"""

    def __init__(
        self,
        bot: commands.Bot,
        author: discord.User | discord.Member,
        shop_data: ShopData,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.shop_data = shop_data
        self.interaction: discord.Interaction | None = None  # 将在 start 中被赋值
        self.selected_item_id: int | None = None

        # 从 shop_data 获取数据
        self.balance: int | None = shop_data.balance
        self.items = shop_data.items

        # 初始化面板
        self.shop_panel = ShopPanel(self)
        self.daily_panel = DailyPanel(self)

        # 按类别分组商品
        self.grouped_items = {}
        for item in self.items:
            category = item["category"]
            if category not in self.grouped_items:
                self.grouped_items[category] = []
            self.grouped_items[category].append(item)

        # 添加核心按钮
        self.add_item(CategorySelect(list(self.grouped_items.keys())))
        self.add_item(PurchaseButton())
        self.add_item(RefreshBalanceButton())
        self.add_item(LoanButton())
        self.add_item(WorkButton())
        self.add_item(SellBodyButton())
        self.add_item(LeaderboardButton())
        self.add_item(DailyReportButton())
        self.add_item(DiaryButton())

        # --- 动态添加按钮 ---
        if self.shop_data.active_event:
            self.add_item(EventButton())

        if self.shop_data.show_tutorial_button:
            self.add_item(KnowledgeBaseButton())

        # 添加聊天须知按钮
        self.add_item(ChatGuidelinesButton())

        # 添加类脑娘的工作清单按钮（包含工具设置和命令设置）
        self.add_item(ToolListButton())

        # 添加反馈按钮
        self.add_item(FeedbackButton())

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.interaction:
            try:
                await self.interaction.edit_original_response(view=self)
            except (discord.NotFound, discord.errors.InteractionResponded):
                pass  # 忽略可能的错误

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "这不是你的商店界面哦！", ephemeral=True
            )
            return False
        return True

    async def start(self, interaction: discord.Interaction):
        """启动视图并发送初始消息"""
        self.interaction = interaction
        initial_embeds = await self.create_shop_embeds()
        await self.interaction.response.send_message(
            embeds=initial_embeds, view=self, ephemeral=True
        )

    async def create_shop_embeds(self) -> List[discord.Embed]:
        """创建并返回所有需要在商店中显示的 Embeds"""
        embeds = []

        # 1. 公告 Embed
        if self.shop_data.announcement:
            announcement_embed = discord.Embed(
                description=self.shop_data.announcement,
                color=discord.Color.from_rgb(255, 182, 193),  # Light Pink
            )
            embeds.append(announcement_embed)

        # 2. 活动推广 Embed
        if self.shop_data.active_event:
            # EventPanelView 现在不需要 main_shop_view，因为它通过 interaction.view 访问
            event_panel = EventPanelView(
                event_data=self.shop_data.active_event, main_shop_view=self
            )
            event_promo_embed = await event_panel.create_event_embed()
            embeds.append(event_promo_embed)

        # 3. 主商店 Embed (通过 Panel 创建)
        main_shop_embed = await self.shop_panel.create_embed()
        embeds.append(main_shop_embed)

        return embeds

    async def _update_shop_embed(
        self, interaction: discord.Interaction, category: str | None = None
    ):
        """Helper to update the shop embed while preserving other embeds."""
        if not interaction.message:
            return
        new_shop_embed = await self.shop_panel.create_embed(category)

        current_embeds = interaction.message.embeds
        new_embeds_list = []
        shop_embed_found = False

        for embed in current_embeds:
            if embed.title == "类脑商店":
                new_embeds_list.append(new_shop_embed)
                shop_embed_found = True
            else:
                new_embeds_list.append(embed)

        if not shop_embed_found:
            new_embeds_list.append(new_shop_embed)

        try:
            await interaction.response.edit_message(embeds=new_embeds_list, view=self)
        except discord.errors.InteractionResponded:
            await interaction.followup.edit_message(
                message_id=interaction.message.id, embeds=new_embeds_list, view=self
            )


class TutorialManagementView(discord.ui.View):
    """View for managing a user's tutorials."""

    def __init__(
        self,
        bot: commands.Bot,
        author: discord.User | discord.Member,
        shop_data: ShopData,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.shop_data = shop_data
        self.interaction: discord.Interaction | None = None
        self.panel: TutorialPanel | None = None

    async def initialize(self, force_refresh: bool = False):
        """Async initialization for the view."""
        # Only fetch tutorials if they are not already loaded or if a refresh is forced
        if force_refresh or not self.shop_data.tutorials:
            tutorials = await shop_service.get_tutorials_by_author(self.author.id)
            self.shop_data.tutorials = tutorials

        if not self.panel:
            self.panel = TutorialPanel(self)

        self.update_components()

    def add_components(self):
        """(Deprecated) Will be replaced by update_components."""
        # This method is kept for compatibility during transition,
        # but update_components is the primary method now.
        self.update_components()

    def update_components(self):
        """Clears and adds components based on the panel's state."""
        if not self.panel:
            return

        self.clear_items()
        components = self.panel.get_components()
        for component in components:
            self.add_item(component)

    async def create_embed(self) -> discord.Embed:
        """Creates the embed for the view."""
        if not self.panel:
            return discord.Embed(title="错误", description="面板未初始化。")
        return await self.panel.create_embed()

    async def on_timeout(self):
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True
        if self.interaction:
            try:
                await self.interaction.edit_original_response(view=self)
            except (discord.NotFound, discord.errors.InteractionResponded):
                pass
