# -*- coding: utf-8 -*-

import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from datetime import datetime, timedelta
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)


def _parse_developer_ids() -> set[int]:
    """从环境变量中解析逗号分隔的 ID 列表，兼容带引号的字符串"""
    ids_str = os.getenv("DEVELOPER_USER_IDS", "")
    if not ids_str:
        return set()

    # 移除字符串两端的引号
    ids_str = ids_str.strip().strip("'\"")

    try:
        return {int(id_str.strip()) for id_str in ids_str.split(",") if id_str.strip()}
    except ValueError:
        log.error(f"无法解析 DEVELOPER_USER_IDS: '{ids_str}'", exc_info=True)
        return set()


def is_developer():
    """检查用户是否是开发者"""
    developer_ids = _parse_developer_ids()

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id not in developer_ids:
            log.warning(
                f"权限检查失败: 用户 {interaction.user.id} 不在开发者列表 {developer_ids} 中。"
            )
            await interaction.response.send_message(
                "你没有权限使用此命令。", ephemeral=True
            )
            return False
        return True

    return app_commands.check(predicate)


class BlacklistAdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="封禁", description="将用户加入黑名单 (仅开发者可用)")
    @app_commands.describe(
        user_id="要封禁的用户ID",
        duration_minutes="封禁时长(分钟)",
        reason="封禁理由",
        global_ban="是否全局封禁 (默认否)",
    )
    @app_commands.default_permissions(manage_guild=True)
    @is_developer()
    async def blacklist_user(
        self,
        interaction: discord.Interaction,
        user_id: str,
        duration_minutes: int,
        reason: str = "无",
        global_ban: bool = False,
    ):
        try:
            target_user_id = int(user_id)
        except ValueError:
            await interaction.response.send_message(
                "请输入有效的用户ID。", ephemeral=True
            )
            return

        expires_at = datetime.utcnow() + timedelta(minutes=duration_minutes)

        try:
            try:
                target_user = await self.bot.fetch_user(target_user_id)
                if target_user:
                    embed = discord.Embed(
                        title="封禁通知",
                        description=f"您已被开发者封禁，时长为 {duration_minutes} 分钟。在此期间您将无法与 类脑娘 互动。",
                        color=discord.Color.red(),
                    )
                    embed.add_field(name="理由", value=reason, inline=False)
                    embed.set_footer(
                        text=f"封禁时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                    )
                    try:
                        await target_user.send(embed=embed)
                    except discord.Forbidden:
                        log.warning(
                            f"无法向用户 {target_user_id} 发送封禁通知私信，可能因为用户关闭了私信。"
                        )
            except discord.NotFound:
                log.warning(f"无法找到用户 {target_user_id}，无法发送私信。")

            if global_ban:
                # 全局封禁
                if await chat_db_manager.is_user_globally_blacklisted(target_user_id):
                    await interaction.response.send_message(
                        f"用户 <@{target_user_id}> 已经在全局黑名单中。", ephemeral=True
                    )
                    return
                await chat_db_manager.add_to_global_blacklist(
                    target_user_id, expires_at
                )
                await interaction.response.send_message(
                    f"已将用户 <@{target_user_id}> 加入全局黑名单，时长 {duration_minutes} 分钟。",
                    ephemeral=True,
                )
                log.info(
                    f"开发者 {interaction.user} 将用户 {target_user_id} 加入全局黑名单，时长 {duration_minutes} 分钟，理由: {reason}。"
                )
            else:
                # 服务器封禁
                guild_id = interaction.guild.id if interaction.guild else 0
                if await chat_db_manager.is_user_blacklisted(target_user_id, guild_id):
                    await interaction.response.send_message(
                        f"用户 <@{target_user_id}> 已经在当前服务器的黑名单中。",
                        ephemeral=True,
                    )
                    return
                await chat_db_manager.add_to_blacklist(
                    target_user_id, guild_id, expires_at
                )
                await interaction.response.send_message(
                    f"已将用户 <@{target_user_id}> 加入当前服务器的黑名单，时长 {duration_minutes} 分钟。",
                    ephemeral=True,
                )
                log.info(
                    f"开发者 {interaction.user} 将用户 {target_user_id} 加入服务器 {guild_id} 的黑名单，时长 {duration_minutes} 分钟，理由: {reason}。"
                )
        except Exception as e:
            log.error(f"封禁用户时出错: {e}", exc_info=True)
            await interaction.response.send_message(
                "封禁用户时发生错误，请检查日志。", ephemeral=True
            )

    @app_commands.command(
        name="解封", description="将用户从黑名单中移除 (仅开发者可用)"
    )
    @app_commands.describe(
        user_id="要解封的用户ID", global_ban="是否从全局黑名单解封 (默认否)"
    )
    @app_commands.default_permissions(manage_guild=True)
    @is_developer()
    async def unblacklist_user(
        self, interaction: discord.Interaction, user_id: str, global_ban: bool = False
    ):
        try:
            target_user_id = int(user_id)
        except ValueError:
            await interaction.response.send_message(
                "请输入有效的用户ID。", ephemeral=True
            )
            return

        try:
            if global_ban:
                # 全局解封
                if not await chat_db_manager.is_user_globally_blacklisted(
                    target_user_id
                ):
                    await interaction.response.send_message(
                        f"用户 <@{target_user_id}> 不在全局黑名单中。", ephemeral=True
                    )
                    return
                await chat_db_manager.remove_from_global_blacklist(target_user_id)
                await interaction.response.send_message(
                    f"已将用户 <@{target_user_id}> 从全局黑名单中移除。", ephemeral=True
                )
                log.info(
                    f"开发者 {interaction.user} 将用户 {target_user_id} 从全局黑名单中移除。"
                )
            else:
                # 服务器解封
                guild_id = interaction.guild.id if interaction.guild else 0
                if not await chat_db_manager.is_user_blacklisted(
                    target_user_id, guild_id
                ):
                    await interaction.response.send_message(
                        f"用户 <@{target_user_id}> 不在当前服务器的黑名单中。",
                        ephemeral=True,
                    )
                    return
                await chat_db_manager.remove_from_blacklist(target_user_id, guild_id)
                await interaction.response.send_message(
                    f"已将用户 <@{target_user_id}> 从当前服务器的黑名单中移除。",
                    ephemeral=True,
                )
                log.info(
                    f"开发者 {interaction.user} 将用户 {target_user_id} 从服务器 {guild_id} 的黑名单中移除。"
                )
        except Exception as e:
            log.error(f"解封用户时出错: {e}", exc_info=True)
            await interaction.response.send_message(
                "解封用户时发生错误，请检查日志。", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(BlacklistAdminCog(bot))
