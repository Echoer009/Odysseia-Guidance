# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
from discord import app_commands
import logging

log = logging.getLogger(__name__)

# 这是Discord为21点游戏指定的官方应用ID
# 将来如果Discord更新或您想换成别的官方活动，可以修改这个ID
BLACKJACK_APPLICATION_ID = 945737671220174988


class BlackjackCog(commands.Cog):
    """处理21点游戏活动的Cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="blackjack", description="在语音频道中开始一个21点游戏活动"
    )
    async def blackjack(self, interaction: discord.Interaction):
        """
        当用户输入 /blackjack 命令时被调用
        """
        # 1. 检查用户是否在语音频道中
        if interaction.user.voice and interaction.user.voice.channel:
            voice_channel = interaction.user.voice.channel

            # 2. 创建活动邀请链接
            try:
                # target_application_id 指向我们想要启动的游戏
                invite = await voice_channel.create_invite(
                    target_type=discord.InviteTarget.embedded_application,
                    target_application_id=BLACKJACK_APPLICATION_ID,
                )

                # 3. 回复用户
                await interaction.response.send_message(
                    f"好的！点击下面的链接，在 **{voice_channel.name}** 频道开始21点游戏：\n{invite.url}",
                    ephemeral=True,  # ephemeral=True 表示这条消息只有发送者自己能看到
                )
            except Exception as e:
                log.error(f"创建21点活动邀请失败: {e}")
                await interaction.response.send_message(
                    "抱歉，创建游戏邀请时遇到了一个错误。", ephemeral=True
                )
        else:
            # 如果用户不在语音频道，则提示他们
            await interaction.response.send_message(
                "你需要先加入一个语音频道才能开始21点游戏哦！", ephemeral=True
            )


async def setup(bot: commands.Bot):
    """将这个Cog添加到机器人中"""
    await bot.add_cog(BlackjackCog(bot))
