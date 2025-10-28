# -*- coding: utf-8 -*-

import discord
from discord.ui import View, Button, button
from aiohttp import ClientConnectorError
import json
import logging
from typing import Optional

from src.guidance.utils.database import guidance_db_manager as db_manager
from src import config
from src.guidance.utils.helpers import create_embed_from_template
from src.guidance.ui.views.message_cycler import MessageCycleView

log = logging.getLogger(__name__)


class EphemeralMessageView(discord.ui.View):
    """
    一个动态的视图，用于在多条临时消息之间导航。
    这个视图自我管理状态和更新。
    """

    def __init__(
        self,
        original_interaction: discord.Interaction,
        messages: list,
        user_path: Optional[list],
        current_step_index: Optional[int],
        user_progress: Optional[dict],
    ):
        super().__init__(timeout=300)
        self.original_interaction = original_interaction
        self.messages = messages
        self.user_path = user_path
        self.current_step_index = current_step_index
        self.user_progress = user_progress
        self.message_index = 0
        self.ephemeral_message: Optional[discord.WebhookMessage] = (
            None  # 保存我们自己发送的临时消息
        )

        self.on_timeout = self.disable_components

    async def disable_components(self):
        for item in self.children:
            item.disabled = True
        if self.ephemeral_message:
            try:
                await self.ephemeral_message.edit(view=self)
            except (discord.NotFound, discord.HTTPException, ClientConnectorError) as e:
                log.warning(
                    f"Could not disable components for ephemeral message due to a network error or message deletion: {e}"
                )
                pass

    def create_embed(self) -> discord.Embed:
        """根据当前索引创建Embed。"""
        message_data = self.messages[self.message_index]

        # 获取原始标题模板
        title_template = message_data.get("title", "详细信息")

        # 获取频道名称并替换占位符
        channel_name = self.original_interaction.channel.name
        final_title = title_template.replace("CHANNEL_NAME_PLACEHOLDER", channel_name)

        embed = discord.Embed(
            title=final_title,
            description=message_data.get("description")
            or message_data.get("content", "..."),
            color=config.EMBED_COLOR_PRIMARY,
        )

        # 添加页脚文本
        footer_text = message_data.get("footer_text")
        if footer_text and footer_text.strip():
            embed.set_footer(text=footer_text.strip())

        # [BUGFIX] 添加对缩略图和图片URL的处理
        thumbnail_url = message_data.get("thumbnail_url")
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        image_url = message_data.get("image_url")
        if image_url:
            embed.set_image(url=image_url)

        return embed

    def add_navigation_buttons(self):
        """添加导航按钮（下一条或完成/下一步）。"""
        self.clear_items()
        is_last_message = self.message_index >= len(self.messages) - 1

        if not is_last_message:
            self.add_item(self.NextButton())
        else:
            # 如果没有用户路径（预览模式），则显示关闭按钮
            if self.user_path is None:
                self.add_item(self.CloseButton())
            else:
                # 否则，执行正常的引导流程逻辑
                is_last_step = self.current_step_index + 1 >= len(self.user_path)
                if not is_last_step:
                    next_step_info = self.user_path[self.current_step_index + 1]
                    next_channel = (
                        self.original_interaction.guild.get_channel_or_thread(
                            next_step_info["location_id"]
                        )
                    )
                    if next_channel:
                        next_step_config = db_manager.get_channel_message_sync(
                            next_channel.id
                        )
                        deployed_message_id = (
                            next_step_config.get("deployed_message_id")
                            if next_step_config
                            else None
                        )
                        next_step_url = (
                            f"https://discord.com/channels/{self.original_interaction.guild.id}/{next_channel.id}/{deployed_message_id}"
                            if deployed_message_id
                            else next_channel.jump_url
                        )
                        self.add_item(
                            self.NextStepButton(
                                label=f"前往下一站: {next_channel.name}",
                                url=next_step_url,
                            )
                        )
                else:
                    self.add_item(self.FinishButton())

    async def start(self):
        """发送初始消息。"""
        self.add_navigation_buttons()
        embed = self.create_embed()
        self.ephemeral_message = await self.original_interaction.followup.send(
            embed=embed, view=self, ephemeral=True
        )

    async def handle_completion(self, interaction: discord.Interaction):
        """统一处理完成引导的逻辑"""
        current_stage = self.user_progress["guidance_stage"]
        if current_stage == "stage_2_in_progress":
            await db_manager.update_user_progress(
                interaction.user.id,
                interaction.guild_id,
                status="completed",
                guidance_stage="stage_2_completed",
            )
            template_name = "completion_message_stage_2"
        else:
            await db_manager.update_user_progress(
                interaction.user.id,
                interaction.guild_id,
                status="completed",
                guidance_stage="stage_1_completed",
            )
            template_name = "completion_message_stage_1"

        template = await db_manager.get_message_template(
            interaction.guild_id, template_name
        )
        if template:
            embed, view = create_embed_from_template(
                template,
                interaction.guild,
                interaction.user,
                template_name=template_name,
            )
            if isinstance(view, MessageCycleView):
                await view.start(interaction, ephemeral=True)
            elif embed:
                await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                config.GUIDANCE_COMPLETION_MESSAGE, ephemeral=True
            )

    # --- 按钮定义和回调 ---

    class NextButton(Button):
        def __init__(self):
            super().__init__(
                label="下一条", style=discord.ButtonStyle.primary, emoji="▶️"
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()  # Defer immediately

            self.view.message_index += 1
            self.view.add_navigation_buttons()
            embed = self.view.create_embed()

            is_last_message = self.view.message_index >= len(self.view.messages) - 1
            if is_last_message and self.view.user_path is not None:
                is_last_step = self.view.current_step_index + 1 >= len(
                    self.view.user_path
                )
                if is_last_step:
                    # Do completion logic first
                    await self.view.handle_completion(interaction)
                else:
                    # Update progress for the next step
                    await db_manager.update_user_progress(
                        interaction.user.id,
                        interaction.guild_id,
                        current_step=self.view.current_step_index + 2,
                    )

            # Now that all logic is done, edit the original message
            await interaction.edit_original_response(embed=embed, view=self.view)

    class NextStepButton(Button):
        def __init__(self, label: str, url: str):
            super().__init__(
                label=label, style=discord.ButtonStyle.link, url=url, emoji="➡️"
            )

    class FinishButton(Button):
        def __init__(self):
            super().__init__(
                label="完成引导", style=discord.ButtonStyle.success, emoji="✅"
            )

        async def callback(self, interaction: discord.Interaction):
            # Defer the interaction to prevent timeout and allow for followups.
            await interaction.response.defer()

            # Perform the completion logic first, as it sends a new followup message.
            await self.view.handle_completion(interaction)

            # Now, disable the buttons on the original message this button was on.
            for item in self.view.children:
                item.disabled = True

            # Since we deferred, we use edit_original_response to edit the message
            # that contained the button.
            await interaction.edit_original_response(view=self.view)

    class CloseButton(Button):
        def __init__(self):
            super().__init__(
                label="关闭", style=discord.ButtonStyle.secondary, emoji="❌"
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            await interaction.delete_original_response()


class PermanentPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(
        label="了解详情 & 前往下一步",
        style=discord.ButtonStyle.primary,
        emoji="ℹ️",
        custom_id="show_channel_details",
    )
    async def show_details(self, interaction: discord.Interaction, button: Button):
        # log.info(
        #     f"[DEBUG] show_details triggered by user {interaction.user.id} in channel {interaction.channel.id} for message {interaction.message.id}"
        # )
        try:
            await interaction.response.defer(ephemeral=True)

            user_progress = await db_manager.get_user_progress(
                interaction.user.id, interaction.guild.id
            )

            # 检查用户是否在引导流程中
            if not user_progress or not user_progress["generated_path_json"]:
                # 用户不在流程中，进入“预览模式”
                log.info(
                    f"User {interaction.user.id} is not in a guidance process. Entering preview mode."
                )
                channel_config = await db_manager.get_channel_message(
                    interaction.channel.id
                )
                temp_messages = (
                    channel_config.get("temporary_message_data")
                    if channel_config
                    else []
                )

                if not isinstance(temp_messages, list) or not temp_messages:
                    # 如果此频道没有临时消息，则发送默认提示
                    await interaction.followup.send(
                        "此地标没有额外的详细信息。", ephemeral=True
                    )
                else:
                    # 如果有临时消息，则以预览模式显示
                    ephemeral_view = EphemeralMessageView(
                        interaction,
                        temp_messages,
                        user_path=None,
                        current_step_index=None,
                        user_progress=None,
                    )
                    await ephemeral_view.start()
                return  # 结束执行

            # --- 以下为用户在引导流程中的原始逻辑 ---
            display_path = json.loads(user_progress["completed_path_json"])
            current_step = user_progress["current_step"]
            current_step_index = current_step - 1

            if not (
                0 <= current_step_index < len(display_path)
                and display_path[current_step_index]["location_id"]
                == interaction.channel.id
            ):
                try:
                    correct_step_index = next(
                        i
                        for i, step in enumerate(display_path)
                        if step["location_id"] == interaction.channel.id
                    )
                    await db_manager.update_user_progress(
                        interaction.user.id,
                        interaction.guild.id,
                        current_step=correct_step_index + 1,
                    )
                    current_step_index = correct_step_index
                except StopIteration:
                    await interaction.followup.send(
                        "🤔 你似乎偏离了为你规划的引导路径。", ephemeral=True
                    )
                    return

            channel_config = await db_manager.get_channel_message(
                interaction.channel.id
            )
            temp_messages = (
                channel_config["temporary_message_data"]
                if channel_config and channel_config["temporary_message_data"]
                else []
            )
            if not isinstance(temp_messages, list) or not temp_messages:
                log.info(
                    f"[DEBUG] No temporary messages found for channel {interaction.channel.id}. Calling handle_no_temporary_messages."
                )
                await self.handle_no_temporary_messages(
                    interaction, user_progress, display_path, current_step_index
                )
                return

            ephemeral_view = EphemeralMessageView(
                interaction,
                temp_messages,
                display_path,
                current_step_index,
                user_progress,
            )
            await ephemeral_view.start()

        except discord.errors.NotFound:
            log.warning(
                f"处理交互时失败 (NotFound: Unknown Interaction/Webhook)，可能由超时引起。交互已忽略。"
            )
        except Exception as e:
            log.error(f"处理频道详情按钮时出现意外错误: {e}", exc_info=True)
            try:
                await interaction.followup.send(
                    "❌ 处理您的请求时发生了一个内部错误。", ephemeral=True
                )
            except discord.errors.NotFound:
                pass

    async def handle_no_temporary_messages(
        self,
        interaction: discord.Interaction,
        user_progress: dict,
        user_path: list,
        current_step_index: int,
    ):
        """处理没有配置临时消息的情况。"""
        log.info(
            f"[DEBUG] Entered handle_no_temporary_messages for user {interaction.user.id}."
        )
        next_step_view = View(timeout=180)
        description = "此步骤没有更多详细信息。"
        is_last_step = current_step_index + 1 >= len(user_path)

        if not is_last_step:
            await db_manager.update_user_progress(
                interaction.user.id,
                interaction.guild.id,
                current_step=current_step_index + 2,
            )
            next_step_info = user_path[current_step_index + 1]
            next_channel = interaction.guild.get_channel_or_thread(
                next_step_info["location_id"]
            )

            if next_channel:
                next_step_url = next_channel.jump_url
                next_step_view.add_item(
                    Button(
                        label=f"前往下一站: {next_channel.name}",
                        style=discord.ButtonStyle.link,
                        url=next_step_url,
                        emoji="➡️",
                    )
                )
                description += f"\n\n请直接前往下一站：{next_channel.mention}"
            else:
                description += (
                    "\n\n**路径中的下一个地点已不存在，您的引导已提前完成。**"
                )
                await self.handle_completion_in_main_flow(interaction, user_progress)
        else:
            await self.handle_completion_in_main_flow(interaction, user_progress)

        embed = discord.Embed(
            title="步骤信息", description=description, color=config.EMBED_COLOR_PRIMARY
        )
        log.info(
            f"[DEBUG] About to send followup in handle_no_temporary_messages. View has {len(next_step_view.children)} item(s)."
        )
        if description:  # 只有在有内容时才发送
            await interaction.followup.send(
                embed=embed, view=next_step_view, ephemeral=True
            )

    async def handle_completion_in_main_flow(
        self, interaction: discord.Interaction, user_progress: dict
    ):
        """在主流程中处理完成逻辑，它不会发送自己的消息，而是让调用者处理。"""
        current_stage = user_progress["guidance_stage"]
        template_name = "completion_message_stage_1"
        if current_stage == "stage_2_in_progress":
            await db_manager.update_user_progress(
                interaction.user.id,
                interaction.guild_id,
                status="completed",
                guidance_stage="stage_2_completed",
            )
            template_name = "completion_message_stage_2"
        else:
            await db_manager.update_user_progress(
                interaction.user.id,
                interaction.guild_id,
                status="completed",
                guidance_stage="stage_1_completed",
            )

        template = await db_manager.get_message_template(
            interaction.guild_id, template_name
        )
        if template:
            embed, view = create_embed_from_template(
                template,
                interaction.guild,
                interaction.user,
                template_name=template_name,
            )
            if isinstance(view, MessageCycleView):
                await view.start(interaction, ephemeral=True)
                return True  # 返回 True 表示已处理
        return False  # 返回 False 表示未处理
