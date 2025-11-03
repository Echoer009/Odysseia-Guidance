# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
import logging

from src.guidance.repositories.user_progress_repository import UserProgressRepository
from src.guidance.models.user_progress import UserProgress
from src.guidance.utils.database import (
    guidance_db_manager as db_manager,
)  # 暂时还需要它来获取模板等
from src.guidance.utils.helpers import create_embed_from_template
from src.guidance import config as guidance_config

# 导入 UI 组件，这是正确的做法
from src.guidance.ui.views.guidance_components import TagSelect

log = logging.getLogger(__name__)


class GuidanceService:
    """
    处理所有与用户引导流程相关的核心业务逻辑。
    这一层不直接与 Discord 的事件或视图交互，而是被它们调用。
    """

    def __init__(self, bot: commands.Bot, user_progress_repo: UserProgressRepository):
        self.bot = bot
        self.user_progress_repo = user_progress_repo

    async def start_stage_2_guidance(
        self, member: discord.Member, user_progress: UserProgress
    ):
        """向用户发送祝贺信息，并引导他们完成【第二阶段】的路径。"""
        try:
            guild = member.guild

            # 1. 直接从模型对象获取待解锁的路径 (JSON解析已在模型中完成)
            stage_2_path_unfiltered = user_progress.remaining_path

            # 2. 基于用户当前权限，再次过滤第二阶段的路径
            stage_2_path = []
            for step in stage_2_path_unfiltered:
                channel = guild.get_channel_or_thread(step["location_id"])
                if channel and channel.permissions_for(member).view_channel:
                    stage_2_path.append(step)

            # 如果过滤后没有新的可见路径，则只发送祝贺消息
            if not stage_2_path:
                log.info(
                    f"用户 {member.name} 已解锁新身份组，但剩余路径当前均不可见或已全部完成。"
                )
                user_progress.guidance_stage = "stage_2_completed"
                await self.user_progress_repo.update(user_progress)
                return

            # 2. 准备消息
            template = await db_manager.get_message_template(
                guild.id, "welcome_message_stage_2"
            )
            path_preview_string = " -> ".join(
                [f"<#{step['location_id']}>" for step in stage_2_path]
            )

            embed, view = create_embed_from_template(
                template,
                guild,
                user=member,
                template_name="welcome_message_stage_2",
                generated_path=path_preview_string,
            )

            # 3. 准备“出发”按钮
            first_channel_id = stage_2_path[0]["location_id"]
            first_channel = guild.get_channel_or_thread(first_channel_id)
            if not first_channel:
                log.warning(f"第二阶段引导的起始频道 {first_channel_id} 已不存在。")
                # 即使无法跳转，也应告知用户
                await member.send(embed=embed)
                return

            first_step_config = await db_manager.get_channel_message(first_channel_id)
            deployed_message_id = (
                first_step_config["deployed_message_id"] if first_step_config else None
            )
            jump_url = (
                f"https://discord.com/channels/{guild.id}/{first_channel_id}/{deployed_message_id}"
                if deployed_message_id
                else first_channel.jump_url
            )

            # 4. 发送私信并更新数据库
            final_view = view if view is not None else discord.ui.View()

            # 定义一个创建按钮的函数，以便复用
            def create_start_button():
                return discord.ui.Button(
                    label=f"前往新区域：{first_channel.name}",
                    style=discord.ButtonStyle.link,
                    url=jump_url,
                    emoji="✨",
                )

            # 如果是 MessageCycleView，则配置“出发”按钮工厂
            if isinstance(final_view, discord.ui.View) and hasattr(
                final_view, "start_button_factory"
            ):
                final_view.add_start_button = True
                final_view.start_button_factory = create_start_button
                final_view.update_view()
            # 否则（对于非多消息模板），直接添加按钮
            else:
                final_view.add_item(create_start_button())

            await member.send(embed=embed, view=final_view)

            # --- [REFACTOR] 更新用户进度，合并第一和第二阶段路径 ---
            newly_visible_location_ids = {step["location_id"] for step in stage_2_path}

            # 直接在模型对象上操作
            user_progress.completed_path.extend(stage_2_path)
            user_progress.remaining_path = [
                step
                for step in user_progress.remaining_path
                if step["location_id"] not in newly_visible_location_ids
            ]
            user_progress.guidance_stage = "stage_2_in_progress"

            await self.user_progress_repo.update(user_progress)
            log.info(
                f"已向用户 {member.name} 发送第二阶段引导私信，并更新了其组合路径。"
            )

        except discord.Forbidden:
            log.warning(f"无法向用户 {member.name} 发送第二阶段引导私信。")
        except Exception as e:
            log.error(
                f"开始第二阶段引导时发生错误 (用户: {member.name}): {e}", exc_info=True
            )

    async def start_guidance_flow(self, member: discord.Member):
        """向用户发送私信，让用户选择兴趣标签以开始【第一阶段】引导流程。"""
        try:
            guild_id = member.guild.id

            # 获取配置，包括默认标签ID
            guild_config = await db_manager.get_guild_config(guild_id)
            default_tag_id = guild_config["default_tag_id"] if guild_config else None

            all_tags = await db_manager.get_all_tags(guild_id)

            # 过滤掉默认标签，使其在选择列表中不可见
            visible_tags = [tag for tag in all_tags if tag["tag_id"] != default_tag_id]

            if not all_tags:  # 检查所有标签，而不是可见标签
                log.warning(
                    f"服务器 {member.guild.name} 已触发引导流程，但尚未配置任何兴趣标签。"
                )
                return

            template = await db_manager.get_message_template(
                guild_id, "welcome_message"
            )
            embed, view = create_embed_from_template(
                template,
                member.guild,
                user=member,
                template_name="welcome_message",
                server_name=member.guild.name,
            )

            # --- 新的、更智能的视图处理逻辑 ---
            final_view = (
                view  # 从 create_embed_from_template 获取的可能是 MessageCycleView
            )

            # 如果模板没有提供视图 (例如，它不是一个多消息模板)
            # 我们需要创建一个基础视图来承载 TagSelect
            if final_view is None:
                final_view = discord.ui.View(timeout=300.0)
                final_view.add_item(TagSelect(self.bot, guild_id, visible_tags))

            # 如果模板提供了 MessageCycleView，我们需要告诉它如何创建 TagSelect
            elif isinstance(final_view, discord.ui.View) and hasattr(
                final_view, "tag_select_factory"
            ):
                # 使用 lambda 来捕获当前上下文 (self, guild_id, visible_tags)
                # 这使得 MessageCycleView 可以在需要时才创建 TagSelect
                final_view.tag_select_factory = lambda: TagSelect(
                    self.bot, guild_id, visible_tags
                )
                final_view.add_tag_select = True
                # 重新调用 update_view 以应用更改
                final_view.update_view()

            await member.send(embed=embed, view=final_view)

            await self.user_progress_repo.create_or_reset(
                member.id,
                guild_id,
                status=guidance_config.USER_STATUS_PENDING_SELECTION,
                guidance_stage="stage_1_pending",
            )
            log.info(f"已向用户 {member.name} 发送第一阶段引导私信。")

        except discord.Forbidden:
            log.warning(f"无法向用户 {member.name} 发送私信。")
        except Exception as e:
            log.error(
                f"开始第一阶段引导时发生错误 (用户: {member.name}): {e}", exc_info=True
            )
