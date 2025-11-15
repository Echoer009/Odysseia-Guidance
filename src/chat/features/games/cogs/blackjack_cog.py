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

    @app_commands.command(name="blackjack", description="来一场紧张刺激的Blackjack吧?")
    async def blackjack(self, interaction: discord.Interaction):
        """
        当用户输入 /blackjack 命令时被调用。
        直接使用应用的 Application ID 发送 LAUNCH_ACTIVITY (类型12) 响应，
        以实现无缝启动游戏，不依赖语音频道。
        """
        # 检查应用ID是否已在 .env 文件中正确配置
        if BLACKJACK_APPLICATION_ID == 0:
            log.error(
                "VITE_DISCORD_CLIENT_ID not found or is invalid in .env file. Blackjack command failed."
            )
            await interaction.response.send_message(
                "抱歉，游戏启动失败，因为缺少关键的应用ID配置。",
                ephemeral=True,
            )
            return

        try:
            # 根据最新的 discord.py 文档 (v2.6+)，
            # 使用官方提供的 launch_activity() 方法来直接启动活动。
            # 这是最正确、最稳定的方式。
            await interaction.response.launch_activity()
            log.info(
                f"Successfully launched Blackjack activity for user {interaction.user.id}"
            )

        except discord.InteractionResponded:
            log.warning(
                f"Attempted to launch activity for {interaction.user.id}, but interaction was already responded to."
            )
        except discord.errors.NotFound as e:
            log.error(f"Discord API未找到错误 (可能是网络或配置问题): {e}")
            # 使用followup而不是response，因为interaction可能已经过期
            try:
                await interaction.followup.send(
                    "启动游戏失败：无法连接到Discord服务。请检查网络连接或稍后再试。",
                    ephemeral=True,
                )
            except discord.errors.NotFound:
                log.error("无法发送错误消息，交互已过期")
        except discord.errors.HTTPException as e:
            log.error(f"Discord HTTP错误 (可能是网络问题): {e}")
            try:
                await interaction.followup.send(
                    "启动游戏失败：网络连接问题。请稍后再试。", ephemeral=True
                )
            except discord.errors.NotFound:
                log.error("无法发送错误消息，交互已过期")
        except Exception as e:
            log.error(
                f"使用 interaction.response.launch_activity() 启动21点时出错: {e}"
            )
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        "抱歉，启动游戏时遇到了一个未知错误。", ephemeral=True
                    )
                except discord.errors.NotFound:
                    log.error("无法发送错误消息，交互已过期")
            else:
                try:
                    await interaction.followup.send(
                        "抱歉，启动游戏时遇到了一个未知错误。", ephemeral=True
                    )
                except discord.errors.NotFound:
                    log.error("无法发送错误消息，交互已过期")


async def setup(bot: commands.Bot):
    """将这个Cog添加到机器人中"""
    await bot.add_cog(BlackjackCog(bot))
