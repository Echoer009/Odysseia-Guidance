# -*- coding: utf-8 -*-

import asyncio
import discord
import logging
import argparse
import sys
import os
from typing import Optional

# --- 设置项目根路径 ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- 加载环境变量 ---
from dotenv import load_dotenv

load_dotenv()

from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.utils.helpers import create_embed_from_template_data
from src.guidance.ui.views.channel_panel import PermanentPanelView

# --- 日志配置 ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# --- Discord 客户端 ---
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
client = discord.Client(intents=intents)


async def redeploy_single_panel(
    guild: discord.Guild, channel: discord.TextChannel, config_item: dict
) -> bool:
    """为单个频道强制重新部署引导面板。"""
    log.info(f"  [部署模式] 开始为频道 #{channel.name} 部署...")
    try:
        perm_data = config_item.get("permanent_message_data") or {}
        if not perm_data:
            log.error(f"  ❌ 部署失败: 频道 #{channel.name} 缺少永久消息配置。")
            return False

        # 1. 清理旧面板
        expected_footer = perm_data.get("footer_text")
        if expected_footer:
            log.info(f"  - 正在扫描并清理 #{channel.name} 中的旧面板...")
            deleted_count = 0
            try:
                async for message in channel.history(limit=100):
                    if (
                        message.author.id == client.user.id
                        and message.embeds
                        and message.embeds[0].footer
                        and message.embeds[0].footer.text == expected_footer
                    ):
                        await message.delete()
                        deleted_count += 1
                if deleted_count > 0:
                    log.info(f"  - 成功清理了 {deleted_count} 个旧面板。")
            except discord.Forbidden:
                log.warning(f"  - 清理时权限不足，跳过清理步骤。")
            except Exception as e:
                log.error(f"  - 清理旧面板时发生未知错误: {e}")

        # 2. 创建并发送新消息
        perm_embed = create_embed_from_template_data(perm_data, channel=channel)
        view = PermanentPanelView()
        new_message = await channel.send(embed=perm_embed, view=view)

        # 3. 更新数据库
        await db_manager.update_channel_deployment_id(channel.id, new_message.id)
        log.info(f"  ✅ 部署成功。新消息ID: {new_message.id}。数据库已更新。")
        return True

    except discord.Forbidden:
        log.error(
            f"  ❌ 部署失败: 权限不足，无法在 #{channel.name} 中发送消息或删除消息。"
        )
        return False
    except Exception as e:
        log.error(f"  ❌ 部署时发生未知错误: {e}", exc_info=True)
        return False


