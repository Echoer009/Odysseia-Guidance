"""
本模块包含奥德赛币商店功能中使用的所有UI组件（按钮、选择菜单、模态框）。
"""

from __future__ import annotations
import discord
import logging
from typing import List, Dict, Any, TypeVar, cast, TYPE_CHECKING, Optional


from src.chat.services.event_service import event_service
from src.chat.features.events.ui.event_panel_view import EventPanelView
from src.chat.features.work_game.services.work_service import WorkService
from src.chat.features.work_game.services.sell_body_service import SellBodyService
from src.chat.features.work_game.services.work_db_service import WorkDBService
from ..leaderboard_ui import LeaderboardView
from src.chat.features.odysseia_coin.service.coin_service import (
    coin_service,
    PERSONAL_MEMORY_ITEM_EFFECT_ID,
    WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID,
    ENABLE_THREAD_REPLIES_EFFECT_ID,
    SELL_BODY_EVENT_SUBMISSION_EFFECT_ID,
)
from src.chat.features.chat_settings.ui.channel_settings_modal import ChatSettingsModal
from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config
import src.config as config
from src.chat.features.odysseia_coin.service.shop_service import shop_service
from src.chat.features.tools.tool_metadata import (
    get_all_tools_metadata,
)
from src.chat.features.tools.services.user_tool_settings_service import (
    user_tool_settings_service,
)
from src.database.database import AsyncSessionLocal
from src.database.models import CommunityMemberProfile
from sqlalchemy.future import select


if TYPE_CHECKING:
    from ..shop_ui import SimpleShopView, TutorialManagementView
    from discord.ext import commands

log = logging.getLogger(__name__)

# 使用 TypeVar 来指定视图类型，以获得更好的类型提示
ViewT = TypeVar("ViewT", bound=discord.ui.View)


# --- 基础组件 ---


class ShopButton(discord.ui.Button[ViewT]):
    """一个基础按钮类，为视图提供正确的类型提示。"""

    @property
    def view(self) -> ViewT:
        return cast(ViewT, super().view)


class ShopSelect(discord.ui.Select[ViewT]):
    """一个基础选择菜单类，为视图提供正确的类型提示。"""

    @property
    def view(self) -> ViewT:
        return cast(ViewT, super().view)


# --- 活动UI组件 ---


class EventButton(ShopButton["SimpleShopView"]):
    """进入当前活动视图的按钮。"""

    def __init__(self):
        super().__init__(
            label="节日活动", style=discord.ButtonStyle.primary, emoji="🎃"
        )

    async def callback(self, interaction: discord.Interaction):
        active_event = event_service.get_active_event()
        if not active_event:
            await interaction.response.send_message(
                "当前没有正在进行的活动哦。", ephemeral=True
            )
            return

        event_view = EventPanelView(event_data=active_event, main_shop_view=self.view)
        embed = await event_view.create_event_embed()
        await interaction.response.edit_message(embeds=[embed], view=event_view)


# --- 每日速报UI组件 ---


class DailyReportView(discord.ui.View):
    """用于显示每日速报的视图。"""

    def __init__(self, main_view: "SimpleShopView"):
        super().__init__(timeout=180)
        self.main_view = main_view

        back_button = discord.ui.Button(
            label="返回商店", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def create_embed(self) -> discord.Embed:
        """创建每日速报的嵌入消息。"""
        if hasattr(self.main_view, "daily_panel"):
            return await self.main_view.daily_panel.create_embed()
        return discord.Embed(
            title="错误", description="无法加载日报面板。", color=discord.Color.red()
        )

    async def back_callback(self, interaction: discord.Interaction):
        """返回主商店视图。"""
        embeds = await self.main_view.create_shop_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self.main_view)


class DailyReportButton(ShopButton["SimpleShopView"]):
    """打开每日速报视图的按钮。"""

    def __init__(self):
        super().__init__(
            label="每日速报", style=discord.ButtonStyle.primary, emoji="📅"
        )

    async def callback(self, interaction: discord.Interaction):
        if not hasattr(self.view, "daily_panel"):
            await interaction.response.send_message(
                "日报功能暂未开放。", ephemeral=True
            )
            return

        daily_view = DailyReportView(self.view)
        embed = await daily_view.create_embed()
        await interaction.response.edit_message(embeds=[embed], view=daily_view)


# --- 借贷UI组件 ---


