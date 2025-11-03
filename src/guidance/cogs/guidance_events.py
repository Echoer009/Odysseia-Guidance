# -*- coding: utf-8 -*-

import logging
import discord
from discord.ext import commands
import asyncio

# 从我们自己的模块中导入
from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.repositories.user_progress_repository import UserProgressRepository
from src.guidance.services.guidance_service import GuidanceService
# UI 组件已移至新文件，此处不再需要
# from ..utils.views.guidance_components import InitialGuidanceView, TagSelect

log = logging.getLogger(__name__)


class GuidanceEventsCog(commands.Cog):
    """处理机器人核心后台逻辑。"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.user_progress_repo = UserProgressRepository(db_manager)
        self.guidance_service = GuidanceService(self.bot, self.user_progress_repo)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles == after.roles:
            return

        guild_id = after.guild.id
        guild_config = await db_manager.get_guild_config(guild_id)
        if not guild_config:
            return

        buffer_role_id = guild_config["buffer_role_id"]
        verified_role_id = guild_config["verified_role_id"]

        # 如果两个阶段的身份组都未设置，则不执行任何操作
        if not buffer_role_id and not verified_role_id:
            return

        roles_before = {role.id for role in before.roles}
        roles_after = {role.id for role in after.roles}
        gained_roles = roles_after - roles_before

        user_progress = await self.user_progress_repo.get(after.id, guild_id)

        # --- 场景一：用户获得“缓冲区”身份组，触发第一阶段引导 ---
        if buffer_role_id in gained_roles:
            # 如果用户已经有任何引导记录，则跳过，防止重复触发
            # if user_progress:
            #     log.info(f"用户 {after.name} 已有引导记录，跳过重复的缓冲区引导。")
            #     return

            log.info(
                f"检测到用户 {after.name} 获得缓冲区身份组，准备触发第一阶段引导。"
            )
            await self.guidance_service.start_guidance_flow(after)
            return

        # --- 场景二：用户获得“已验证”身份组，触发第二阶段引导 ---
        if verified_role_id in gained_roles:
            # 如果用户没有进度，或者第一阶段未完成，则不处理
            if not user_progress or user_progress.guidance_stage != "stage_1_completed":
                log.info(
                    f"用户 {after.name} 获得了已验证身份组，但其第一阶段引导未完成，跳过。"
                )
                return

            log.info(
                f"检测到用户 {after.name} 获得已验证身份组，准备触发第二阶段引导。"
            )
            # [BUGFIX] 使用 asyncio.create_task 将耗时操作放入后台，防止阻塞事件循环导致交互失败
            asyncio.create_task(
                self.guidance_service.start_stage_2_guidance(after, user_progress)
            )
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(GuidanceEventsCog(bot))
