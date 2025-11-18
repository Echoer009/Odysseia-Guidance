import logging
import discord
import os
from discord import app_commands
from discord.ext import commands

from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.odysseia_coin.ui.shop_ui import SimpleShopView
from src.chat.services.event_service import event_service
from src.chat.features.events.ui.event_panel_view import EventPanelView
from src.chat.config import chat_config

log = logging.getLogger(__name__)


class CoinCog(commands.Cog):
    """处理与类脑币相关的事件和命令"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """监听用户每日首次发言"""
        if message.author.bot:
            return

        # 排除特定命令前缀的消息，避免与命令冲突
        if hasattr(self.bot, "command_prefix") and message.content.startswith(
            self.bot.command_prefix
        ):
            return

        try:
            reward_granted = await coin_service.grant_daily_message_reward(
                message.author.id
            )
            if reward_granted:
                log.info(
                    f"用户 {message.author.name} ({message.author.id}) 获得了每日首次发言奖励。"
                )
        except Exception as e:
            log.error(
                f"处理用户 {message.author.id} 的每日发言奖励时出错: {e}", exc_info=True
            )

    async def handle_new_thread_reward(
        self, thread: discord.Thread, first_message: discord.Message
    ):
        """
        由中央事件处理器调用的公共方法，用于处理新帖子的发币奖励。
        """
        try:
            author = first_message.author
            if author.bot:
                return

            # 检查服务器是否在奖励列表中已由中央处理器完成，这里直接执行逻辑
            log.info(f"[CoinCog] 接收到新帖子进行奖励处理: {thread.name} ({thread.id})")
            reward_amount = chat_config.COIN_CONFIG["FORUM_POST_REWARD"]
            reason = f"在频道 {thread.parent.name} 发布新帖"
            new_balance = await coin_service.add_coins(author.id, reward_amount, reason)
            log.info(
                f"[CoinCog] 用户 {author.name} ({author.id}) 因发帖获得 {reward_amount} 类脑币。新余额: {new_balance}"
            )

        except Exception as e:
            log.error(
                f"[CoinCog] 处理帖子 {thread.id} 的发帖奖励时出错: {e}", exc_info=True
            )

    @app_commands.command(name="类脑商店", description="打开商店，购买商品。")
    async def shop(self, interaction: discord.Interaction):
        """斜杠命令：打开商店"""
        await interaction.response.defer(ephemeral=True)
        try:
            from src.chat.utils.database import chat_db_manager

            balance = await coin_service.get_balance(interaction.user.id)
            items_rows = await coin_service.get_all_items()
            items = [dict(item) for item in items_rows]

            # 检查用户是否已经拥有个人记忆功能
            user_profile = await chat_db_manager.get_user_profile(interaction.user.id)
            has_personal_memory = user_profile and user_profile["has_personal_memory"]

            # 如果用户已经拥有个人记忆功能，则修改商品列表中"个人记忆功能"的价格为10
            if has_personal_memory:
                for item in items:
                    if item["name"] == "个人记忆功能":
                        item["price"] = 10
                        break

            view = SimpleShopView(self.bot, interaction.user, balance, items)
            view.interaction = interaction  # 提前设置，以便 EventPanelView 能访问

            embeds_to_send = []

            # 0. 创建商店公告 Embed
            try:
                announcement_path = (
                    "src/chat/features/odysseia_coin/shop_announcement.md"
                )
                if (
                    os.path.exists(announcement_path)
                    and os.path.getsize(announcement_path) > 0
                ):
                    with open(announcement_path, "r", encoding="utf-8") as f:
                        announcement_content = f.read()
                    announcement_embed = discord.Embed(
                        description=announcement_content,
                        color=discord.Color.from_rgb(255, 182, 193),  # Light Pink
                    )
                    embeds_to_send.append(announcement_embed)
            except Exception as e:
                log.error(f"读取或创建商店公告时出错: {e}")

            # 1. 检查是否有活动，如果有，创建活动推广 Embed
            active_event = event_service.get_active_event()
            if active_event:
                # 创建 EventPanelView 实例以调用其 embed 创建方法
                event_panel_view = EventPanelView(
                    event_data=active_event, main_shop_view=view
                )
                # 现在 create_event_embed 是异步的，需要 await
                event_promo_embed = await event_panel_view.create_event_embed()
                embeds_to_send.append(event_promo_embed)

            # 2. 创建商店主 Embed
            shop_embed = view.create_shop_embed()
            embeds_to_send.append(shop_embed)

            # 3. 发送消息
            await interaction.followup.send(
                embeds=embeds_to_send, view=view, ephemeral=True
            )

        except Exception as e:
            log.error(f"打开商店时出错: {e}", exc_info=True)
            await interaction.followup.send(
                "打开商店时发生错误，请稍后再试。", ephemeral=True
            )

    # @app_commands.command(name="admin_add_coins", description="【管理员】为指定用户添加类脑币。")
    # @app_commands.default_permissions(administrator=True)
    # @app_commands.describe(
    #     user="选择一个用户",
    #     amount="要添加的金额"
    # )
    # async def admin_add_coins(
    #     self,
    #     interaction: discord.Interaction,
    #     user: discord.Member,
    #     amount: int
    # ):
    #     """管理员命令：为用户添加类脑币"""
    #     if amount <= 0:
    #         await interaction.response.send_message("❌ 金额必须是正数。", ephemeral=True)
    #         return

    #     await interaction.response.defer(ephemeral=True)
    #     try:
    #         reason = f"由管理员 {interaction.user.name} 添加"
    #         new_balance = await coin_service.add_coins(user.id, amount, reason)

    #         embed = discord.Embed(
    #             title="💰 类脑币添加成功",
    #             description=f"已成功为用户 {user.mention} 添加了 **{amount}** 类脑币。",
    #             color=discord.Color.green()
    #         )
    #         embed.add_field(name="操作人", value=interaction.user.mention, inline=True)
    #         embed.add_field(name="新余额", value=f"{new_balance}", inline=True)

    #         await interaction.followup.send(embed=embed, ephemeral=True)
    #         log.info(f"管理员 {interaction.user.name} 为用户 {user.name} 添加了 {amount} 类脑币。")

    #     except Exception as e:
    #         log.error(f"管理员 {interaction.user.name} 添加类脑币时出错: {e}", exc_info=True)
    #         await interaction.followup.send(f"❌ 操作失败，发生内部错误：{e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CoinCog(bot))