class LoanModal(discord.ui.Modal, title="输入借款金额"):
    def __init__(self, loan_view: "LoanView"):
        super().__init__(timeout=180)
        self.loan_view = loan_view
        self.amount_input = discord.ui.TextInput(
            label=f"借款金额 (最多 {chat_config.COIN_CONFIG['MAX_LOAN_AMOUNT']})",
            placeholder="请输入你要借的类脑币数量",
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            await interaction.followup.send("❌ 金额必须是有效的数字。", ephemeral=True)
            return

        success, message = await coin_service.borrow_coins(interaction.user.id, amount)
        await interaction.followup.send(message, ephemeral=True)

        if success:
            await self.loan_view.refresh()


class LoanView(discord.ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        author: discord.User | discord.Member,
        main_view: "SimpleShopView",
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.main_view = main_view
        self.active_loan: Dict[str, Any] | None = None

    async def initialize(self):
        self.active_loan = await coin_service.get_active_loan(self.author.id)
        self.update_components()

    def update_components(self):
        self.clear_items()
        if self.active_loan:
            repay_button = discord.ui.Button(
                label=f"还款 {self.active_loan['amount']}",
                style=discord.ButtonStyle.success,
            )
            repay_button.callback = self.repay_callback
            self.add_item(repay_button)
        else:
            borrow_button = discord.ui.Button(
                label="借款", style=discord.ButtonStyle.primary
            )
            borrow_button.callback = self.borrow_callback
            self.add_item(borrow_button)

        back_button = discord.ui.Button(
            label="返回商店", style=discord.ButtonStyle.secondary
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    def create_loan_embed(self) -> discord.Embed:
        balance = (
            self.main_view.balance if self.main_view.balance is not None else "N/A"
        )
        if self.active_loan:
            desc = (
                f"你当前有一笔 **{self.active_loan['amount']}** 类脑币的贷款尚未还清。"
            )
        else:
            desc = f"你可以从类脑娘这里借款，最高可借 **{chat_config.COIN_CONFIG['MAX_LOAN_AMOUNT']}** 类脑币。"
        embed = discord.Embed(
            title="类脑币借贷中心", description=desc, color=discord.Color.blue()
        )
        embed.set_footer(text=f"你的余额: {balance} 类脑币")
        thumbnail_url = chat_config.COIN_CONFIG.get("LOAN_THUMBNAIL_URL")
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        return embed

    async def borrow_callback(self, interaction: discord.Interaction):
        modal = LoanModal(self)
        try:
            await interaction.response.send_modal(modal)
        except (discord.HTTPException, discord.ClientException):
            try:
                await interaction.followup.send(
                    "连接异常，请稍后再试。", ephemeral=True
                )
            except discord.HTTPException:
                pass

    async def repay_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success, message = await coin_service.repay_loan(self.author.id)
        await interaction.followup.send(message, ephemeral=True)
        if success:
            await self.refresh()

    async def back_callback(self, interaction: discord.Interaction):
        embeds = await self.main_view.create_shop_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self.main_view)

    async def refresh(self):
        await self.initialize()
        self.main_view.balance = await coin_service.get_balance(self.author.id)
        embed = self.create_loan_embed()
        if self.main_view.interaction:
            await self.main_view.interaction.edit_original_response(
                embeds=[embed], view=self
            )


# --- 主商店组件 ---


class CategorySelect(ShopSelect["SimpleShopView"]):
    """用于选择商品类别的选择菜单。"""

    def __init__(self, categories: List[str]):
        options = [
            discord.SelectOption(
                label=category,
                value=category,
                description=f"浏览 {category} 类别的商品",
                emoji="📁",
            )
            for category in categories
        ]
        super().__init__(
            placeholder="选择一个商品类别...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if view is None:
            return

        selected_category = self.values[0]
        item_select = ItemSelect(
            selected_category, view.grouped_items[selected_category]
        )
        view.clear_items()
        view.add_item(item_select)
        view.add_item(BackToCategoriesButton())
        view.add_item(PurchaseButton())
        view.add_item(RefreshBalanceButton())
        await view._update_shop_embed(interaction, category=selected_category)


class ItemSelect(ShopSelect["SimpleShopView"]):
    """用于选择特定商品的选择菜单。"""

    def __init__(self, category: str, items: List[Dict[str, Any]]):
        options = [
            discord.SelectOption(
                label=item["name"],
                value=str(item["item_id"]),
                description=f"{item['price']} 类脑币 - {item['description']}",
                emoji="🛒",
            )
            for item in items
        ]
        options = options[:25]
        super().__init__(
            placeholder=f"选择 {category} 中的商品...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_item_id = int(self.values[0])
        await interaction.response.defer()


class BackToCategoriesButton(ShopButton["SimpleShopView"]):
    """返回类别选择视图的按钮。"""

    def __init__(self):
        super().__init__(
            label="返回类别", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.view
        if view is None:
            return

        view.clear_items()
        view.add_item(CategorySelect(list(view.grouped_items.keys())))
        view.add_item(PurchaseButton())
        view.add_item(RefreshBalanceButton())
        await view._update_shop_embed(interaction)


class LoanButton(ShopButton["SimpleShopView"]):
    """打开借贷视图的按钮。"""

    def __init__(self):
        super().__init__(label="借贷", style=discord.ButtonStyle.primary, emoji="🏦")

    async def callback(self, interaction: discord.Interaction):
        loan_view = LoanView(self.view.bot, self.view.author, self.view)
        await loan_view.initialize()
        embed = loan_view.create_loan_embed()
        await interaction.response.edit_message(embeds=[embed], view=loan_view)


class WorkButton(ShopButton["SimpleShopView"]):
    """执行打工并赚取类脑币的按钮。"""

    def __init__(self):
        super().__init__(label="打工", style=discord.ButtonStyle.primary, emoji="🛠️")

    async def callback(self, interaction: discord.Interaction):
        work_db_service = WorkDBService()
        user_id = interaction.user.id

        is_on_cooldown, remaining_time = await work_db_service.check_work_cooldown(
            user_id
        )
        if is_on_cooldown:
            await interaction.response.send_message(
                f"你刚打完一份工，正在休息呢。请在 **{remaining_time}** 后再来吧！",
                ephemeral=True,
            )
            return

        is_limit_reached, count = await work_db_service.check_daily_limit(
            user_id, "work"
        )
        if is_limit_reached:
            await interaction.response.send_message(
                f"你今天已经工作了 **{count}** 次，够辛苦了，明天再来吧！",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        work_service = WorkService(coin_service)
        result_message = await work_service.perform_work(user_id)
        await interaction.followup.send(result_message, ephemeral=True)


class SellBodyButton(ShopButton["SimpleShopView"]):
    """“卖屁股”功能的按钮。"""

    def __init__(self):
        super().__init__(label="卖屁股", style=discord.ButtonStyle.primary, emoji="🥵")

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        await interaction.response.defer(ephemeral=True, thinking=True)
        sell_body_service = SellBodyService(coin_service)
        result = await sell_body_service.perform_sell_body(user_id)

        if result["success"]:
            embed_data = result["embed_data"]
            user = interaction.user
            event_name = embed_data["title"].lstrip("🥵").strip()
            title = f"{user.display_name} 选择了 {event_name}"
            description = f"{embed_data['description']}"
            footer_text = embed_data["reward_text"]
            embed = discord.Embed(
                title=title, description=description, color=discord.Color.pink()
            )
            if user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text=footer_text)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                f"<@{user_id}> {result['message']}", ephemeral=True
            )


class LeaderboardButton(ShopButton["SimpleShopView"]):
    """打开排行榜视图的按钮。"""

    def __init__(self):
        super().__init__(label="排行榜", style=discord.ButtonStyle.primary, emoji="🏆")

    async def callback(self, interaction: discord.Interaction):
        leaderboard_view = LeaderboardView(self.view.bot, self.view.author, self.view)
        embed = await leaderboard_view.create_leaderboard_embed()
        await interaction.response.edit_message(embeds=[embed], view=leaderboard_view)


class PurchaseButton(ShopButton["SimpleShopView"]):
    """购买所选商品的按钮。"""

    def __init__(self):
        super().__init__(label="购买", style=discord.ButtonStyle.primary, emoji="💰")

    async def callback(self, interaction: discord.Interaction):
        if self.view.selected_item_id is None:
            await interaction.response.send_message(
                "请先从下拉菜单中选择一个商品。", ephemeral=True
            )
            return

        selected_item = next(
            (
                item
                for item in self.view.items
                if item["item_id"] == self.view.selected_item_id
            ),
            None,
        )
        if not selected_item:
            await interaction.response.send_message("选择的商品无效。", ephemeral=True)
            return

        item_effect = selected_item.get("effect_id")

        if item_effect == PERSONAL_MEMORY_ITEM_EFFECT_ID:
            await self.handle_personal_memory_purchase(interaction, selected_item)
            return

        modal_effects = [
            WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID,
            SELL_BODY_EVENT_SUBMISSION_EFFECT_ID,
        ]
        if item_effect in modal_effects:
            await self.handle_standard_modal_purchase(interaction, selected_item)
            return

        await self.handle_standard_purchase(interaction, selected_item)

    async def handle_personal_memory_purchase(
        self, interaction: discord.Interaction, item: Dict[str, Any]
    ):
        current_balance = await coin_service.get_balance(interaction.user.id)
        if current_balance < item["price"]:
            await interaction.response.send_message(
                f"你的余额不足！需要 {item['price']} 类脑币，但你只有 {current_balance}。",
                ephemeral=True,
            )
            return

        from src.chat.features.personal_memory.ui.profile_purchase_modal import (
            PersonalProfilePurchaseModal,
        )

        purchase_info = {"item_id": item["item_id"], "price": item["price"]}
        modal = PersonalProfilePurchaseModal(purchase_info=purchase_info)
        await interaction.response.send_modal(modal)

    async def handle_standard_modal_purchase(
        self, interaction: discord.Interaction, item: Dict[str, Any]
    ):
        current_balance = await coin_service.get_balance(interaction.user.id)
        if current_balance < item["price"]:
            await interaction.response.send_message(
                f"你的余额不足！需要 {item['price']} 类脑币，但你只有 {current_balance}。",
                ephemeral=True,
            )
            return

        modal_map = {
            WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID: "src.chat.features.world_book.ui.contribution_modal.WorldBookContributionModal",
            SELL_BODY_EVENT_SUBMISSION_EFFECT_ID: "src.chat.features.work_game.ui.sell_body_submission_modal.SellBodySubmissionModal",
        }
        modal_path = modal_map.get(item["effect_id"])
        if not modal_path:
            await interaction.response.send_message(
                "无法找到此商品对应的功能。", ephemeral=True
            )
            return

        try:
            parts = modal_path.split(".")
            module_path, class_name = ".".join(parts[:-1]), parts[-1]
            module = __import__(module_path, fromlist=[class_name])
            ModalClass = getattr(module, class_name)
            purchase_info = {"item_id": item["item_id"], "price": item["price"]}
            modal = ModalClass(purchase_info=purchase_info)
            await interaction.response.send_modal(modal)
        except (ImportError, AttributeError) as e:
            log.error(f"动态加载模态框失败: {e}", exc_info=True)
            await interaction.response.send_message(
                "打开功能界面时出错，请联系管理员。", ephemeral=True
            )

    async def handle_standard_purchase(
        self, interaction: discord.Interaction, item: Dict[str, Any]
    ):
        await interaction.response.defer(ephemeral=True)
        (
            success,
            message,
            new_balance,
            should_show_modal,
            embed_data,
            cg_url,
        ) = await coin_service.purchase_item(
            interaction.user.id,
            interaction.guild.id if interaction.guild else 0,
            item["item_id"],
        )

        final_message = message

        # 检查是否需要显示对话块管理面板
        if success and message == "show_conversation_blocks_panel":
            await self._show_conversation_blocks_panel(interaction, item, new_balance)
            return

        if success and embed_data:
            embed = discord.Embed(
                title=embed_data["title"],
                description=embed_data["description"],
                color=discord.Color.blue(),
            )
            await interaction.followup.send(message, embed=embed, ephemeral=True)
        elif success and cg_url:
            # 购买成功且有CG图片URL，显示提示和图片链接
            final_message = f"{message}\n\n{cg_url}"
            await interaction.followup.send(final_message, ephemeral=True)
        else:
            await interaction.followup.send(final_message, ephemeral=True)

        if success:
            self.view.balance = new_balance
            await self.view._update_shop_embed(interaction)

            if (
                should_show_modal
                and item.get("effect_id") == ENABLE_THREAD_REPLIES_EFFECT_ID
            ):
                await self.handle_thread_settings_modal(interaction)

    async def _show_conversation_blocks_panel(
        self,
        interaction: discord.Interaction,
        item: Dict[str, Any],
        new_balance: Optional[int],
    ):
        """显示对话块管理面板"""
        from src.chat.features.personal_memory.ui.user_conversation_blocks_view import (
            UserConversationBlocksView,
        )

        # 创建初始 Embed
        embed = discord.Embed(
            title="💬 对话记忆管理",
            description="正在加载你的对话记忆...",
            color=discord.Color.purple(),
        )

        # 发送初始消息并获取该消息对象
        # followup.send 返回 WebhookMessage，可以直接用于后续编辑
        message = await interaction.followup.send(
            embed=embed, ephemeral=True, wait=True
        )

        # 创建视图
        view = UserConversationBlocksView(
            user_id=interaction.user.id,
            message=message,
        )
        await view.initialize()

        # 更新视图
        embed = await view._build_embed()
        await message.edit(embed=embed, view=view)

        # 更新商店余额显示
        if new_balance is not None:
            self.view.balance = new_balance
            await self.view._update_shop_embed(interaction)

    async def handle_thread_settings_modal(self, interaction: discord.Interaction):
        try:
            user_settings = await coin_service.get_thread_cooldown_settings(
                interaction.user.id
            )
            current_config = {}
            if user_settings:
                current_config = {
                    "cooldown_seconds": user_settings["thread_cooldown_seconds"],
                    "cooldown_duration": user_settings["thread_cooldown_duration"],
                    "cooldown_limit": user_settings["thread_cooldown_limit"],
                }

            async def modal_callback(
                modal_interaction: discord.Interaction, settings: Dict[str, Any]
            ):
                await coin_service.update_thread_cooldown_settings(
                    interaction.user.id, settings
                )
                await modal_interaction.response.send_message(
                    "✅ 你的个人帖子冷却设置已保存！", ephemeral=True
                )

            modal = ChatSettingsModal(
                title="设置你的帖子默认冷却",
                current_config=current_config,
                on_submit_callback=modal_callback,
                include_enable_option=False,
            )

            view = discord.ui.View(timeout=180)
            button = discord.ui.Button(
                label="点此设置帖子冷却", style=discord.ButtonStyle.primary
            )

            async def button_callback(interaction: discord.Interaction):
                await interaction.response.send_modal(modal)
                button.disabled = True
                await interaction.edit_original_response(view=view)

            button.callback = button_callback
            view.add_item(button)

            await interaction.followup.send(
                "请点击下方按钮来配置你的帖子或子区里类脑娘的活跃时间,默认是1分钟两次哦",
                view=view,
                ephemeral=True,
            )
        except Exception as e:
            log.error(
                f"为用户 {interaction.user.id} 显示帖子冷却设置模态框时出错: {e}",
                exc_info=True,
            )
            await interaction.followup.send(
                "❌ 打开设置界面时遇到问题，但你的购买已成功。请联系管理员。",
                ephemeral=True,
            )


class RefreshBalanceButton(ShopButton["SimpleShopView"]):
    """刷新用户类脑币余额的按钮。"""

    def __init__(self):
        super().__init__(
            label="刷新余额", style=discord.ButtonStyle.primary, emoji="🔄"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_balance = await coin_service.get_balance(interaction.user.id)
        if new_balance is not None:
            self.view.balance = new_balance
        await self.view._update_shop_embed(interaction)
        await interaction.followup.send("余额已刷新。", ephemeral=True)


# --- 教程/知识库组件 ---


class BackToShopButton(ShopButton["TutorialManagementView"]):
    """返回主商店视图的按钮。"""

    def __init__(self):
        super().__init__(
            label="返回商店", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )

    async def callback(self, interaction: discord.Interaction):
        # 我们需要重新创建主商店视图
        from ..shop_ui import SimpleShopView

        main_view = SimpleShopView(self.view.bot, self.view.author, self.view.shop_data)
        main_view.interaction = interaction  # 保持状态至关重要

        embeds = await main_view.create_shop_embeds()
        await interaction.response.edit_message(embeds=embeds, view=main_view)


class TutorialModal(discord.ui.Modal, title="添加新的知识库教程"):
    # <--- 修改 2: __init__ 接收视图
    def __init__(self, view: "TutorialManagementView"):
        super().__init__(timeout=300)
        self.view = view  # 存储视图
        self.title_input = discord.ui.TextInput(
            label="教程标题",
            placeholder="请输入一个简洁明了的标题",
            style=discord.TextStyle.short,
            required=True,
            max_length=100,
        )
        self.description_input = discord.ui.TextInput(
            label="教程描述/内容",
            placeholder="请详细输入教程的内容...",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
        )
        self.add_item(self.title_input)
        self.add_item(self.description_input)

    # <--- 修改 3: 实现 on_submit 逻辑
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        thread_id = self.view.shop_data.thread_id
        if not thread_id:
            await interaction.followup.send(
                "❌ 错误：无法找到当前帖子的ID。请确保你在一个帖子中。", ephemeral=True
            )
            return

        success = await shop_service.add_tutorial(
            title=self.title_input.value,
            description=self.description_input.value,
            author_id=interaction.user.id,
            author_name=interaction.user.display_name,
            thread_id=thread_id,
        )

        if success:
            await interaction.followup.send("✅ 你的教程已成功提交！", ephemeral=True)
            # 刷新视图以显示新教程
            await self.view.initialize()
            embed = await self.view.create_embed()
            if self.view.interaction:
                # 使用原始交互来编辑消息
                await self.view.interaction.edit_original_response(
                    embeds=[embed], view=self.view
                )
        else:
            await interaction.followup.send(
                "❌ 提交教程时发生错误，请稍后再试或联系管理员。", ephemeral=True
            )


class EditTutorialModal(discord.ui.Modal, title="编辑知识库教程"):
    def __init__(
        self,
        view: "TutorialManagementView",
        tutorial_id: int,
        current_data: Dict[str, Any],
    ):
        super().__init__(timeout=300)
        self.view = view
        self.tutorial_id = tutorial_id
        self.title_input = discord.ui.TextInput(
            label="教程标题",
            style=discord.TextStyle.short,
            required=True,
            max_length=100,
            default=current_data.get("title", ""),
        )
        self.description_input = discord.ui.TextInput(
            label="教程描述/内容",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=2000,
            default=current_data.get("description", ""),
        )
        self.add_item(self.title_input)
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # 我们接下来将实现服务层
        success = await shop_service.update_tutorial(
            tutorial_id=self.tutorial_id,
            title=self.title_input.value,
            description=self.description_input.value,
            author_id=interaction.user.id,
        )

        if success:
            await interaction.followup.send("✅ 你的教程已成功更新！", ephemeral=True)
            # 刷新视图
            await self.view.initialize(force_refresh=True)
            panel = self.view.panel
            if panel:
                panel.enter_listing_mode()  # 编辑后返回列表视图
            self.view.update_components()
            embed = await self.view.create_embed()
            if self.view.interaction:
                await self.view.interaction.edit_original_response(
                    embeds=[embed], view=self.view
                )
        else:
            await interaction.followup.send(
                "❌ 更新教程时发生错误，请稍后再试或联系管理员。", ephemeral=True
            )


class SearchModeButton(ShopButton["TutorialManagementView"]):
    """切换当前帖子搜索模式的按钮。"""

    def __init__(self):
        super().__init__(
            label="切换搜索模式", style=discord.ButtonStyle.primary, emoji="🔍"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        from src.chat.features.tutorial_search.services.thread_settings_service import (
            thread_settings_service,
        )

        thread_id = self.view.shop_data.thread_id
        if not thread_id:
            await interaction.followup.send(
                "❌ 错误：无法找到当前帖子的ID。请确保你在一个帖子中。", ephemeral=True
            )
            return

        # 获取当前模式
        current_mode = await thread_settings_service.get_search_mode(str(thread_id))

        # 切换模式
        new_mode = "PRIORITY" if current_mode == "ISOLATED" else "ISOLATED"
        await thread_settings_service.set_search_mode(str(thread_id), new_mode)

        # 刷新视图
        await self.view.initialize()
        self.view.update_components()
        embed = await self.view.create_embed()
        await interaction.edit_original_response(embeds=[embed], view=self.view)


class AddTutorialButton(ShopButton["TutorialManagementView"]):
    """添加新教程的按钮。"""

    def __init__(self):
        super().__init__(
            label="添加新知识库", style=discord.ButtonStyle.success, emoji="➕"
        )

    async def callback(self, interaction: discord.Interaction):
        modal = TutorialModal(self.view)
        await interaction.response.send_modal(modal)


class KnowledgeBaseButton(ShopButton["SimpleShopView"]):
    """打开教程管理视图的按钮。"""

    def __init__(self):
        super().__init__(
            label="知识库管理", style=discord.ButtonStyle.primary, emoji="📚"
        )

    async def callback(self, interaction: discord.Interaction):
        from ..shop_ui import TutorialManagementView

        # 此视图将在下一步中创建
        tutorial_view = TutorialManagementView(
            bot=self.view.bot, author=self.view.author, shop_data=self.view.shop_data
        )
        await tutorial_view.initialize()
        embed = await tutorial_view.create_embed()
        await interaction.response.edit_message(embeds=[embed], view=tutorial_view)


class ConfirmationModal(discord.ui.Modal, title="确认删除"):
    """一个用于确认操作的简单模态框。"""

    def __init__(self, on_confirm_callback):
        super().__init__(timeout=180)
        self._on_confirm = on_confirm_callback
        self.add_item(
            discord.ui.TextInput(
                label="输入 '确认删除' 以继续",
                placeholder="确认删除",
                style=discord.TextStyle.short,
                required=True,
                max_length=4,
            )
        )

    async def on_submit(self, interaction: discord.Interaction):
        text_input = cast(discord.ui.TextInput, self.children[0])
        if text_input.value.strip().lower() == "确认删除":
            await self._on_confirm(interaction)
        else:
            await interaction.response.send_message(
                "输入不匹配，操作已取消。", ephemeral=True
            )


class ManageTutorialsButton(ShopButton["TutorialManagementView"]):
    """管理现有教程的按钮。"""

    def __init__(self):
        super().__init__(
            label="管理现有知识库", style=discord.ButtonStyle.secondary, emoji="📝"
        )

    async def callback(self, interaction: discord.Interaction):
        panel = self.view.panel
        if not panel:
            await interaction.response.send_message(
                "发生错误，无法找到教程面板。", ephemeral=True
            )
            return

        tutorials = self.view.shop_data.tutorials
        if not tutorials:
            await interaction.response.send_message(
                "你还没有可以管理的教程。", ephemeral=True
            )
            return

        # 调用面板的方法切换到管理模式
        panel.enter_management_mode()
        self.view.update_components()  # 视图现在将从面板获取组件

        # 使用新的嵌入和组件更新消息
        embed = await self.view.create_embed()
        await interaction.response.edit_message(embeds=[embed], view=self.view)


class TutorialActionSelect(ShopSelect["TutorialManagementView"]):
    """一个用于选择要执行操作（编辑/删除）的教程的选择菜单。"""

    def __init__(self, tutorials: List[Dict[str, Any]]):
        options = [
            discord.SelectOption(
                label=tutorial["title"][:100],  # 标签最多100个字符
                value=str(tutorial["id"]),
                description=f"ID: {tutorial['id']}",
                emoji="📝",
            )
            for tutorial in tutorials
        ]
        options = options[:25]  # 最多25个选项
        super().__init__(
            placeholder="选择一个你要操作的教程...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        panel = self.view.panel
        assert panel is not None
        panel.selected_tutorial_id = int(self.values[0])
        # 视图的 update_components 将处理按钮状态
        self.view.update_components()
        await interaction.response.edit_message(view=self.view)


class EditTutorialButton(ShopButton["TutorialManagementView"]):
    """编辑所选教程的按钮。"""

    def __init__(self):
        super().__init__(
            label="编辑教程",
            style=discord.ButtonStyle.primary,
            emoji="✏️",
        )

    async def callback(self, interaction: discord.Interaction):
        panel = self.view.panel
        assert panel is not None
        if not panel.selected_tutorial_id:
            await interaction.response.send_message(
                "请先从下拉菜单中选择一个要编辑的教程。", ephemeral=True
            )
            return

        # 获取完整的教程数据
        tutorial_data = await shop_service.get_tutorial_by_id(
            panel.selected_tutorial_id
        )
        if not tutorial_data:
            await interaction.response.send_message(
                "❌ 无法找到所选教程的数据，它可能已被删除。", ephemeral=True
            )
            return

        # 打开预填充数据的模态框
        modal = EditTutorialModal(
            view=self.view,
            tutorial_id=panel.selected_tutorial_id,
            current_data=tutorial_data,
        )
        await interaction.response.send_modal(modal)


class DeleteTutorialButton(ShopButton["TutorialManagementView"]):
    """删除所选教程的按钮。"""

    def __init__(self):
        super().__init__(
            label="删除教程",
            style=discord.ButtonStyle.danger,
            emoji="🗑️",
            disabled=True,
        )

    async def callback(self, interaction: discord.Interaction):
        panel = self.view.panel
        assert panel is not None
        if not panel.selected_tutorial_id:
            await interaction.response.send_message(
                "请先选择一个教程。", ephemeral=True
            )
            return

        async def confirm_delete_callback(modal_interaction: discord.Interaction):
            await modal_interaction.response.defer(ephemeral=True)

            tutorial_id_to_delete = panel.selected_tutorial_id
            if not tutorial_id_to_delete:
                await modal_interaction.followup.send(
                    "❌ 发生错误：没有选中的教程。", ephemeral=True
                )
                return

            success = await shop_service.delete_tutorial(
                tutorial_id=tutorial_id_to_delete, author_id=interaction.user.id
            )

            if success:
                await modal_interaction.followup.send(
                    "✅ 教程已成功删除。", ephemeral=True
                )
                # 刷新视图
                await self.view.initialize(force_refresh=True)
                panel.enter_listing_mode()
                self.view.update_components()
                embed = await self.view.create_embed()
                if self.view.interaction:
                    await self.view.interaction.edit_original_response(
                        embeds=[embed], view=self.view
                    )
            else:
                await modal_interaction.followup.send(
                    "❌ 删除失败。你可能不是该教程的作者，或者教程已被删除。",
                    ephemeral=True,
                )

        modal = ConfirmationModal(on_confirm_callback=confirm_delete_callback)
        await interaction.response.send_modal(modal)


class BackToTutorialListButton(ShopButton["TutorialManagementView"]):
    """返回主教程管理面板的按钮。"""

    def __init__(self):
        super().__init__(label="返回列表", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        panel = self.view.panel
        assert panel is not None
        panel.enter_listing_mode()
        self.view.update_components()
        embed = await self.view.create_embed()
        await interaction.response.edit_message(embeds=[embed], view=self.view)


# --- 工具设置UI组件 ---


class ToolListButton(ShopButton["SimpleShopView"]):
    """打开工具设置视图的按钮。"""

    def __init__(self):
        super().__init__(
            label="类脑娘的工作清单", style=discord.ButtonStyle.primary, emoji="🗒️"
        )

    async def callback(self, interaction: discord.Interaction):
        tool_settings_view = ToolSettingsView(main_view=self.view)
        await tool_settings_view.initialize(interaction.user)
        embed = await tool_settings_view.create_embed()
        await interaction.response.edit_message(embeds=[embed], view=tool_settings_view)


class ToolSettingsView(discord.ui.View):
    """管理用户工具设置、命令设置和人设风格的视图。"""

    MODE_TOOLS = "tools"
    MODE_COMMANDS = "commands"
    MODE_PERSONA = "persona"
    MODE_PROFILE_CARD = "profile_card"

    def __init__(self, main_view: "SimpleShopView"):
        super().__init__(timeout=300)
        self.main_view = main_view
        self.user: discord.User | discord.Member | None = None
        self.current_mode: str = self.MODE_TOOLS

        # 工具设置相关
        self.user_tool_settings: Dict[str, Any] | None = None
        self.all_tools: Dict[str, Dict[str, Any]] = {}

        # 命令设置相关
        self.user_command_settings: Dict[str, Any] | None = None
        self.all_commands: Dict[str, Dict[str, str]] = {}

        # 人设风格相关
        self.persona_style: str = "default"

        # 名片相关
        self.profile_data: Dict[str, Any] | None = None

        self.confirmation_message: str | None = None

    async def initialize(self, user: discord.User | discord.Member):
        self.user = user

        # 初始化工具设置
        self.user_tool_settings = (
            await user_tool_settings_service.get_user_tool_settings(str(user.id))
        )
        self.all_tools = get_all_tools_metadata()
        # 获取系统保留的工具列表（用户无法禁用）
        from src.chat.features.tools.services.global_tool_settings_service import (
            global_tool_settings_service,
        )

        self.protected_tools = await global_tool_settings_service.get_protected_tools()

        # 初始化命令设置
        from src.chat.features.affection.services.user_command_settings_service import (
            user_command_settings_service,
        )

        self.user_command_settings = (
            await user_command_settings_service.get_user_command_settings(str(user.id))
        )
        self.all_commands = user_command_settings_service.get_configurable_commands()

        # 初始化人设风格
        from src.chat.services.persona_preference_service import (
            persona_preference_service,
        )

        self.persona_style = await persona_preference_service.get_persona_style(
            str(user.id)
        )

        async with AsyncSessionLocal() as session:
            stmt = select(CommunityMemberProfile).where(
                CommunityMemberProfile.discord_id == str(user.id)
            )
            result = await session.execute(stmt)
            profile = result.scalars().first()
            if profile:
                self.profile_data = {
                    "title": profile.title,
                    "source_metadata": profile.source_metadata,
                    "personal_summary": profile.personal_summary,
                    "created_at": profile.created_at,
                    "updated_at": profile.updated_at,
                }

        self.add_components()

    def add_components(self):
        """根据当前模式向视图添加组件。"""
        self.clear_items()

        if self.current_mode == self.MODE_TOOLS:
            self.add_item(
                ToolToggleSelect(
                    self.all_tools, self.user_tool_settings, self.protected_tools
                )
            )
        elif self.current_mode == self.MODE_COMMANDS:
            self.add_item(
                CommandToggleSelect(self.all_commands, self.user_command_settings)
            )
        elif self.current_mode == self.MODE_PERSONA:
            self.add_item(PersonaButtonDefault(self.persona_style))
            self.add_item(PersonaButtonGentle(self.persona_style))
            self.add_item(PersonaButtonFrank(self.persona_style))

        if self.current_mode == self.MODE_PROFILE_CARD:
            back_button = discord.ui.Button(
                label="返回工作清单",
                style=discord.ButtonStyle.secondary,
                emoji="⬅️",
                row=0,
            )
            back_button.callback = self._back_to_tool_list_callback
            self.add_item(back_button)

            return_to_shop = discord.ui.Button(
                label="返回商店",
                style=discord.ButtonStyle.secondary,
                emoji="🏠",
                row=0,
            )
            return_to_shop.callback = self.back_callback
            self.add_item(return_to_shop)
        else:
            mode_labels = {
                self.MODE_TOOLS: ("切换到命令设置", self.MODE_COMMANDS),
                self.MODE_COMMANDS: ("切换到人设风格", self.MODE_PERSONA),
                self.MODE_PERSONA: ("切换到工具设置", self.MODE_TOOLS),
            }
            label, _ = mode_labels[self.current_mode]
            switch_button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.primary,
                emoji="🔄",
                row=1,
            )
            switch_button.callback = self.switch_mode_callback
            self.add_item(switch_button)

            back_button = discord.ui.Button(
                label="返回商店", style=discord.ButtonStyle.secondary, emoji="⬅️", row=1
            )
            back_button.callback = self.back_callback
            self.add_item(back_button)

            self.add_item(ViewProfileCardButton())

    async def switch_mode_callback(self, interaction: discord.Interaction):
        """切换工具/命令/人设模式。"""
        mode_cycle = {
            self.MODE_TOOLS: self.MODE_COMMANDS,
            self.MODE_COMMANDS: self.MODE_PERSONA,
            self.MODE_PERSONA: self.MODE_TOOLS,
        }
        self.current_mode = mode_cycle[self.current_mode]

        self.add_components()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def create_embed(self) -> discord.Embed:
        """根据当前模式创建嵌入消息。"""
        if self.current_mode == self.MODE_PROFILE_CARD:
            return self._create_profile_card_embed()

        if self.current_mode == self.MODE_TOOLS:
            title = "🗒️ 类脑娘的工作清单 - 工具设置"
            description = "在这里可以设置类脑娘在你的帖子里能使用哪些工具哦～\n默认情况下所有工具都是开启的。"
            color = discord.Color.blue()
        elif self.current_mode == self.MODE_COMMANDS:
            title = "🗒️ 类脑娘的工作清单 - 命令设置"
            description = (
                "在这里可以设置其他人在你的帖子里能使用哪些命令哦～\n"
                "默认情况下所有命令都是开启的。\n"
                "⚠️ 注意：这些设置只影响**你的帖子**中别人使用的命令，不影响你自己使用命令。"
            )
            color = discord.Color.purple()
        else:
            title = "🗒️ 类脑娘的工作清单 - 你希望类脑娘是?"
            style_display = {
                "default": "这样就好",
                "gentle": "更温柔些",
                "frank": "坦率一点",
            }.get(self.persona_style, self.persona_style)
            description = (
                f"当前选择: **{style_display}**\n\n"
                "选择你喜欢的类脑娘风格吧～\n"
                "• **这样就好** — 保持类脑娘原本的性格\n"
                "• **更温柔些** — 类脑娘会变得更加温柔体贴\n"
                "• **坦率一点** — 类脑娘会变得更坦率直接"
            )
            color = discord.Color.green()

        if self.confirmation_message:
            description = f"✅ {self.confirmation_message}\n\n{description}"
            self.confirmation_message = None

        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
        )
        return embed

    def _create_profile_card_embed(self) -> discord.Embed:
        """创建名片嵌入消息。"""
        if not self.profile_data:
            return discord.Embed(
                title="🪪 我的名片",
                description="类脑娘还不认识你\n\n如果你想让类脑娘记住你，可以在商店购买**名片**哦～",
                color=discord.Color.dark_grey(),
            )

        metadata = self.profile_data.get("source_metadata") or {}
        name = metadata.get("name") or self.profile_data.get("title") or "未知"
        personality = metadata.get("personality", "")
        background = metadata.get("background", "")
        preferences = metadata.get("preferences", "")
        personal_summary = self.profile_data.get("personal_summary")

        embed = discord.Embed(
            title="🪪 我的名片",
            description=f"**{name}** 交给类脑娘的名片",
            color=discord.Color.gold(),
        )

        if personality:
            embed.add_field(name="性格特点", value=personality, inline=False)
        if background:
            embed.add_field(name="背景信息", value=background, inline=False)
        if preferences:
            embed.add_field(name="喜好偏好", value=preferences, inline=False)
        if personal_summary:
            embed.add_field(
                name="类脑娘对你的印象",
                value=personal_summary,
                inline=False,
            )

        updated_at = self.profile_data.get("updated_at")
        if updated_at:
            embed.set_footer(text=f"最后更新: {updated_at.strftime('%Y-%m-%d %H:%M')}")

        return embed

    async def back_callback(self, interaction: discord.Interaction):
        """返回主商店视图。"""
        embeds = await self.main_view.create_shop_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self.main_view)

    async def _back_to_tool_list_callback(self, interaction: discord.Interaction):
        """从名片视图返回工作清单。"""
        self.current_mode = self.MODE_TOOLS
        self.add_components()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class ViewProfileCardButton(discord.ui.Button):
    """查看自己名片的按钮。"""

    def __init__(self):
        super().__init__(
            label="我的名片", style=discord.ButtonStyle.secondary, emoji="🪪", row=2
        )

    async def callback(self, interaction: discord.Interaction):
        view = cast(ToolSettingsView, self.view)
        view.current_mode = ToolSettingsView.MODE_PROFILE_CARD
        view.add_components()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PersonaButtonDefault(discord.ui.Button):
    """选择默认人设风格的按钮。"""

    def __init__(self, current_style: str):
        is_current = current_style == "default"
        super().__init__(
            label="✅ 这样就好" if is_current else "这样就好",
            style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.secondary,
            emoji="😊",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        from src.chat.services.persona_preference_service import (
            persona_preference_service,
        )

        view = cast(ToolSettingsView, self.view)
        await persona_preference_service.set_persona_style(
            str(interaction.user.id), "default"
        )
        view.persona_style = "default"
        view.confirmation_message = "已设置为默认风格～"
        view.add_components()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PersonaButtonGentle(discord.ui.Button):
    """选择温柔人设风格的按钮。"""

    def __init__(self, current_style: str):
        is_current = current_style == "gentle"
        super().__init__(
            label="✅ 更温柔些" if is_current else "更温柔些",
            style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.secondary,
            emoji="🌸",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        from src.chat.services.persona_preference_service import (
            persona_preference_service,
        )

        view = cast(ToolSettingsView, self.view)
        await persona_preference_service.set_persona_style(
            str(interaction.user.id), "gentle"
        )
        view.persona_style = "gentle"
        view.confirmation_message = "已设置为温柔风格～"
        view.add_components()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PersonaButtonFrank(discord.ui.Button):
    """选择坦率人设风格的按钮。"""

    def __init__(self, current_style: str):
        is_current = current_style == "frank"
        super().__init__(
            label="✅ 坦率一点" if is_current else "坦率一点",
            style=discord.ButtonStyle.success if is_current else discord.ButtonStyle.secondary,
            emoji="😏",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        from src.chat.services.persona_preference_service import (
            persona_preference_service,
        )

        view = cast(ToolSettingsView, self.view)
        await persona_preference_service.set_persona_style(
            str(interaction.user.id), "frank"
        )
        view.persona_style = "frank"
        view.confirmation_message = "已设置为坦率风格～"
        view.add_components()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class ToolToggleSelect(discord.ui.Select):
    """用于启用/禁用工具的选择菜单。"""

    def __init__(
        self,
        all_tools: Dict[str, Dict[str, Any]],
        user_settings: Dict[str, Any] | None,
        protected_tools: List[str] | None = None,
    ):
        options = []
        enabled_tools = user_settings.get("enabled_tools") if user_settings else None
        # 使用传入的 protected_tools 参数（系统保留的工具，用户无法禁用）
        protected = set(protected_tools or [])

        for tool_name, meta in all_tools.items():
            # 过滤掉不允许用户控制的工具（系统保留工具）
            if tool_name in protected:
                continue
            # 如果 user_settings 为 None，则默认启用所有工具。
            # 如果数据库中的 enabled_tools 为 None，则默认启用所有工具。
            is_enabled = enabled_tools is None or tool_name in enabled_tools
            options.append(
                discord.SelectOption(
                    label=meta["name"],
                    value=tool_name,
                    description=meta["description"],
                    emoji=meta["emoji"],
                    default=is_enabled,
                )
            )

        super().__init__(
            placeholder="选择要开启/关闭的工具...",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        view = cast(ToolSettingsView, self.view)
        user_id = str(interaction.user.id)

        # 将UI中选择的工具保存到数据库
        new_enabled_set = set(self.values) if self.values else set()

        await user_tool_settings_service.save_user_tool_settings(
            user_id, {"enabled_tools": list(new_enabled_set)}
        )

        # 更新视图中的用户设置
        view.user_tool_settings = (
            await user_tool_settings_service.get_user_tool_settings(user_id)
        )

        # 设置确认消息并更新原始消息
        view.confirmation_message = "工具设置已保存！"
        view.add_components()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class CommandToggleSelect(discord.ui.Select):
    """用于启用/禁用命令的选择菜单。"""

    def __init__(
        self,
        all_commands: Dict[str, Dict[str, str]],
        user_settings: Dict[str, Any] | None,
    ):
        options = []
        enabled_commands = (
            user_settings.get("enabled_commands") if user_settings else None
        )

        for cmd_name, meta in all_commands.items():
            # 如果 user_settings 为 None，则默认启用所有命令。
            # 如果数据库中的 enabled_commands 为 None，则默认启用所有命令。
            is_enabled = enabled_commands is None or cmd_name in enabled_commands
            options.append(
                discord.SelectOption(
                    label=meta["name"],
                    value=cmd_name,
                    description=meta["description"],
                    emoji=meta.get("emoji"),
                    default=is_enabled,
                )
            )

        super().__init__(
            placeholder="选择要在你的帖子里开启的命令...",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        from src.chat.features.affection.services.user_command_settings_service import (
            user_command_settings_service,
        )

        view = cast(ToolSettingsView, self.view)
        user_id = str(interaction.user.id)

        # 将UI中选择的命令保存到数据库
        new_enabled_set = set(self.values) if self.values else set()

        await user_command_settings_service.save_user_command_settings(
            user_id, {"enabled_commands": list(new_enabled_set)}
        )

        # 更新视图中的用户命令设置
        view.user_command_settings = (
            await user_command_settings_service.get_user_command_settings(user_id)
        )

        # 设置确认消息并更新原始消息
        view.confirmation_message = "命令设置已保存！"
        view.add_components()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


# --- 反馈UI组件 ---


class FeedbackModal(discord.ui.Modal, title="📝 提交反馈"):
    """用户提交反馈的模态框，包含标题和内容两个字段。"""

    title_input = discord.ui.TextInput(
        label="反馈标题",
        placeholder="简要描述你的反馈",
        style=discord.TextStyle.short,
        required=True,
        max_length=100,
    )
    content_input = discord.ui.TextInput(
        label="反馈内容",
        placeholder="详细写下你的想法、建议或遇到的问题…",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1500,
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=180)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        # 构建反馈 Embed
        user = interaction.user
        embed = discord.Embed(
            title=f"💬 新反馈 — {self.title_input.value}",
            description=self.content_input.value,
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_author(
            name=f"{user.display_name} ({user.name})",
            icon_url=user.display_avatar.url if user.display_avatar else None,
        )
        embed.add_field(name="用户 ID", value=str(user.id), inline=True)

        # 发送私信给所有开发者
        for dev_id in config.DEVELOPER_USER_IDS:
            try:
                dev_user = await self.bot.fetch_user(dev_id)
                await dev_user.send(embed=embed)
            except discord.Forbidden:
                log.warning(f"无法向开发者 {dev_id} 发送反馈私信（权限被拒绝）。")
            except Exception as e:
                log.error(f"向开发者 {dev_id} 发送反馈私信时出错: {e}")

        await interaction.response.send_message(
            "✅ 感谢你的反馈！已成功提交。", ephemeral=True
        )


class FeedbackButton(ShopButton["SimpleShopView"]):
    """打开反馈模态框的按钮。"""

    def __init__(self):
        super().__init__(
            label="反馈", style=discord.ButtonStyle.primary, emoji="💬"
        )

    async def callback(self, interaction: discord.Interaction):
        modal = FeedbackModal(bot=self.view.bot)
        await interaction.response.send_modal(modal)
