# -*- coding: utf-8 -*-

import logging
import discord
from discord.ext import commands
import json
from typing import List, Dict, Any

# 从我们自己的模块中导入
from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.utils.helpers import create_embed_from_template
from src.guidance import config as guidance_config

log = logging.getLogger(__name__)


class TagSelect(discord.ui.Select):
    """让用户选择兴趣标签的下拉菜单。"""

    def __init__(self, bot: commands.Bot, guild_id: int, tags: List[Dict[str, Any]]):
        self.bot = bot
        self.guild_id = guild_id

        options = [
            discord.SelectOption(
                label=tag["tag_name"],
                value=str(tag["tag_id"]),
                description=tag["description"],
            )
            for tag in tags
        ]
        if not options:
            options.append(
                discord.SelectOption(
                    label="没有可用的引导方向", value="disabled", default=True
                )
            )

        super().__init__(
            placeholder="请选择一个或多个你感兴趣的方向...",
            min_values=1,
            max_values=len(options) if options[0].value != "disabled" else 1,
            options=options,
            disabled=not tags,
        )

    async def callback(self, interaction: discord.Interaction):
        # 立即响应交互以防止“未知交互”错误，并将响应时间延长至15分钟
        await interaction.response.defer()

        # 禁用视图，防止重复提交
        for item in self.view.children:
            item.disabled = True
        # 由于我们已经 defer()，现在必须使用 edit_original_response() 来更新消息
        await interaction.edit_original_response(view=self.view)

        selected_tag_ids = [int(v) for v in self.values]

        try:
            # --- 路径合并逻辑 ---
            merged_path = []
            seen_location_ids = set()
            all_tags_info = []

            # --- [新] 默认标签逻辑 ---
            # 1. 获取服务器配置，查看是否有默认标签
            guild_config = await db_manager.get_guild_config(self.guild_id)
            default_tag_id = guild_config["default_tag_id"] if guild_config else None

            # 2. 将用户选择和默认标签合并，并去重
            final_tag_ids = set(selected_tag_ids)
            if default_tag_id:
                final_tag_ids.add(default_tag_id)

            for tag_id in final_tag_ids:
                tag_info = await db_manager.get_tag_by_id(tag_id)
                if tag_info:
                    all_tags_info.append(tag_info)

                path_steps = await db_manager.get_path_for_tag(tag_id)
                for step in path_steps:
                    if step["location_id"] not in seen_location_ids:
                        merged_path.append(dict(step))
                        seen_location_ids.add(step["location_id"])

            if not merged_path:
                await interaction.followup.send(
                    "❌ 抱歉，您选择的方向下没有配置任何有效的引导路径。请联系管理员。",
                    ephemeral=True,
                )
                return

            # --- 寻找入口点 ---
            first_step_config = None
            for step in merged_path:
                channel_config = await db_manager.get_channel_message(
                    step["location_id"]
                )
                if channel_config and channel_config["deployed_message_id"]:
                    first_step_config = channel_config
                    break

            if not first_step_config:
                await interaction.followup.send(
                    "❌ 抱歉，该引导路径的入口点尚未部署。请联系管理员。",
                    ephemeral=True,
                )
                return

            # --- [新] 发送包含路径预览的最终消息 ---
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                log.error(f"在TagSelect回调中无法找到服务器: {self.guild_id}")
                await interaction.followup.send(
                    "❌ 发生内部错误，无法识别您所在的服务器。", ephemeral=True
                )
                return

            # --- [新] 权限过滤逻辑 ---
            # 根据用户当前权限，过滤掉不可见的频道
            member = guild.get_member(interaction.user.id)
            if not member:
                await interaction.followup.send(
                    "❌ 无法获取您的成员信息，请稍后再试。", ephemeral=True
                )
                return

            # 将完整路径拆分为“可见”和“待解锁”两部分
            visible_path = []
            remaining_path = []
            for step in merged_path:
                channel = guild.get_channel_or_thread(step["location_id"])
                if channel and channel.permissions_for(member).view_channel:
                    visible_path.append(step)
                else:
                    remaining_path.append(step)

            # 如果第一阶段完全没有可访问的路径
            if not visible_path:
                await interaction.followup.send(
                    "ℹ️ 根据您当前的权限，为您生成的引导路径为空。当您权限提升后，我们会再次引导您。",
                    ephemeral=True,
                )
                # 记录进度，将所有路径都放入待解锁
                await db_manager.update_user_progress(
                    interaction.user.id,
                    self.guild_id,
                    status=guidance_config.USER_STATUS_COMPLETED,
                    guidance_stage="stage_1_completed",
                    selected_tags_json=json.dumps(selected_tag_ids),
                    generated_path_json=json.dumps(merged_path),
                    completed_path_json="[]",  # 第一阶段可见路径为空
                    remaining_path_json=json.dumps(remaining_path),
                )
                return

            # 1. 生成基于可见路径的预览字符串
            path_preview_string = " -> ".join(
                [f"<#{step['location_id']}>" for step in visible_path]
            )

            # 2. 获取模板并构建基础 Embed
            # 过滤掉默认标签，使其在显示给用户的消息中不可见
            selected_tag_names = [
                t["tag_name"] for t in all_tags_info if t["tag_id"] != default_tag_id
            ]
            template = await db_manager.get_message_template(
                self.guild_id, "prompt_message_stage_1"
            )
            embed, view = create_embed_from_template(
                template,
                guild,
                user=interaction.user,
                template_name="prompt_message_stage_1",
                tag_name=", ".join(selected_tag_names),
                generated_path=path_preview_string,
            )

            # 4. 创建包含“出发”按钮的 View
            first_channel_id = visible_path[0]["location_id"]
            first_channel = guild.get_channel_or_thread(first_channel_id)

            # 极端情况处理：如果第一个地点都找不到了
            if not first_channel:
                await interaction.followup.send(
                    "❌ 路径的起始地点似乎已失效，请联系管理员。", ephemeral=True
                )
                return

            # --- 新逻辑：优先跳转到永久消息 ---
            first_step_config = await db_manager.get_channel_message(first_channel_id)
            deployed_message_id = (
                first_step_config["deployed_message_id"] if first_step_config else None
            )

            if deployed_message_id:
                jump_url = f"https://discord.com/channels/{guild.id}/{first_channel_id}/{deployed_message_id}"
            else:
                jump_url = first_channel.jump_url  # 备用方案

            final_view = discord.ui.View()
            final_view.add_item(
                discord.ui.Button(
                    label=f"出发！前往第一站：{first_channel.name}",
                    style=discord.ButtonStyle.link,
                    url=jump_url,
                    emoji="🚀",
                )
            )

            # 5. 编辑原始消息，显示新的预览面板
            final_view_to_send = view if view is not None else discord.ui.View()

            # 如果是 MessageCycleView，则配置“出发”按钮工厂
            if isinstance(final_view_to_send, discord.ui.View) and hasattr(
                final_view_to_send, "start_button_factory"
            ):
                final_view_to_send.add_start_button = True
                final_view_to_send.start_button_factory = lambda: discord.ui.Button(
                    label=f"出发！前往第一站：{first_channel.name}",
                    style=discord.ButtonStyle.link,
                    url=jump_url,
                    emoji="🚀",
                )
                # 更新视图以应用工厂
                final_view_to_send.update_view()
            # 否则（对于非多消息模板），直接添加按钮
            else:
                final_view_to_send.add_item(
                    discord.ui.Button(
                        label=f"出发！前往第一站：{first_channel.name}",
                        style=discord.ButtonStyle.link,
                        url=jump_url,
                        emoji="🚀",
                    )
                )

            await interaction.edit_original_response(
                embed=embed, view=final_view_to_send
            )

            # --- 更新数据库 ---
            await db_manager.update_user_progress(
                interaction.user.id,
                self.guild_id,
                status=guidance_config.USER_STATUS_IN_PROGRESS,
                guidance_stage="stage_1_in_progress",
                selected_tags_json=json.dumps(selected_tag_ids),
                generated_path_json=json.dumps(merged_path),  # 存储完整路径作为原始记录
                completed_path_json=json.dumps(visible_path),  # 存储第一阶段的可见路径
                remaining_path_json=json.dumps(remaining_path),  # 存储待解锁的路径
            )
            log.info(
                f"用户 {interaction.user.name} 选择了标签 {selected_tag_names} 并生成了合并路径。"
            )

        except Exception as e:
            log.error(f"处理标签选择回调时出错: {e}", exc_info=True)
            await interaction.followup.send(
                "处理您的选择时发生了一个未知的错误，请稍后再试。", ephemeral=True
            )


class InitialGuidanceView(discord.ui.View):
    """引导流程开始时发送给用户的私信视图，包含标签选择。"""

    def __init__(
        self,
        bot: commands.Bot,
        guild_id: int,
        tags: List[Dict[str, Any]],
        timeout: float = 300.0,
    ):
        super().__init__(timeout=timeout)
        self.add_item(TagSelect(bot, guild_id, tags))
