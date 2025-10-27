# -*- coding: utf-8 -*-

import discord
from discord.ui import View, Button, button

from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.ui.modals.channel_message_modal import ChannelMessageModal
from src.guidance.ui.modals.extra_config_modal import ExtraConfigModal
from src.guidance.ui.views.temporary_message_editor import TemporaryMessagesEditView
from src import config as root_config


class ChannelMessageConfigView(View):
    """
    管理频道专属消息配置的视图。
    """

    def __init__(self, main_interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.main_interaction = main_interaction
        self.guild = main_interaction.guild
        self.selected_channel_id: int = None
        self.selected_location_is_thread: bool = False
        self.current_page = 1
        self.items_per_page = 8  # 每页显示8个项目，防止超长
        self.all_configs = []

    async def async_init(self):
        """异步初始化视图，加载数据并设置组件。"""
        # 异步获取数据并创建选择菜单
        self.all_configs = await db_manager.get_all_channel_messages(self.guild.id)
        location_select = await self.LocationSelect.create(self.guild)
        self.add_item(location_select)
        # 更新按钮状态
        await self.update_view_components()

    async def update_view_components(self):
        """根据选择和分页状态更新所有按钮。"""
        # 查找配置、删除按钮并根据是否选择了频道来更新它们的状态
        perm_btn = next(
            (
                item
                for item in self.children
                if item.custom_id == "permanent_config_button"
            ),
            None,
        )
        temp_btn = next(
            (
                item
                for item in self.children
                if item.custom_id == "temporary_config_button"
            ),
            None,
        )
        remove_btn = next(
            (item for item in self.children if item.custom_id == "remove_button"), None
        )
        extra_btn = next(
            (item for item in self.children if item.custom_id == "extra_config_button"),
            None,
        )

        is_channel_selected = self.selected_channel_id is not None

        if perm_btn:
            perm_btn.disabled = not is_channel_selected
        if temp_btn:
            temp_btn.disabled = not is_channel_selected
        if extra_btn:
            extra_btn.disabled = not is_channel_selected

        if remove_btn:
            config_exists = False
            if is_channel_selected:
                config = await db_manager.get_channel_message(self.selected_channel_id)
                if config:
                    config_exists = True
            remove_btn.disabled = not config_exists

        # 更新分页按钮
        prev_btn = next(
            (item for item in self.children if item.custom_id == "prev_page"), None
        )
        next_btn = next(
            (item for item in self.children if item.custom_id == "next_page"), None
        )

        total_pages = (len(self.all_configs) - 1) // self.items_per_page + 1
        if total_pages <= 0:
            total_pages = 1

        if prev_btn:
            prev_btn.disabled = self.current_page <= 1
        if next_btn:
            next_btn.disabled = self.current_page >= total_pages

    async def get_config_list_embed(self) -> discord.Embed:
        """生成配置列表的 Embed。"""
        embed = discord.Embed(
            title="📝 地点专属消息设置",
            description="在这里为服务器的特定频道或帖子设置独一无二的永久和临时引导消息。\n"
            "1. **从下方选择一个已在引导路径中配置过的地点**。\n"
            "2. 点击 **“配置此地点消息”** 来添加或编辑该地点的消息。\n"
            "3. 点击 **“删除此地点配置”** 来移除该地点的设置。",
            color=root_config.EMBED_COLOR_INFO,
        )

        total_pages = (len(self.all_configs) - 1) // self.items_per_page + 1
        if total_pages <= 0:
            total_pages = 1
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        paginated_configs = self.all_configs[start_index:end_index]

        if not self.all_configs:
            embed.add_field(
                name="当前没有配置",
                value="还没有任何地点配置，请先在“路径设置”中添加频道或帖子。",
                inline=False,
            )
        else:
            field_value = ""
            for config_item in paginated_configs:
                channel = self.guild.get_channel_or_thread(config_item["channel_id"])
                channel_name = (
                    channel.name
                    if channel
                    else f"未知地点 (ID: {config_item['channel_id']})"
                )

                status = []
                permanent_data = config_item.get("permanent_message_data") or {}
                temporary_data = config_item.get("temporary_message_data") or []

                if permanent_data and (
                    permanent_data.get("content") or permanent_data.get("embed_data")
                ):
                    status.append("永久消息")
                if temporary_data:
                    status.append(f"临时消息 ({len(temporary_data)})")
                if permanent_data.get("image_url"):
                    status.append("🖼️")
                if permanent_data.get("thumbnail_url"):
                    status.append("🖋️")
                if permanent_data.get("footer"):
                    status.append("📄")

                status_str = " | ".join(status) if status else "无内容"
                field_value += f"• **#{channel_name}** - `{status_str}`\n"

            embed.add_field(
                name=f"已配置的地点 (第 {self.current_page}/{total_pages} 页)",
                value=field_value if field_value else "这一页没有内容。",
                inline=False,
            )

        embed.set_footer(text="选择一个地点后，下方的编辑和删除按钮将启用。")
        return embed

    # --- 组件定义 ---

    class LocationSelect(discord.ui.Select):
        def __init__(self, options: list[discord.SelectOption]):
            super().__init__(
                placeholder="从引导路径中选择一个频道或帖子...",
                min_values=1,
                max_values=1,
                options=options[:25]
                if options
                else [
                    discord.SelectOption(
                        label="没有在路径中配置过的频道/帖子",
                        value="no_locations",
                        emoji="⚠️",
                    )
                ],
                row=0,
                disabled=not options,
            )

        @classmethod
        async def create(cls, guild: discord.Guild):
            """异步创建并返回一个 LocationSelect 实例。"""
            locations = await db_manager.get_configured_path_locations(guild.id)
            options = []
            if locations:
                for loc in locations:
                    channel = guild.get_channel_or_thread(loc["location_id"])
                    if channel:
                        is_thread = isinstance(channel, discord.Thread)
                        prefix = "[帖子]" if is_thread else "[频道]"
                        options.append(
                            discord.SelectOption(
                                label=f"{prefix} {channel.name}",
                                value=str(channel.id),
                                description=f"ID: {channel.id}",
                            )
                        )
            return cls(options)

        async def callback(self, interaction: discord.Interaction):
            if self.values[0] == "no_locations":
                await interaction.response.send_message(
                    "❌ 没有任何频道或帖子在引导路径中被配置。", ephemeral=True
                )
                return

            await interaction.response.defer()
            self.view.selected_channel_id = int(self.values[0])

            # 获取所选对象的类型
            channel = self.view.guild.get_channel_or_thread(
                self.view.selected_channel_id
            )
            if channel:
                self.view.selected_location_is_thread = isinstance(
                    channel, discord.Thread
                )
            else:
                self.view.selected_location_is_thread = False  # Fallback

            await self.view.update_view_components()
            await self.view.main_interaction.edit_original_response(view=self.view)

    # --- 按钮 ---

    @button(
        label="编辑永久消息",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        row=1,
        disabled=True,
        custom_id="permanent_config_button",
    )
    async def permanent_config_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """打开模态框为所选地点编辑永久消息。"""
        if not self.selected_channel_id:
            await interaction.response.send_message(
                "请先从下拉菜单中选择一个地点。", ephemeral=True
            )
            return

        existing_config = await db_manager.get_channel_message(self.selected_channel_id)

        modal = ChannelMessageModal(
            interaction=interaction,
            channel_id=self.selected_channel_id,
            existing_config=existing_config,
            is_thread=self.selected_location_is_thread,
        )
        await interaction.response.send_modal(modal)
        await modal.wait()

        await self.update_view_components()
        new_embed = await self.get_config_list_embed()
        await self.main_interaction.edit_original_response(embed=new_embed, view=self)

    @button(
        label="编辑临时消息",
        style=discord.ButtonStyle.success,
        emoji="💬",
        row=1,
        disabled=True,
        custom_id="temporary_config_button",
    )
    async def temporary_config_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """打开新的视图来管理多条临时消息。"""
        if not self.selected_channel_id:
            await interaction.response.send_message(
                "请先从下拉菜单中选择一个地点。", ephemeral=True
            )
            return

        existing_config = await db_manager.get_channel_message(self.selected_channel_id)
        temporary_data = (
            existing_config.get("temporary_message_data", []) if existing_config else []
        )

        # 确保 temporary_data 是一个列表
        if not isinstance(temporary_data, list):
            temporary_data = [temporary_data] if temporary_data else []

        temp_view = TemporaryMessagesEditView(
            parent_interaction=interaction,
            channel_id=self.selected_channel_id,
            existing_data=temporary_data,
        )
        embed = temp_view.create_embed()
        # 使用 edit_message 切换到临时消息编辑视图，而不是发送新消息
        await interaction.response.edit_message(embed=embed, view=temp_view)

        await temp_view.wait()

        # 结束后刷新主配置视图
        await self.update_view_components()
        new_embed = await self.get_config_list_embed()
        await self.main_interaction.edit_original_response(embed=new_embed, view=self)

    @button(
        label="附加设置",
        style=discord.ButtonStyle.secondary,
        emoji="✨",
        row=1,
        disabled=True,
        custom_id="extra_config_button",
    )
    async def extra_config_button(
        self, interaction: discord.Interaction, button: Button
    ):
        """为永久消息设置图片和页脚。"""
        if not self.selected_channel_id:
            await interaction.response.send_message(
                "请先从下拉菜单中选择一个地点。", ephemeral=True
            )
            return

        config = await db_manager.get_channel_message(self.selected_channel_id)
        permanent_data = (config["permanent_message_data"] or {}) if config else {}
        current_image_url = permanent_data.get("image_url", "")
        current_thumbnail_url = permanent_data.get("thumbnail_url", "")
        current_footer = permanent_data.get("footer", "")

        modal = ExtraConfigModal(
            current_image_url=current_image_url,
            current_thumbnail_url=current_thumbnail_url,
            current_footer=current_footer,
        )
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.submitted_data is not None:
            # 更新 permanent_data 字典
            permanent_data["image_url"] = modal.submitted_data.get("image_url")
            permanent_data["thumbnail_url"] = modal.submitted_data.get("thumbnail_url")
            permanent_data["footer"] = modal.submitted_data.get("footer")

            # 获取现有的 temporary_data，以防被覆盖
            # 获取现有的 temporary_data，以防被覆盖
            existing_temporary_data = (
                (config["temporary_message_data"] or []) if config else []
            )

            # 更新或创建配置
            await db_manager.set_channel_message(
                guild_id=self.guild.id,
                channel_id=self.selected_channel_id,
                permanent_data=permanent_data,
                temporary_data=existing_temporary_data,
            )

            await interaction.followup.send("✅ 附加信息已更新。", ephemeral=True)

            # 刷新视图
            new_embed = await self.get_config_list_embed()
            await self.main_interaction.edit_original_response(
                embed=new_embed, view=self
            )

    @button(
        label="删除此地点配置",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
        row=2,
        disabled=True,
        custom_id="remove_button",
    )
    async def remove_button(self, interaction: discord.Interaction, button: Button):
        """删除已选地点的配置。"""
        if not self.selected_channel_id:
            await interaction.response.send_message(
                "请先从下拉菜单中选择一个地点。", ephemeral=True
            )
            return

        await db_manager.remove_channel_message(self.selected_channel_id)

        # 重置选择并刷新
        self.selected_channel_id = None
        self.selected_location_is_thread = False
        await self.update_view_components()
        new_embed = await self.get_config_list_embed()

        # 重新创建选择菜单并更新视图
        location_select = await self.LocationSelect.create(self.guild)
        # 找到旧的 select 并替换它
        for i, item in enumerate(self.children):
            if isinstance(item, self.LocationSelect):
                self.children[i] = location_select
                break
        else:  # 如果没找到，就添加一个新的
            self.add_item(location_select)

        await self.main_interaction.edit_original_response(embed=new_embed, view=self)
        await interaction.response.send_message(
            "✅ 已成功删除该地点的专属消息配置。", ephemeral=True, delete_after=5
        )

    @button(
        label="⬅️ 上一页",
        style=discord.ButtonStyle.secondary,
        row=3,
        custom_id="prev_page",
    )
    async def prev_page(self, interaction: discord.Interaction, button: Button):
        """翻到上一页。"""
        if self.current_page > 1:
            self.current_page -= 1
        await self.refresh_view(interaction)

    @button(
        label="下一页 ➡️",
        style=discord.ButtonStyle.secondary,
        row=3,
        custom_id="next_page",
    )
    async def next_page(self, interaction: discord.Interaction, button: Button):
        """翻到下一页。"""
        total_pages = (len(self.all_configs) - 1) // self.items_per_page + 1
        if self.current_page < total_pages:
            self.current_page += 1
        await self.refresh_view(interaction)

    @button(label="返回主菜单", style=discord.ButtonStyle.grey, emoji="↩️", row=4)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        """返回主管理面板。"""
        from .main_panel import MainPanelView

        await interaction.response.defer()
        view = MainPanelView(self.main_interaction)
        embed = await view.get_main_embed()
        await self.main_interaction.edit_original_response(embed=embed, view=view)

    async def refresh_view(self, interaction: discord.Interaction):
        """统一刷新视图的快捷方法。"""
        await interaction.response.defer()
        await self.update_view_components()
        embed = await self.get_config_list_embed()
        await self.main_interaction.edit_original_response(embed=embed, view=self)
