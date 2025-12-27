import logging
import discord
from discord import app_commands
from discord.ext import commands

from src.chat.features.odysseia_coin.service.coin_service import coin_service
from src.chat.features.odysseia_coin.ui.shop_ui import SimpleShopView
from src.chat.config import chat_config
from src.chat.features.odysseia_coin.service.shop_service import shop_service

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
        command_prefix = self.bot.command_prefix
        # command_prefix can be a string, or a list/tuple of strings.
        # startswith requires a string or a tuple of strings.
        if isinstance(command_prefix, str):
            if message.content.startswith(command_prefix):
                return
        elif isinstance(command_prefix, (list, tuple)):
            if message.content.startswith(tuple(command_prefix)):
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
            channel_name = thread.parent.name if thread.parent else "未知频道"
            reason = f"在频道 {channel_name} 发布新帖"
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
        try:
            # 1. 准备数据
            shop_data = await shop_service.prepare_shop_data(interaction.user.id)

            is_thread_author = False
            if isinstance(interaction.channel, discord.Thread):
                if interaction.user.id == interaction.channel.owner_id:
                    is_thread_author = True
                    shop_data.thread_id = interaction.channel.id
            shop_data.show_tutorial_button = is_thread_author

            # 2. 创建视图
            view = SimpleShopView(self.bot, interaction.user, shop_data)

            # 3. 启动视图（视图现在自己处理交互响应）
            await view.start(interaction)

        except Exception as e:
            log.error(f"打开商店时出错: {e}", exc_info=True)
            error_message = "打开商店时发生错误，请稍后再试。"
            # 根据交互是否已被响应来决定是使用 followup 还是 send_message
            if interaction.response.is_done():
                await interaction.followup.send(error_message, ephemeral=True)
            else:
                # 在初始 defer 之前就发生错误的情况
                await interaction.response.send_message(error_message, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CoinCog(bot))
