# -*- coding: utf-8 -*-

import discord
from discord.ui import View, Button, button

# 导入各个子视图
from src.guidance.ui.views.tag_management import TagManagementView
from src.guidance.ui.views.path_configuration import PathConfigurationView
from src.guidance.ui.views.role_configuration import RoleConfigurationView
from src.guidance.ui.views.message_templates import MessageTemplatesView
from src.guidance.ui.views.channel_message_config import ChannelMessageConfigView
from src.guidance.ui.views.deployment import DeploymentView

from src import config as root_config  # 导入配置文件以使用颜色
from src.guidance.utils.database import guidance_db_manager as db_manager


class MainPanelView(View):
    """
    主管理面板视图，作为所有管理功能的导航中心。
    """

    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.interaction = interaction
        self.guild = interaction.guild

    async def on_timeout(self):
        # 视图超时后禁用所有按钮
        for item in self.children:
            item.disabled = True
        try:
            await self.interaction.edit_original_response(view=self)
        except discord.NotFound:
            pass  # 如果消息被删除则忽略

    async def get_main_embed(self) -> discord.Embed:
        """生成主面板的 Embed"""
        embed = discord.Embed(
            title=f"⚙️ {self.guild.name} 新人引导管理面板",
            description="欢迎使用统一管理面板。请通过下方的按钮选择您要配置的项目。",
            color=root_config.EMBED_COLOR_INFO,
        )
        # 异步获取配置状态
        deployed_panel = await db_manager.get_deployed_panel(self.guild.id)

        # 根据配置状态添加字段
        embed.add_field(
            name="🏷️ 标签管理", value="创建、编辑和删除用于分类的兴趣标签。", inline=True
        )
        embed.add_field(
            name="🗺️ 路径设置", value="为每个标签关联具体的引导频道或帖子。", inline=True
        )
        embed.add_field(
            name="🛂 身份组配置", value="设置哪些身份组会触发新成员引导。", inline=True
        )
        embed.add_field(
            name="✉️ 消息模板", value="自定义引导流程中发送给用户的消息。", inline=True
        )
        embed.add_field(
            name="📝 频道消息设置",
            value="为引导路径中的特定频道配置专属的临时消息。",
            inline=True,
        )

        deployment_status = (
            "✅ 已部署"
            if deployed_panel and deployed_panel["channel_id"]
            else "❌ 未部署"
        )
        embed.add_field(
            name="🚀 部署与重置",
            value=f"部署引导面板到指定频道。\n状态: **{deployment_status}**",
            inline=True,
        )
        embed.set_footer(text="Odysseia Guidance System")
        return embed

    # --- 按钮回调 ---

    @button(label="标签管理", style=discord.ButtonStyle.secondary, emoji="🏷️", row=0)
    async def manage_tags(self, interaction: discord.Interaction, button: Button):
        # 切换到标签管理视图
        await interaction.response.defer()  # 延迟响应，防止超时
        view = TagManagementView(self.interaction)
        await view.async_init()
        embed = view.get_embed()
        await interaction.edit_original_response(embed=embed, view=view)

    @button(label="路径设置", style=discord.ButtonStyle.secondary, emoji="🗺️", row=0)
    async def configure_paths(self, interaction: discord.Interaction, button: Button):
        # 切换到路径设置视图
        await interaction.response.defer()
        view = PathConfigurationView(self.interaction)
        await view.async_init()
        embed = view.get_embed()
        await interaction.edit_original_response(embed=embed, view=view)

    @button(label="身份组配置", style=discord.ButtonStyle.secondary, emoji="🛂", row=1)
    async def configure_roles(self, interaction: discord.Interaction, button: Button):
        """打开身份组配置视图"""
        await interaction.response.defer()
        view = RoleConfigurationView(self.interaction)
        await view.async_init()
        embed = view.get_embed()
        await interaction.edit_original_response(embed=embed, view=view)

    @button(label="消息模板", style=discord.ButtonStyle.secondary, emoji="✉️", row=1)
    async def configure_templates(
        self, interaction: discord.Interaction, button: Button
    ):
        """打开消息模板配置视图"""
        await interaction.response.defer()
        view = MessageTemplatesView(self.interaction)
        await view.async_init()
        embed = view.get_embed()
        await interaction.edit_original_response(embed=embed, view=view)

    @button(
        label="频道消息设置", style=discord.ButtonStyle.secondary, emoji="📝", row=2
    )
    async def configure_channel_messages(
        self, interaction: discord.Interaction, button: Button
    ):
        """打开频道专属消息配置视图"""
        await interaction.response.defer()
        view = ChannelMessageConfigView(self.interaction)
        await view.async_init()
        embed = await view.get_config_list_embed()
        await interaction.edit_original_response(embed=embed, view=view)

    @button(label="部署与重置", style=discord.ButtonStyle.success, emoji="🚀", row=2)
    async def deploy(self, interaction: discord.Interaction, button: Button):
        """打开部署视图"""
        await interaction.response.defer()

        # 创建部署视图，它会自己进行检查
        deployment_view = DeploymentView(self.interaction)
        await deployment_view.async_init()

        # 从部署视图获取检查结果来生成 Embed
        embed = await deployment_view.get_embed()

        await interaction.edit_original_response(embed=embed, view=deployment_view)