async def repair_deployment_ids(
    guild_id: int,
    channel_id_to_force: Optional[int] = None,
    deploy_all_missing: bool = False,
):
    """
    扫描、强制重部署或批量部署引导面板以修复数据库记录。
    """
    log.info(f"--- 开始为服务器 {guild_id} 修复部署ID ---")
    if channel_id_to_force:
        log.warning(
            f"--- [警告] 已激活对频道 {channel_id_to_force} 的强制重部署模式 ---"
        )
    elif deploy_all_missing:
        log.warning("--- [警告] 已激活一键部署所有缺失面板模式 ---")

    await db_manager.init_async()
    log.info("数据库连接成功。")

    try:
        guild = await client.fetch_guild(guild_id)
        log.info(f"成功获取服务器: {guild.name}")
    except (discord.NotFound, discord.Forbidden):
        log.error(
            f"无法获取服务器 {guild_id}。请检查机器人是否在该服务器中以及是否有权限。"
        )
        return

    all_configs = await db_manager.get_all_channel_messages(guild.id)

    # 根据模式确定要处理的目标
    if channel_id_to_force:
        targets_to_fix = [
            c for c in all_configs if c.get("channel_id") == channel_id_to_force
        ]
        if not targets_to_fix:
            log.error(f"错误：在数据库中找不到频道ID为 {channel_id_to_force} 的配置。")
            return
    else:
        # 默认模式（搜索）和批量部署模式都基于这个列表
        targets_to_fix = [
            c
            for c in all_configs
            if c.get("permanent_message_data") and not c.get("deployed_message_id")
        ]

    if not targets_to_fix:
        log.info("数据库中所有已配置的永久面板都已有部署ID，无需操作。")
        return

    log.info(f"共找到 {len(targets_to_fix)} 个需要处理的频道。")

    success_count = 0
    fail_count = 0

    for config_item in targets_to_fix:
        channel_id = config_item["channel_id"]
        channel_name = f"ID: {channel_id}"

        try:
            channel = await guild.fetch_channel(channel_id)
            channel_name = f"#{channel.name}"

            # 强制单频道重部署 或 一键部署所有
            if channel_id_to_force or deploy_all_missing:
                if await redeploy_single_panel(guild, channel, config_item):
                    success_count += 1
                else:
                    fail_count += 1
                continue

            # --- 默认的搜索修复逻辑 ---
            perm_data = config_item.get("permanent_message_data", {})
            expected_footer = perm_data.get("footer_text")

            if not expected_footer:
                log.warning(
                    f"⚠️ {channel_name}: 配置中缺少 'footer_text'，无法进行匹配。跳过。"
                )
                fail_count += 1
                continue

            log.info(
                f"正在扫描频道 {channel_name} 的最近1000条消息，寻找页脚为 '{expected_footer}' 的面板..."
            )

            found_message = None
            async for message in channel.history(limit=1000):
                if (
                    message.author.id == client.user.id
                    and message.embeds
                    and message.embeds[0].footer
                    and message.embeds[0].footer.text == expected_footer
                ):
                    found_message = message
                    break

            if found_message:
                log.info(
                    f"  ✅ 在 {channel_name} 找到匹配的消息 (ID: {found_message.id})。正在更新数据库..."
                )
                await db_manager.update_channel_deployment_id(
                    channel_id, found_message.id
                )
                log.info(f"  ✅ 数据库更新成功。")
                success_count += 1
            else:
                log.error(
                    f"  ❌ 在 {channel_name} 的最近1000条消息中未能找到匹配的面板。"
                )
                log.error(
                    f"     请尝试使用 --force-redeploy --channel-id {channel_id} 或 --deploy-all-missing 模式进行修复。"
                )
                fail_count += 1

        except discord.NotFound:
            log.error(f"❌ 无法找到频道 {channel_name}。可能已被删除。")
            fail_count += 1
        except discord.Forbidden:
            log.error(f"❌ 权限不足，无法读取或操作频道 {channel_name}。")
            fail_count += 1
        except Exception as e:
            log.error(f"❌ 处理频道 {channel_name} 时发生未知错误: {e}", exc_info=True)
            fail_count += 1

    log.info("--- 任务完成 ---")
    log.info(f"总计: {len(targets_to_fix)} 个频道")
    log.info(f"成功: {success_count} 个")
    log.info(f"失败/跳过: {fail_count} 个")


async def main():
    parser = argparse.ArgumentParser(
        description="修复、强制重部署或批量部署引导面板，以解决数据库中部署ID丢失的问题。"
    )
    parser.add_argument(
        "--guild-id", type=int, required=True, help="需要操作的服务器（Guild）的ID。"
    )

    # 创建一个互斥组，确保这些操作模式不会同时被激活
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--force-redeploy",
        dest="channel_id_to_force",
        type=int,
        metavar="CHANNEL_ID",
        help="为指定的单个频道ID强制部署新面板，而不是搜索旧面板。",
    )
    mode_group.add_argument(
        "--deploy-all-missing",
        action="store_true",
        help="一键为所有在数据库有配置但没有部署ID的频道部署新面板。",
    )

    args = parser.parse_args()

    bot_token = os.getenv("DISCORD_TOKEN")
    if not bot_token:
        log.error("错误：未在 .env 文件或环境变量中找到 DISCORD_TOKEN。")
        return

    try:
        await client.login(bot_token)
        await repair_deployment_ids(
            args.guild_id, args.channel_id_to_force, args.deploy_all_missing
        )
    except discord.LoginFailure:
        log.error("Discord 登录失败，请检查你的 DISCORD_TOKEN 是否正确。")
    except Exception as e:
        log.error(f"发生未知错误: {e}", exc_info=True)
    finally:
        await client.close()
        await db_manager.close()
        log.info("客户端和数据库连接已关闭。")


if __name__ == "__main__":
    asyncio.run(main())
