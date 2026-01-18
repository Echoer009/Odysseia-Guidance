"""
This module contains all the UI components (Buttons, Selects, Modals)
used in the Odysseia Coin Shop feature.
"""

from __future__ import annotations
import discord
import logging
from typing import List, Dict, Any, TypeVar, cast, TYPE_CHECKING


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
    COMMUNITY_MEMBER_UPLOAD_EFFECT_ID,
    ENABLE_THREAD_REPLIES_EFFECT_ID,
    SELL_BODY_EVENT_SUBMISSION_EFFECT_ID,
)
from src.chat.features.chat_settings.ui.channel_settings_modal import ChatSettingsModal
from src.chat.utils.database import chat_db_manager
from src.chat.config import chat_config
from src.chat.features.affection.service.gift_service import GiftService
from src.chat.features.affection.service.affection_service import affection_service
from src.chat.services.gemini_service import gemini_service
from src.chat.features.odysseia_coin.service.shop_service import shop_service


if TYPE_CHECKING:
    from ..shop_ui import SimpleShopView, TutorialManagementView
    from discord.ext import commands

log = logging.getLogger(__name__)

# Use a TypeVar to specify the view type for better type hinting
ViewT = TypeVar("ViewT", bound=discord.ui.View)


# --- Base Components ---


class ShopButton(discord.ui.Button[ViewT]):
    """A base button class that provides correct type hinting for the view."""

    @property
    def view(self) -> ViewT:
        return cast(ViewT, super().view)


class ShopSelect(discord.ui.Select[ViewT]):
    """A base select class that provides correct type hinting for the view."""

    @property
    def view(self) -> ViewT:
        return cast(ViewT, super().view)


# --- Event UI Components ---


class EventButton(ShopButton["SimpleShopView"]):
    """Button to enter the active event view."""

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


# --- Daily Report UI Components ---


class DailyReportView(discord.ui.View):
    """View for displaying the daily report."""

    def __init__(self, main_view: "SimpleShopView"):
        super().__init__(timeout=180)
        self.main_view = main_view

        back_button = discord.ui.Button(
            label="返回商店", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )
        back_button.callback = self.back_callback
        self.add_item(back_button)

    async def create_embed(self) -> discord.Embed:
        """Creates the embed for the daily report."""
        if hasattr(self.main_view, "daily_panel"):
            return await self.main_view.daily_panel.create_embed()
        return discord.Embed(
            title="错误", description="无法加载日报面板。", color=discord.Color.red()
        )

    async def back_callback(self, interaction: discord.Interaction):
        """Returns to the main shop view."""
        embeds = await self.main_view.create_shop_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self.main_view)


class DailyReportButton(ShopButton["SimpleShopView"]):
    """Button to open the daily report view."""

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


# --- Loan UI Components ---


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
        await interaction.response.send_modal(modal)

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


# --- Main Shop Components ---


class CategorySelect(ShopSelect["SimpleShopView"]):
    """Select menu for choosing an item category."""

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
        selected_category = self.values[0]
        item_select = ItemSelect(
            selected_category, self.view.grouped_items[selected_category]
        )
        self.view.clear_items()
        self.view.add_item(item_select)
        self.view.add_item(BackToCategoriesButton())
        self.view.add_item(PurchaseButton())
        self.view.add_item(RefreshBalanceButton())
        await self.view._update_shop_embed(interaction, category=selected_category)


