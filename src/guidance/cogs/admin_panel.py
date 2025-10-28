# -*- coding: utf-8 -*-

import discord
from discord import app_commands
from discord.ext import commands
import logging

# 从我们自己的模块中导入
from src.guidance.ui.views.main_panel import MainPanelView
from src import config

log = logging.getLogger(__name__)


def is_authorized(interaction: discord.Interaction) -> bool:
    """检查用户是否有权使用管理命令"""
    # 检查是否为开发者
    if interaction.user.id in config.DEVELOPER_USER_IDS:
        return True

    # 检查是否拥有管理员角色
    if isinstance(interaction.user, discord.Member):
        user_role_ids = {role.id for role in interaction.user.roles}
        if not user_role_ids.isdisjoint(config.ADMIN_ROLE_IDS):
            return True

    return False


class AdminPanel(commands.Cog):
    """
    包含所有与统一管理面板相关的命令。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="新人引导管理面板", description="打开集成的多功能新人引导管理面板。"
    )
    async def open_admin_panel(self, interaction: discord.Interaction):
        """
        显示主管理面板。
        """
        try:
            await interaction.response.defer(ephemeral=True)

            if not interaction.guild:
                await interaction.followup.send(
                    "此命令只能在服务器中使用。", ephemeral=True
                )
                return

            if not is_authorized(interaction):
                await interaction.followup.send(
                    "❌ 你没有权限使用此命令。", ephemeral=True
                )
                return

            view = MainPanelView(interaction)
            embed = await view.get_main_embed()
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except discord.errors.NotFound:
            log.warning(
                f"在 open_admin_panel 中处理交互失败 (NotFound)，可能由超时引起。交互已忽略。"
            )
        except Exception as e:
            log.error(f"打开管理面板时出现意外错误: {e}", exc_info=True)
            # 尝试向用户发送一条错误消息，如果失败也无妨
            try:
                await interaction.followup.send(
                    "❌ 打开管理面板时发生了一个内部错误。", ephemeral=True
                )
            except discord.errors.NotFound:
                pass


async def setup(bot: commands.Bot):
    """将这个 Cog 添加到机器人中"""
    await bot.add_cog(AdminPanel(bot))
