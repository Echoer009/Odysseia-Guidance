import discord
import logging
import asyncio
import uuid
from typing import List, Dict, Any

from discord.ext import commands

from src.chat.features.odysseia_coin.service.coin_service import (
    coin_service,
    PERSONAL_MEMORY_ITEM_EFFECT_ID,
    WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID,
    COMMUNITY_MEMBER_UPLOAD_EFFECT_ID,
    ENABLE_THREAD_REPLIES_EFFECT_ID,
)
from src.chat.features.chat_settings.ui.channel_settings_modal import ChatSettingsModal
from src.chat.utils.database import chat_db_manager
from src.chat.features.personal_memory.services.personal_memory_service import (
    personal_memory_service,
)
from src.chat.features.world_book.services.world_book_service import world_book_service
from src.chat.config import chat_config
from src.chat.features.affection.service.gift_service import GiftService
from src.chat.features.affection.service.affection_service import affection_service
from src.chat.services.gemini_service import gemini_service
from src.chat.services.event_service import event_service
from src.chat.features.events.ui.event_panel_view import EventPanelView

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


# --- Event UI ---


class EventButton(discord.ui.Button):
    """活动入口按钮"""

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

        # 创建新的活动视图
        event_view = EventPanelView(event_data=active_event, main_shop_view=self.view)
        # 异步创建活动 Embed
        embed = await event_view.create_event_embed()
        # 编辑消息，只显示活动 Embed 和活动 View
        await interaction.response.edit_message(embeds=[embed], view=event_view)


# --- Transfer UI ---


