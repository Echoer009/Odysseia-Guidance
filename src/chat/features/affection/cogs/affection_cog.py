import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, time, timezone, timedelta
import logging

from src.chat.features.affection.service.affection_service import affection_service
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)


class AffectionCog(commands.Cog):
    """处理与好感度相关的用户命令。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.affection_service = affection_service
        # 设置时区为 UTC+8
        self.beijing_tz = timezone(timedelta(hours=8))
        # 每天凌晨 00:05 执行
        self.daily_task.start()

    def cog_unload(self):
        self.daily_task.cancel()

    @tasks.loop(time=time(0, 5, tzinfo=timezone(timedelta(hours=8))))
    async def daily_task(self):
        """每日定时任务，用于处理好感度浮动和重置。"""
        log.info("开始执行每日好感度定时任务...")
        today_str = datetime.now(self.beijing_tz).date().isoformat()

        # 每日任务现在是全局的，不再需要遍历服务器
        try:
            await chat_db_manager.reset_daily_affection_gain(today_str)
            log.info("已重置所有用户的每日好感度上限。")
            await self.affection_service.apply_daily_fluctuation()
            log.info("已应用全局每日好感度浮动。")
        except Exception as e:
            log.error(f"执行全局每日好感度任务时出错: {e}", exc_info=True)

        log.info("每日好感度定时任务执行完毕。")

    @app_commands.command(name="好感度", description="查询你与类脑娘的好感度状态。")
    async def affection(self, interaction: discord.Interaction):
        """处理好感度查询命令。"""
        await interaction.response.defer(ephemeral=True)

        user = interaction.user
        guild = interaction.guild

        if not guild:
            await interaction.followup.send(
                "此命令只能在服务器中使用。", ephemeral=True
            )
            return

        try:
            status = await self.affection_service.get_affection_status(user.id)

            embed = discord.Embed(
                title=f"{user.display_name} 与类脑娘的好感度",
                color=discord.Color.pink(),
            )
            embed.set_thumbnail(url=user.display_avatar.url)

            embed.add_field(
                name="当前等级", value=f"**{status['level_name']}**", inline=False
            )
            embed.add_field(name="好感度点数", value=str(status["points"]), inline=True)
            embed.add_field(
                name="今日已获得",
                value=f"{status['daily_gain']} / {status['daily_cap']}",
                inline=True,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"查询好感度时出错: {e}", ephemeral=True)
            # 可以在这里添加更详细的日志记录
            print(f"Error in affection command: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AffectionCog(bot))