class ItemSelect(ShopSelect["SimpleShopView"]):
    """Select menu for choosing a specific item."""

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
    """Button to return to the category selection view."""

    def __init__(self):
        super().__init__(
            label="返回类别", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.clear_items()
        self.view.add_item(CategorySelect(list(self.view.grouped_items.keys())))
        self.view.add_item(PurchaseButton())
        self.view.add_item(RefreshBalanceButton())
        await self.view._update_shop_embed(interaction)


class LoanButton(ShopButton["SimpleShopView"]):
    """Button to open the loan view."""

    def __init__(self):
        super().__init__(label="借贷", style=discord.ButtonStyle.primary, emoji="🏦")

    async def callback(self, interaction: discord.Interaction):
        loan_view = LoanView(self.view.bot, self.view.author, self.view)
        await loan_view.initialize()
        embed = loan_view.create_loan_embed()
        await interaction.response.edit_message(embeds=[embed], view=loan_view)


class WorkButton(ShopButton["SimpleShopView"]):
    """Button to perform work and earn coins."""

    def __init__(self):
        super().__init__(label="打工", style=discord.ButtonStyle.success, emoji="🛠️")

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
    """Button for the 'sell body' feature."""

    def __init__(self):
        super().__init__(label="卖屁股", style=discord.ButtonStyle.danger, emoji="🥵")

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
    """Button to open the leaderboard view."""

    def __init__(self):
        super().__init__(label="排行榜", style=discord.ButtonStyle.primary, emoji="🏆")

    async def callback(self, interaction: discord.Interaction):
        leaderboard_view = LeaderboardView(self.view.bot, self.view.author, self.view)
        embed = await leaderboard_view.create_leaderboard_embed()
        await interaction.response.edit_message(embeds=[embed], view=leaderboard_view)


class PurchaseButton(ShopButton["SimpleShopView"]):
    """Button to purchase the selected item."""

    def __init__(self):
        super().__init__(label="购买", style=discord.ButtonStyle.success, emoji="💰")

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
            COMMUNITY_MEMBER_UPLOAD_EFFECT_ID,
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
            COMMUNITY_MEMBER_UPLOAD_EFFECT_ID: "src.chat.features.community_member.ui.community_member_modal.CommunityMemberUploadModal",
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
            should_generate_gift_response,
            embed_data,
        ) = await coin_service.purchase_item(
            interaction.user.id,
            interaction.guild.id if interaction.guild else 0,
            item["item_id"],
        )

        final_message = message
        if success and embed_data:
            embed = discord.Embed(
                title=embed_data["title"],
                description=embed_data["description"],
                color=discord.Color.blue(),
            )
            await interaction.followup.send(message, embed=embed, ephemeral=True)
        elif success and should_generate_gift_response:
            gift_service = GiftService(gemini_service, affection_service)
            try:
                ai_response = await gift_service.generate_gift_response(
                    interaction.user, item["name"]
                )
                final_message += f"\n\n{ai_response}"
            except Exception as e:
                log.error(f"为礼物 {item['name']} 生成AI回应时出错: {e}")
                final_message += (
                    "\n\n（AI 在想感谢语时遇到了点小麻烦，但你的心意已经收到了！）"
                )
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

    async def handle_thread_settings_modal(self, interaction: discord.Interaction):
        try:
            user_settings_query = "SELECT thread_cooldown_seconds, thread_cooldown_duration, thread_cooldown_limit FROM user_coins WHERE user_id = ?"
            user_settings_row = await chat_db_manager._execute(
                chat_db_manager._db_transaction,
                user_settings_query,
                (interaction.user.id,),
                fetch="one",
            )
            current_config = {}
            if user_settings_row:
                current_config = {
                    "cooldown_seconds": user_settings_row["thread_cooldown_seconds"],
                    "cooldown_duration": user_settings_row["thread_cooldown_duration"],
                    "cooldown_limit": user_settings_row["thread_cooldown_limit"],
                }

            async def modal_callback(
                modal_interaction: discord.Interaction, settings: Dict[str, Any]
            ):
                await chat_db_manager.update_user_thread_cooldown_settings(
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
    """Button to refresh the user's coin balance."""

    def __init__(self):
        super().__init__(
            label="刷新余额", style=discord.ButtonStyle.secondary, emoji="🔄"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_balance = await coin_service.get_balance(interaction.user.id)
        if new_balance is not None:
            self.view.balance = new_balance
        await self.view._update_shop_embed(interaction)
        await interaction.followup.send("余额已刷新。", ephemeral=True)


# --- Tutorial / Knowledge Base Components ---


class BackToShopButton(ShopButton["TutorialManagementView"]):
    """Button to return to the main shop view."""

    def __init__(self):
        super().__init__(
            label="返回商店", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )

    async def callback(self, interaction: discord.Interaction):
        # We need to re-create the main shop view
        from ..shop_ui import SimpleShopView

        main_view = SimpleShopView(self.view.bot, self.view.author, self.view.shop_data)
        main_view.interaction = interaction  # Crucial for keeping state

        embeds = await main_view.create_shop_embeds()
        await interaction.response.edit_message(embeds=embeds, view=main_view)


class TutorialModal(discord.ui.Modal, title="添加新的知识库教程"):
    # <--- 修改 2: __init__ 接收 view
    def __init__(self, view: "TutorialManagementView"):
        super().__init__(timeout=300)
        self.view = view  # Store the view
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
            # Refresh the view to show the new tutorial
            await self.view.initialize()
            embed = await self.view.create_embed()
            if self.view.interaction:
                # Use the original interaction to edit the message
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
        # We will implement the service layer next
        success = await shop_service.update_tutorial(
            tutorial_id=self.tutorial_id,
            title=self.title_input.value,
            description=self.description_input.value,
            author_id=interaction.user.id,
        )

        if success:
            await interaction.followup.send("✅ 你的教程已成功更新！", ephemeral=True)
            # Refresh the view
            await self.view.initialize(force_refresh=True)
            panel = self.view.panel
            if panel:
                panel.enter_listing_mode()  # Go back to the list view after edit
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


class AddTutorialButton(ShopButton["TutorialManagementView"]):
    """Button to add a new tutorial."""

    def __init__(self):
        super().__init__(
            label="添加新知识库", style=discord.ButtonStyle.success, emoji="➕"
        )

    async def callback(self, interaction: discord.Interaction):
        modal = TutorialModal(self.view)
        await interaction.response.send_modal(modal)


class KnowledgeBaseButton(ShopButton["SimpleShopView"]):
    """Button to open the tutorial management view."""

    def __init__(self):
        super().__init__(
            label="知识库管理", style=discord.ButtonStyle.primary, emoji="📚"
        )

    async def callback(self, interaction: discord.Interaction):
        from ..shop_ui import TutorialManagementView

        # This view will be created in the next step
        tutorial_view = TutorialManagementView(
            bot=self.view.bot, author=self.view.author, shop_data=self.view.shop_data
        )
        await tutorial_view.initialize()
        embed = await tutorial_view.create_embed()
        await interaction.response.edit_message(embeds=[embed], view=tutorial_view)


class ConfirmationModal(discord.ui.Modal, title="确认删除"):
    """A simple modal to confirm an action."""

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
    """Button to manage existing tutorials."""

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

        # Call the panel's method to switch to management mode
        panel.enter_management_mode()
        self.view.update_components()  # The view will now get components from the panel

        # Update the message with the new embed and components
        embed = await self.view.create_embed()
        await interaction.response.edit_message(embeds=[embed], view=self.view)


class TutorialActionSelect(ShopSelect["TutorialManagementView"]):
    """A select menu to choose a tutorial for an action (edit/delete)."""

    def __init__(self, tutorials: List[Dict[str, Any]]):
        options = [
            discord.SelectOption(
                label=tutorial["title"][:100],  # Max 100 chars for label
                value=str(tutorial["id"]),
                description=f"ID: {tutorial['id']}",
                emoji="📝",
            )
            for tutorial in tutorials
        ]
        options = options[:25]  # Max 25 options
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
        # The view's update_components will handle button states
        self.view.update_components()
        await interaction.response.edit_message(view=self.view)


class EditTutorialButton(ShopButton["TutorialManagementView"]):
    """Button to edit a selected tutorial."""

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

        # Fetch the full tutorial data
        tutorial_data = await shop_service.get_tutorial_by_id(
            panel.selected_tutorial_id
        )
        if not tutorial_data:
            await interaction.response.send_message(
                "❌ 无法找到所选教程的数据，它可能已被删除。", ephemeral=True
            )
            return

        # Open the modal with pre-filled data
        modal = EditTutorialModal(
            view=self.view,
            tutorial_id=panel.selected_tutorial_id,
            current_data=tutorial_data,
        )
        await interaction.response.send_modal(modal)


class DeleteTutorialButton(ShopButton["TutorialManagementView"]):
    """Button to delete a selected tutorial."""

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
                # Refresh the view
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
    """Button to go back to the main tutorial management panel."""

    def __init__(self):
        super().__init__(label="返回列表", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        panel = self.view.panel
        assert panel is not None
        panel.enter_listing_mode()
        self.view.update_components()
        embed = await self.view.create_embed()
        await interaction.response.edit_message(embeds=[embed], view=self.view)