class TransferModal(discord.ui.Modal, title="类脑币转账"):
    def __init__(self, main_view: "SimpleShopView"):
        super().__init__(timeout=180)
        self.main_view = main_view

        self.receiver_input = discord.ui.TextInput(
            label="收款人 (用户英文id或数字id)",
            placeholder="输入对方的英文id或数字ID",
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(self.receiver_input)

        self.amount_input = discord.ui.TextInput(
            label="转账金额",
            placeholder="请输入你要转账的类脑币数量",
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # 1. 验证金额
        try:
            amount = int(self.amount_input.value)
            if amount <= 0:
                await interaction.followup.send(
                    "❌ 转账金额必须是正数。", ephemeral=True
                )
                return
        except ValueError:
            await interaction.followup.send("❌ 金额必须是有效的数字。", ephemeral=True)
            return

        # 2. 查找收款人
        receiver_str = self.receiver_input.value.strip()
        receiver: discord.Member = None

        if not interaction.guild:
            await interaction.followup.send(
                "❌ 无法在当前上下文中找到服务器信息。", ephemeral=True
            )
            return

        # 优先通过ID查找
        try:
            receiver_id = int(receiver_str)
            receiver = interaction.guild.get_member(receiver_id)
        except ValueError:
            # 如果不是ID，则通过名称查找
            receiver = discord.utils.find(
                lambda m: m.name.lower() == receiver_str.lower(),
                interaction.guild.members,
            )

        if receiver is None:
            await interaction.followup.send(
                f"❌ 在这个服务器中找不到用户 '{receiver_str}'。", ephemeral=True
            )
            return

        # 3. 调用服务执行转账
        success, message, new_balance = await coin_service.transfer_coins(
            sender_id=interaction.user.id, receiver_id=receiver.id, amount=amount
        )

        # 4. 发送反馈并更新视图
        await interaction.followup.send(message, ephemeral=True)

        if success:
            self.main_view.balance = new_balance
            await self.main_view.interaction.edit_original_response(
                embed=self.main_view.create_shop_embed(), view=self.main_view
            )


# --- Loan UI ---


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
        self, bot: commands.Bot, author: discord.Member, main_view: "SimpleShopView"
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.main_view = main_view
        self.active_loan = None

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

    def create_loan_embed(self):
        balance = self.main_view.balance
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
        await interaction.response.edit_message(
            embed=self.main_view.create_shop_embed(), view=self.main_view
        )

    async def refresh(self):
        await self.initialize()
        # Refresh balance in main view
        self.main_view.balance = await coin_service.get_balance(self.author.id)
        embed = self.create_loan_embed()
        await self.main_view.interaction.edit_original_response(embed=embed, view=self)


class SimpleShopView(discord.ui.View):
    """简化版的商店视图，直接显示所有商品"""

    def __init__(
        self,
        bot: commands.Bot,
        author: discord.Member,
        balance: int,
        items: List[Dict[str, Any]],
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.balance = balance
        self.items = items
        self.selected_item_id = None

        # 按类别分组商品
        self.grouped_items = {}
        for item in items:
            category = item["category"]
            if category not in self.grouped_items:
                self.grouped_items[category] = []
            self.grouped_items[category].append(item)

        # 添加类别选择下拉菜单
        self.add_item(CategorySelect(list(self.grouped_items.keys())))
        # 添加购买按钮和刷新余额按钮
        self.add_item(PurchaseButton())
        self.add_item(RefreshBalanceButton())
        self.add_item(TransferButton())
        self.add_item(LoanButton())
        # --- 动态添加入口 ---
        if event_service.get_active_event():
            self.add_item(EventButton())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if hasattr(self, "interaction"):
            try:
                await self.interaction.edit_original_response(view=self)
            except:
                pass  # 忽略可能的错误，比如消息已被删除

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "这不是你的商店界面哦！", ephemeral=True
            )
            return False
        return True

    def create_shop_embed(
        self, purchase_message: str = None, category: str = None
    ) -> discord.Embed:
        """创建商店的 Embed 消息"""
        description_text = "欢迎来到类脑商店！请选择你想要购买的商品。"
        if purchase_message:
            description_text = f"**{purchase_message}**\n\n" + description_text

        embed = discord.Embed(
            title="类脑商店", description=description_text, color=discord.Color.gold()
        )

        if category:
            # 显示特定类别的商品
            embed.add_field(
                name=f"📁 {category}", value="请从下拉菜单中选择商品", inline=False
            )
        else:
            # 显示类别列表
            if self.items:
                categories = sorted(list(set(item["category"] for item in self.items)))
                categories_str = "\n".join([f"✨ **{cat}**" for cat in categories])
                embed.add_field(name="商品类别", value=categories_str, inline=False)
            else:
                embed.add_field(name="", value="商店暂时没有商品哦。", inline=False)

        embed.set_footer(text=f"你的余额: {self.balance} 类脑币")
        return embed


class CategorySelect(discord.ui.Select):
    """类别选择下拉菜单"""

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
        # 创建商品选择下拉菜单
        item_select = ItemSelect(
            selected_category, self.view.grouped_items[selected_category]
        )

        # 更新视图，移除类别选择，添加商品选择
        self.view.clear_items()
        self.view.add_item(item_select)
        self.view.add_item(BackToCategoriesButton())
        self.view.add_item(PurchaseButton())
        self.view.add_item(RefreshBalanceButton())

        # 更新嵌入消息，显示选中的类别
        new_embed = self.view.create_shop_embed(category=selected_category)
        await interaction.response.edit_message(embed=new_embed, view=self.view)


class ItemSelect(discord.ui.Select):
    """商品选择下拉菜单"""

    def __init__(self, category: str, items: List[Dict[str, Any]]):
        options = []
        for item in items:
            options.append(
                discord.SelectOption(
                    label=item["name"],
                    value=str(item["item_id"]),
                    description=f"{item['price']} 类脑币 - {item['description']}",
                    emoji="🛒",
                )
            )

        # 确保选项数量不超过25个（Discord的限制）
        options = options[:25]

        super().__init__(
            placeholder=f"选择 {category} 中的商品...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        selected_value = self.values[0]
        self.view.selected_item_id = int(selected_value)
        await interaction.response.defer()  # 延迟响应，避免"此互动失败"


class BackToCategoriesButton(discord.ui.Button):
    """返回类别选择按钮"""

    def __init__(self):
        super().__init__(
            label="返回类别", style=discord.ButtonStyle.secondary, emoji="⬅️"
        )

    async def callback(self, interaction: discord.Interaction):
        # 重新创建类别选择视图
        self.view.clear_items()
        self.view.add_item(CategorySelect(list(self.view.grouped_items.keys())))
        self.view.add_item(PurchaseButton())
        self.view.add_item(RefreshBalanceButton())

        # 更新嵌入消息，回到类别列表
        new_embed = self.view.create_shop_embed()
        await interaction.response.edit_message(embed=new_embed, view=self.view)


class TransferButton(discord.ui.Button):
    """转账按钮"""

    def __init__(self):
        super().__init__(label="转账", style=discord.ButtonStyle.primary, emoji="💸")

    async def callback(self, interaction: discord.Interaction):
        modal = TransferModal(main_view=self.view)
        await interaction.response.send_modal(modal)


class LoanButton(discord.ui.Button):
    """借贷按钮"""

    def __init__(self):
        super().__init__(label="借贷", style=discord.ButtonStyle.primary, emoji="🏦")

    async def callback(self, interaction: discord.Interaction):
        loan_view = LoanView(self.view.bot, self.view.author, self.view)
        await loan_view.initialize()
        embed = loan_view.create_loan_embed()
        await interaction.response.edit_message(embed=embed, view=loan_view)


class PurchaseButton(discord.ui.Button):
    """购买按钮"""

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

        # --- 新的个人记忆商品购买流程 ---
        if item_effect == PERSONAL_MEMORY_ITEM_EFFECT_ID:
            await self.handle_personal_memory_purchase(interaction, selected_item)
            return

        # --- 其他模态框购买流程 (保持原样) ---
        modal_effects = [
            WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID,
            COMMUNITY_MEMBER_UPLOAD_EFFECT_ID,
        ]
        if item_effect in modal_effects:
            await self.handle_standard_modal_purchase(interaction, selected_item)
            return

        # --- 普通商品购买流程 ---
        await self.handle_standard_purchase(interaction, selected_item)

    async def handle_personal_memory_purchase(
        self, interaction: discord.Interaction, item: Dict[str, Any]
    ):
        """处理个人记忆商品的购买，采用先开模态框后扣款的逻辑"""
        # 1. 检查余额
        current_balance = await coin_service.get_balance(interaction.user.id)
        if current_balance < item["price"]:
            await interaction.response.send_message(
                f"你的余额不足！需要 {item['price']} 类脑币，但你只有 {current_balance}。",
                ephemeral=True,
            )
            return

        # 2. 创建一个带唯一ID的模态框
        from src.chat.features.personal_memory.ui.profile_modal import ProfileEditModal

        unique_id = f"personal_profile_edit_modal_{uuid.uuid4()}"
        modal = ProfileEditModal(custom_id=unique_id)
        await interaction.response.send_modal(modal)

        try:
            # 3. 等待模态框提交
            modal_interaction: discord.Interaction = await self.view.bot.wait_for(
                "interaction",
                check=lambda i: i.type == discord.InteractionType.modal_submit
                and i.data.get("custom_id") == unique_id,
                timeout=300.0,  # 5分钟超时
            )

            # 4. 用户提交后，先扣款
            await modal_interaction.response.defer(ephemeral=True)

            success, message, new_balance, _, _ = await coin_service.purchase_item(
                interaction.user.id,
                interaction.guild.id if interaction.guild else 0,
                item["item_id"],
            )

            if not success:
                await modal_interaction.followup.send(
                    f"购买失败：{message}", ephemeral=True
                )
                return

            # 5. 扣款成功后，保存个人档案
            components = modal_interaction.data.get("components", [])
            values_by_id = {
                comp["components"][0]["custom_id"]: comp["components"][0]["value"]
                for comp in components
                if comp.get("components") and comp["components"]
            }
            profile_data = {
                "name": values_by_id.get("name", "").strip(),
                "personality": values_by_id.get("personality", "").strip(),
                "background": values_by_id.get("background", "").strip(),
                "preferences": values_by_id.get("preferences", "").strip(),
                "discord_id": str(interaction.user.id),
                "uploaded_by": interaction.user.id,
                "uploaded_by_name": interaction.user.display_name,
                "update_target_id": str(
                    interaction.user.id
                ),  # 商店购买总是首次创建或覆盖
            }

            if not profile_data["name"] or not profile_data["personality"]:
                await modal_interaction.followup.send(
                    "名称和性格特点不能为空，购买失败，已自动退款。", ephemeral=True
                )
                # --- 新增退款逻辑 ---
                await coin_service.add_balance(
                    user_id=interaction.user.id,
                    amount=item["price"],
                    reason=f"个人档案提交信息不完整自动退款 (item_id: {item['item_id']})",
                )
                log.info(
                    f"已为用户 {interaction.user.id} 退款 {item['price']} 类脑币，原因：提交信息不完整。"
                )
                return

            # --- 构造支付信息 ---
            purchase_info = {"item_id": item["item_id"], "price": item["price"]}

            # 使用新的通用审核流程
            review_settings = chat_config.WORLD_BOOK_CONFIG[
                "personal_profile_review_settings"
            ]

            embed_title = "哇!我收到了一张新名片！"
            embed_description = f"**{interaction.user.display_name}** 递给了我一张TA的名片，大伙怎么看？"

            embed_fields = [
                {"name": "名称", "value": profile_data["name"], "inline": True},
                {
                    "name": "性格特点",
                    "value": profile_data["personality"][:300]
                    + ("..." if len(profile_data["personality"]) > 300 else ""),
                    "inline": False,
                },
            ]
            if profile_data["background"]:
                embed_fields.append(
                    {
                        "name": "背景信息",
                        "value": profile_data["background"][:200]
                        + ("..." if len(profile_data["background"]) > 200 else ""),
                        "inline": False,
                    }
                )
            if profile_data["preferences"]:
                embed_fields.append(
                    {
                        "name": "喜好偏好",
                        "value": profile_data["preferences"][:200]
                        + ("..." if len(profile_data["preferences"]) > 200 else ""),
                        "inline": False,
                    }
                )

            # 注意：这里我们使用 modal_interaction 来发送后续消息，但审核流程需要原始的 interaction 来定位频道
            await world_book_service.initiate_review_process(
                interaction=interaction,  # 使用原始的 interaction
                entry_type="personal_profile",
                entry_data=profile_data,
                review_settings=review_settings,
                embed_title=embed_title,
                embed_description=embed_description,
                embed_fields=embed_fields,
                is_update=False,  # 从商店购买视为首次提交
                purchase_info=purchase_info,  # --- 传递支付信息 ---
                followup_interaction=modal_interaction,  # 传递 modal_interaction 用于发送反馈
            )

            # 6. 更新商店界面
            self.view.balance = new_balance
            new_embed = self.view.create_shop_embed()
            await interaction.edit_original_response(embed=new_embed, view=self.view)

        except asyncio.TimeoutError:
            # 7. 用户未提交，超时处理
            await interaction.followup.send(
                "由于你长时间未操作，购买已自动取消。", ephemeral=True
            )
        except Exception as e:
            log.error(f"处理个人记忆商品购买时出错: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "处理你的购买请求时发生了一个意想不到的错误。", ephemeral=True
                )

    async def handle_standard_modal_purchase(
        self, interaction: discord.Interaction, item: Dict[str, Any]
    ):
        """处理需要弹出模态框的商品的购买，采用先开模态框后扣款的逻辑"""
        # 1. 快速检查余额
        current_balance = await coin_service.get_balance(interaction.user.id)
        if current_balance < item["price"]:
            await interaction.response.send_message(
                f"你的余额不足！需要 {item['price']} 类脑币，但你只有 {current_balance}。",
                ephemeral=True,
            )
            return

        # 2. 立即弹出模态框，并将购买信息传递过去
        modal_map = {
            WORLD_BOOK_CONTRIBUTION_ITEM_EFFECT_ID: "src.chat.features.world_book.ui.contribution_modal.WorldBookContributionModal",
            COMMUNITY_MEMBER_UPLOAD_EFFECT_ID: "src.chat.features.community_member.ui.community_member_modal.CommunityMemberUploadModal",
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
            # 交互已经响应，后续的扣款和消息更新将在模态框的 on_submit 中处理
        except (ImportError, AttributeError) as e:
            log.error(f"动态加载模态框失败: {e}", exc_info=True)
            await interaction.response.send_message(
                "打开功能界面时出错，请联系管理员。", ephemeral=True
            )
        except Exception as e:
            log.error(f"处理标准模态框购买时发生未知错误: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "处理请求时发生未知错误。", ephemeral=True
                )

    async def handle_standard_purchase(
        self, interaction: discord.Interaction, item: Dict[str, Any]
    ):
        """处理普通商品的购买"""
        await interaction.response.defer(ephemeral=True)
        try:
            (
                success,
                message,
                new_balance,
                should_show_modal,
                should_generate_gift_response,
            ) = await coin_service.purchase_item(
                interaction.user.id,
                interaction.guild.id if interaction.guild else 0,
                item["item_id"],
            )

            final_message = message
            if success and should_generate_gift_response:
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

            try:
                await interaction.followup.send(final_message, ephemeral=True)
            except discord.errors.NotFound:
                log.warning(
                    f"Followup failed for user {interaction.user.id}, sending DM as fallback."
                )
                try:
                    await interaction.user.send(f"你的购买已完成！\n\n{final_message}")
                except discord.errors.Forbidden:
                    log.error(
                        f"Failed to send DM to user {interaction.user.id} as a fallback."
                    )

            if success:
                self.view.balance = new_balance
                new_embed = self.view.create_shop_embed()
                await interaction.edit_original_response(
                    embed=new_embed, view=self.view
                )

                if (
                    should_show_modal
                    and item.get("effect_id") == ENABLE_THREAD_REPLIES_EFFECT_ID
                ):
                    await self.handle_thread_settings_modal(interaction)

        except Exception as e:
            log.error(f"处理购买商品 {item['item_id']} 时出错: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "处理你的购买请求时发生了一个意想不到的错误。", ephemeral=True
                )

    async def handle_thread_settings_modal(self, interaction: discord.Interaction):
        """处理购买“通行许可”后弹出的帖子冷却设置模态框"""
        try:
            # 1. 获取用户当前的设置作为默认值
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

            # 2. 定义模态框提交后的回调函数
            async def modal_callback(
                modal_interaction: discord.Interaction, settings: Dict[str, Any]
            ):
                await chat_db_manager.update_user_thread_cooldown_settings(
                    interaction.user.id, settings
                )
                await modal_interaction.response.send_message(
                    "✅ 你的个人帖子冷却设置已保存！", ephemeral=True
                )

            # 3. 创建并发送模态框
            modal = ChatSettingsModal(
                title="设置你的帖子默认冷却",
                current_config=current_config,
                on_submit_callback=modal_callback,
                include_enable_option=False,  # 不需要“启用/禁用”选项
            )

            # 使用 followup 发送一个新的交互响应，因为原始交互已经响应过了
            # 注意：Discord UI 的限制，我们不能在一个已经响应的交互上再发送一个模态框
            # 因此，这里我们直接在 followup 消息中发送模态框，但这通常不被支持。
            # 一个更好的方法是发送一条新消息，带有一个按钮，点击按钮弹出模态框。
            # 但为了简化流程，我们先尝试直接发送。如果不行，就需要调整。
            # 经过测试，直接在 followup 中发送模态框是不可行的。
            # 正确的做法是，让购买按钮的回调函数不 defer，而是直接 response.send_modal()
            # 但这会改变整个购买流程的结构。
            #
            # 折中方案：发送一条带按钮的新消息。

            view = discord.ui.View(timeout=180)
            button = discord.ui.Button(
                label="点此设置帖子冷却", style=discord.ButtonStyle.primary
            )

            async def button_callback(button_interaction: discord.Interaction):
                await button_interaction.response.send_modal(modal)
                button.disabled = True
                await button_interaction.edit_original_response(view=view)

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


class RefreshBalanceButton(discord.ui.Button):
    """刷新余额按钮"""

    def __init__(self):
        super().__init__(
            label="刷新余额", style=discord.ButtonStyle.secondary, emoji="🔄"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        # 重新获取用户余额
        new_balance = await coin_service.get_balance(interaction.user.id)
        self.view.balance = new_balance

        # 创建一个新的 embed 来更新余额显示
        # 注意：我们不会改变视图（view），只更新嵌入消息（embed）
        # 我们需要确定当前所在的 embed 是哪个
        current_embed = interaction.message.embeds[0]
        current_embed.set_footer(text=f"你的余额: {self.view.balance} 类脑币")

        # 编辑原始消息，只更新 embed
        await interaction.edit_original_response(embed=current_embed, view=self.view)
