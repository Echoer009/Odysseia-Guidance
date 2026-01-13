# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
from discord import app_commands
import logging

from src import config
from src.chat.features.admin_panel.ui.views.db_management_view import DBManagementView

log = logging.getLogger(__name__)


# --- 权限检查 ---
def is_admin_or_dev():
    """检查用户是否是管理员或开发者"""

    async def predicate(interaction: discord.Interaction) -> bool:
        if not config.ADMIN_ROLE_IDS and not config.DEVELOPER_USER_IDS:
            log.warning("ADMIN_ROLE_IDS 和 DEVELOPER_USER_IDS 未在 .env 文件中配置。")
            return False

        user = interaction.user
        if not isinstance(user, discord.Member):
            # If the user is not a member (e.g., in a DM), they cannot have admin roles.
            return user.id in config.DEVELOPER_USER_IDS

        user_roles = {role.id for role in user.roles}
        user_id = interaction.user.id

        # 检查用户是否是开发者
        is_dev = user_id in config.DEVELOPER_USER_IDS
        # 检查用户是否拥有管理员角色
        is_admin = not user_roles.isdisjoint(config.ADMIN_ROLE_IDS)

        result = is_admin or is_dev
        if not result:
            log.warning(
                f"用户 {interaction.user} (ID: {user_id}) 尝试执行管理员命令失败（权限不足）。"
            )
        return result

    return app_commands.check(predicate)


class AdminPanelCog(commands.Cog):
    """包含仅限管理员和开发者使用的命令"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="数据库管理面板", description="以交互方式浏览和管理数据库内容"
    )
    @is_admin_or_dev()
    async def db_view(self, interaction: discord.Interaction):
        """启动数据库浏览器"""
        log.info(
            f"管理员 {interaction.user.display_name} (ID: {interaction.user.id}) 启动了数据库浏览器。"
        )
        try:
            await interaction.response.defer(ephemeral=True)
            view = DBManagementView(interaction.user.id)
            # 先发送一个临时的加载消息
            message = await interaction.followup.send(
                "正在加载数据库浏览器...", ephemeral=True
            )
            view.message = message
            # 手动触发第一次视图更新，显示完整的UI
            await view.update_view()
        except Exception as e:
            log.error(f"启动数据库浏览器时发生未知错误: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"启动数据库浏览器时发生未知错误: {e}", ephemeral=True
                )

    @db_view.error
    async def on_db_view_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """db_view 命令的错误处理程序"""
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "抱歉，您没有权限使用此命令。", ephemeral=True
            )
        else:
            log.error(f"执行 db_view 命令时发生未处理的错误: {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"执行命令时发生未知错误: {error}", ephemeral=True
                )


async def setup(bot: commands.Bot):
    """将这个Cog添加到机器人中"""
    await bot.add_cog(AdminPanelCog(bot))
