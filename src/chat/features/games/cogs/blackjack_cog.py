# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

log = logging.getLogger(__name__)

# 从环境变量中获取您自己的应用ID
# 这个ID应该与您的 blackjack-web 前端应用所使用的 VITE_DISCORD_CLIENT_ID 匹配
BLACKJACK_APPLICATION_ID_STR = os.getenv("VITE_DISCORD_CLIENT_ID")
if not BLACKJACK_APPLICATION_ID_STR:
    # 如果环境变量不存在，记录一个错误并设置一个无效的默认值
    log.error(
        "VITE_DISCORD_CLIENT_ID not found in .env file. Blackjack command will fail."
    )
    BLACKJACK_APPLICATION_ID = 0
else:
    BLACKJACK_APPLICATION_ID = int(BLACKJACK_APPLICATION_ID_STR)


class BlackjackCog(commands.Cog):
    """处理21点游戏活动的Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="blackjack", description="获取一个21点游戏的开始链接")
    async def blackjack(self, interaction: discord.Interaction):
        """
        当用户输入 /blackjack 命令时被调用。
        机器人会自动寻找一个可用的语音频道来创建活动。
        """
        # 检查我们是否成功获取了应用ID
        if BLACKJACK_APPLICATION_ID == 0:
            await interaction.response.send_message(
                "抱歉，21点游戏的应用ID未正确配置，请联系管理员。", ephemeral=True
            )
            return

        # 检查命令是否在服务器（guild）中使用
        if not interaction.guild:
            await interaction.response.send_message(
                "这个命令只能在服务器中使用。", ephemeral=True
            )
            return

        # 活动将在当前频道创建
        target_channel = interaction.channel

        try:
            # 为找到的频道创建活动邀请
            invite = await target_channel.create_invite(
                target_type=discord.InviteTarget.embedded_application,
                target_application_id=BLACKJACK_APPLICATION_ID,
                max_age=600,  # 邀请10分钟后失效
            )

            view = discord.ui.View()
            button = discord.ui.Button(
                label="点击开始21点",
                style=discord.ButtonStyle.link,
                url=invite.url,
            )
            view.add_item(button)

            await interaction.response.send_message(
                f"游戏已在 **{target_channel.name}** 频道准备就绪，点击按钮加入：",
                view=view,
                ephemeral=True,
            )

        except Exception as e:
            log.error(f"为频道 {target_channel.name} 创建21点活动时出错: {e}")
            await interaction.response.send_message(
                "抱歉，创建游戏时遇到了一个未知错误。", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """将这个Cog添加到机器人中"""
    await bot.add_cog(BlackjackCog(bot))
