import discord
from discord.ext import commands
from discord import app_commands

from src.chat.features.chat_settings.ui.chat_settings_view import ChatSettingsView
from src import config


async def is_authorized(interaction: discord.Interaction) -> bool:
    """检查用户是否是开发者或拥有管理员角色"""
    # 检查用户ID是否在开发者列表中
    if interaction.user.id in config.DEVELOPER_USER_IDS:
        return True

    # 检查用户的角色ID是否在管理员角色列表中
    if any(role.id in config.ADMIN_ROLE_IDS for role in interaction.user.roles):
        return True

    return False


class ChatSettingsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "你没有权限使用此命令。", ephemeral=True
            )
        else:
            # 对于其他错误，可以在这里添加日志记录或通用错误消息
            await interaction.response.send_message(
                "执行命令时发生错误。", ephemeral=True
            )
            print(f"Error in ChatSettingsCog: {error}")

    @app_commands.command(name="聊天设置", description="打开聊天功能设置面板")
    @app_commands.guild_only()
    @app_commands.check(is_authorized)
    async def chat_settings(self, interaction: discord.Interaction):
        """打开聊天功能设置面板"""
        await interaction.response.defer(ephemeral=True)
        view = await ChatSettingsView.create(interaction)

        # 创建一个显示模型使用情况的 Embed
        embed = discord.Embed(
            title="⚙️ 聊天功能设置",
            description="在此管理服务器的聊天设置，并查看AI模型使用情况统计。",
            color=config.EMBED_COLOR_PRIMARY,
        )
        embed.add_field(name="模型调用统计", value="---", inline=False)

        for model_name in config.AVAILABLE_AI_MODELS:
            count = view.model_usage_counts.get(model_name, 0)
            embed.add_field(name=model_name, value=f"调用次数: {count}", inline=True)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        message = await interaction.original_response()
        view.message = message


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatSettingsCog(bot))
