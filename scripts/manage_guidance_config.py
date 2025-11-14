# -*- coding-utf-8 -*-

import asyncio
import argparse
import sys
import os
import logging
from typing import List, Dict, Any

# --- 设置项目根路径 ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- 加载环境变量 ---
from dotenv import load_dotenv

load_dotenv()

import discord
from src.guidance.utils.database import guidance_db_manager as db_manager

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
client = discord.Client(intents=intents)


def print_table(headers: List[str], data: List[Dict[str, Any]]):
    """格式化并打印表格数据。"""
    if not data:
        log.info("没有找到任何数据。")
        return

    # 计算每列的最大宽度
    widths = {key: len(str(key)) for key in headers}
    for row in data:
        for key in headers:
            # 确保键存在
            if key in row:
                widths[key] = max(widths.get(key, 0), len(str(row.get(key, ""))))

    # 打印表头
    header_line = " | ".join(f"{h:<{widths.get(h, len(h))}}" for h in headers)
    print("\n" + header_line)
    print("-" * len(header_line))

    # 打印数据行
    for row in data:
        data_line = " | ".join(
            f"{str(row.get(h, 'N/A')):<{widths.get(h, len(str(row.get(h, 'N/A'))))}}"
            for h in headers
        )
        print(data_line)
    print("\n")


async def list_channels(guild_id: int):
    """列出指定服务器的所有频道消息配置，并附带详细信息。"""
    log.info(f"--- 正在获取服务器 {guild_id} 的所有频道配置 ---")

    try:
        guild = await client.fetch_guild(guild_id)
        log.info(f"成功连接到服务器: {guild.name}")
        log.info("正在获取服务器的所有频道信息...")
        await guild.fetch_channels()  # 主动获取所有频道来填充缓存
        log.info("频道信息获取完毕。")
    except (discord.NotFound, discord.Forbidden):
        log.error(
            f"无法获取服务器 {guild_id}。请检查机器人是否在该服务器中以及是否有权限。"
        )
        return

    all_configs = await db_manager.get_all_channel_messages(guild.id)

    if not all_configs:
        log.info("该服务器没有任何频道配置。")
        return

    headers = ["Channel ID", "Channel Name", "Status", "Panel Footer"]
    table_data = []
    for config in all_configs:
        channel_id = config.get("channel_id")
        channel = guild.get_channel(channel_id)
        channel_name = f"#{channel.name}" if channel else f"ID: {channel_id} (Unknown)"

        # 如果 get_channel 失败，尝试强制 fetch
        if not channel:
            try:
                channel = await guild.fetch_channel(channel_id)
                channel_name = f"#{channel.name}"
            except (discord.NotFound, discord.Forbidden):
                channel_name = f"ID: {channel_id} (Not Found/No Access)"

        status = (
            "✅ Deployed" if config.get("deployed_message_id") else "❌ Not Deployed"
        )

        panel_footer = "N/A"

        if config.get("permanent_message_data"):
            perm_data = config.get("permanent_message_data", {})
            panel_footer = perm_data.get("footer_text", "No Footer")
        else:
            status = "⚠️ No Panel Config"

        table_data.append(
            {
                "Channel ID": channel_id,
                "Channel Name": channel_name,
                "Status": status,
                "Panel Footer": panel_footer,
            }
        )

    print_table(headers, table_data)


async def delete_channel(channel_id: int):
    """从数据库中删除一个频道的配置。"""
    log.info(f"--- 准备删除频道 {channel_id} 的配置 ---")

    existing_config = await db_manager.get_channel_message(channel_id)
    if not existing_config:
        log.error(f"错误：在数据库中找不到频道 {channel_id} 的配置。")
        return

    await db_manager.remove_channel_message(channel_id)
    log.info(f"✅ 成功从数据库中删除了频道 {channel_id} 的所有相关配置。")
    log.warning("请注意：此操作不会删除Discord频道本身或频道内的任何消息。")


async def main():
    parser = argparse.ArgumentParser(description="管理引导系统的数据库配置。")
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用的命令")

    parser_list = subparsers.add_parser("list", help="列出数据库中的配置信息。")
    parser_list.add_argument(
        "--channels", action="store_true", help="列出所有已配置的频道。"
    )
    parser_list.add_argument(
        "--guild-id", type=int, required=True, help="要操作的服务器ID。"
    )

    parser_delete = subparsers.add_parser("delete", help="从数据库中删除配置信息。")
    parser_delete.add_argument(
        "--channel", type=int, required=True, help="删除指定频道ID的配置。"
    )

    args = parser.parse_args()

    bot_token = os.getenv("DISCORD_TOKEN")
    if not bot_token:
        log.error("错误：未在 .env 文件或环境变量中找到 DISCORD_TOKEN。")
        return

    await db_manager.init_async()

    try:
        if args.command == "list" and not args.channels:
            parser_list.print_help()
            return

        if args.command == "delete" and not args.channel:
            parser_delete.print_help()
            return

        # 对于需要连接Discord的操作，进行登录
        if args.command == "list" and args.channels:
            log.info("正在登录到 Discord...")
            await client.login(bot_token)
            await list_channels(args.guild_id)
        elif args.command == "delete":
            await delete_channel(args.channel)

    except discord.LoginFailure:
        log.error("Discord 登录失败，请检查你的 DISCORD_TOKEN 是否正确。")
    except Exception as e:
        log.error(f"发生未知错误: {e}", exc_info=True)
    finally:
        if client.is_ready():
            await client.close()
        await db_manager.close()
        log.info("数据库和Discord连接已关闭。")


if __name__ == "__main__":
    asyncio.run(main())
