#!/usr/bin/env python3
"""
管理类脑娘频道配置的脚本（交互式版本）

用法：
    # 列出服务器的所有频道配置
    python scripts/manage_channel_config.py --list <GUILD_ID>

    # 修改特定频道的配置（交互式）
    python scripts/manage_channel_config.py <GUILD_ID> <CHANNEL_ID>
"""

import discord
import os
import asyncio
import argparse
from dotenv import load_dotenv
import sys

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.chat.utils.database import ChatDatabaseManager

# 加载环境变量
load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_TOKEN")


class ChannelConfigBot(discord.Client):
    def __init__(self, mode, guild_id, channel_id=None, **options):
        super().__init__(**options)
        self.mode = mode
        self.guild_id = int(guild_id)
        self.channel_id = int(channel_id) if channel_id else None
        self.db_manager: ChatDatabaseManager | None = None

    async def on_ready(self):
        print(f"\n以 {self.user} 的身份登录成功！")
        print("-" * 50)

        # 初始化数据库管理器
        self.db_manager = ChatDatabaseManager()
        await self.db_manager.init_async()

        try:
            if self.mode == "list":
                await self.list_guild_configs()
            elif self.mode == "modify":
                await self.run_interactive_config()
        finally:
            await self.close()

    def get_guild(self):
        """获取指定的服务器"""
        return discord.utils.get(self.guilds, id=self.guild_id)

    async def list_guild_configs(self):
        """列出服务器的所有频道配置"""
        assert self.db_manager is not None, "Database manager not initialized"

        guild = self.get_guild()
        if not guild:
            print(f"错误：找不到服务器 ID {self.guild_id}")
            print("可用的服务器：")
            for g in self.guilds:
                print(f"  - {g.name} (ID: {g.id})")
            return

        print(f"\n服务器: {guild.name} (ID: {guild.id})")
        print("=" * 60)

        # 获取全局配置
        global_config = await self.db_manager.get_global_chat_config(self.guild_id)
        print("\n【全局配置】")
        if global_config:
            print(f"  聊天启用: {'✓' if global_config['chat_enabled'] else '✗'}")
            print(f"  暖贴启用: {'✓' if global_config['warm_up_enabled'] else '✗'}")
        else:
            print("  使用默认配置（聊天启用，暖贴启用）")

        # 获取所有频道配置
        channel_configs = await self.db_manager.get_all_channel_configs_for_guild(
            self.guild_id
        )

        if not channel_configs:
            print("\n【频道/分类配置】")
            print("  未设置任何特定频道配置")
            print("\n" + "=" * 60)
            return

        print("\n【频道/分类配置】")
        for config in channel_configs:
            entity_id = config["entity_id"]
            entity_type = config["entity_type"]

            # 获取频道/分类名称
            if entity_type == "channel":
                channel = guild.get_channel(entity_id)
                name = channel.name if channel else f"未知频道 (ID: {entity_id})"
                prefix = "#"
            else:  # category
                category = discord.utils.get(guild.categories, id=entity_id)
                name = category.name if category else f"未知分类 (ID: {entity_id})"
                prefix = "📁 "

            print(f"\n  [{entity_type.upper()}] {prefix}{name} (ID: {entity_id})")
            print(
                f"    聊天: {'✓' if config['is_chat_enabled'] else '✗' if config['is_chat_enabled'] is not None else '（继承）'}"
            )

            # 显示冷却设置
            cd_seconds = config["cooldown_seconds"]
            cd_duration = config["cooldown_duration"]
            cd_limit = config["cooldown_limit"]

            if cd_seconds is not None and cd_seconds > 0:
                print(f"    冷却: 固定 {cd_seconds}秒")
            elif (
                cd_duration is not None
                and cd_limit is not None
                and cd_duration > 0
                and cd_limit > 0
            ):
                print(f"    冷却: 频率限制 ({cd_duration}秒内最多{cd_limit}条)")
            else:
                print("    冷却: 无限制")

        print("\n" + "=" * 60)
        print(f"共 {len(channel_configs)} 个配置项")

    async def run_interactive_config(self):
        """运行交互式配置界面"""
        assert self.db_manager is not None, "Database manager not initialized"

        if self.channel_id is None:
            print("错误：未指定频道 ID")
            return

        guild = self.get_guild()
        if not guild:
            print(f"错误：找不到服务器 ID {self.guild_id}")
            print("可用的服务器：")
            for g in self.guilds:
                print(f"  - {g.name} (ID: {g.id})")
            return

        assert self.channel_id is not None, "Channel ID must be set in modify mode"

        channel = guild.get_channel(self.channel_id)
        if not channel:
            print(f"错误：在服务器中找不到频道 ID {self.channel_id}")
            print("\n可用的频道：")
            for ch in guild.text_channels:
                print(f"  - #{ch.name} (ID: {ch.id})")
            return

        print(f"\n当前频道: #{channel.name} (ID: {channel.id})")
        print(f"所属服务器: {guild.name} (ID: {guild.id})")
        print("=" * 50)

        # 获取当前配置
        current_config = await self.db_manager.get_channel_config(
            self.guild_id, self.channel_id
        )

        # 显示当前配置
        print("\n【当前配置】")
        if current_config:
            is_enabled = current_config["is_chat_enabled"]
            cd_seconds = current_config["cooldown_seconds"]
            cd_duration = current_config["cooldown_duration"]
            cd_limit = current_config["cooldown_limit"]

            print(
                f"  聊天功能: {'启用' if is_enabled else '禁用' if is_enabled is not None else '（继承）'}"
            )

            if cd_seconds is not None and cd_seconds > 0:
                print("  冷却模式: 固定时长")
                print(f"  冷却时间: {cd_seconds} 秒")
            elif (
                cd_duration is not None
                and cd_limit is not None
                and cd_duration > 0
                and cd_limit > 0
            ):
                print("  冷却模式: 频率限制")
                print("  时间窗口: {cd_duration} 秒")
                print("  消息限制: {cd_limit} 条")
            else:
                print("  冷却设置: 无限制")
        else:
            print("  未设置特定配置，使用默认设置")

        print("\n" + "=" * 50)

        # 交互式菜单
        while True:
            print("\n【配置选项】")
            print("1. 启用/禁用聊天功能")
            print("2. 设置固定冷却模式")
            print("3. 设置频率限制模式")
            print("4. 清除冷却设置")
            print("5. 查看当前配置")
            print("0. 退出")

            choice = input("\n请选择操作 (0-5): ").strip()

            if choice == "0":
                print("\n退出配置...")
                break
            elif choice == "1":
                await self.toggle_chat_enabled(channel)
            elif choice == "2":
                await self.set_fixed_cooldown(channel)
            elif choice == "3":
                await self.set_rate_limit(channel)
            elif choice == "4":
                await self.clear_cooldown(channel)
            elif choice == "5":
                # 重新获取并显示配置
                current_config = await self.db_manager.get_channel_config(
                    self.guild_id, self.channel_id
                )
                print("\n【当前配置】")
                if current_config:
                    is_enabled = current_config["is_chat_enabled"]
                    cd_seconds = current_config["cooldown_seconds"]
                    cd_duration = current_config["cooldown_duration"]
                    cd_limit = current_config["cooldown_limit"]

                    print(
                        f"  聊天功能: {'启用' if is_enabled else '禁用' if is_enabled is not None else '（继承）'}"
                    )

                    if cd_seconds is not None and cd_seconds > 0:
                        print("  冷却模式: 固定时长")
                        print(f"  冷却时间: {cd_seconds} 秒")
                    elif (
                        cd_duration is not None
                        and cd_limit is not None
                        and cd_duration > 0
                        and cd_limit > 0
                    ):
                        print("  冷却模式: 频率限制")
                        print(f"  时间窗口: {cd_duration} 秒")
                        print(f"  消息限制: {cd_limit} 条")
                    else:
                        print("  冷却设置: 无限制")
                else:
                    print("  未设置特定配置，使用默认设置")
            else:
                print("无效的选择，请重新输入。")

    async def toggle_chat_enabled(self, channel):
        """启用/禁用聊天功能"""
        assert self.db_manager is not None, "Database manager not initialized"
        assert self.channel_id is not None, "Channel ID must be set in modify mode"

        print("\n【启用/禁用聊天功能】")
        print("1. 启用")
        print("2. 禁用")
        print("3. 继承（清除设置）")

        choice = input("请选择 (1-3): ").strip()

        is_chat_enabled = None
        if choice == "1":
            is_chat_enabled = True
            print(f"\n✓ 频道 #{channel.name} 的聊天功能已启用")
        elif choice == "2":
            is_chat_enabled = False
            print(f"\n✓ 频道 #{channel.name} 的聊天功能已禁用")
        elif choice == "3":
            is_chat_enabled = None
            print(f"\n✓ 频道 #{channel.name} 的聊天功能设置为继承")
        else:
            print("无效的选择")
            return

        # 获取当前配置
        current_config = await self.db_manager.get_channel_config(
            self.guild_id, self.channel_id
        )

        # 保存配置
        await self.db_manager.update_channel_config(
            guild_id=self.guild_id,
            entity_id=self.channel_id,
            entity_type="channel",
            is_chat_enabled=is_chat_enabled,
            cooldown_seconds=current_config["cooldown_seconds"]
            if current_config
            else None,
            cooldown_duration=current_config["cooldown_duration"]
            if current_config
            else None,
            cooldown_limit=current_config["cooldown_limit"] if current_config else None,
        )

    async def set_fixed_cooldown(self, channel):
        """设置固定冷却模式"""
        assert self.db_manager is not None, "Database manager not initialized"
        assert self.channel_id is not None, "Channel ID must be set in modify mode"

        print("\n【设置固定冷却模式】")
        print("说明：用户两次消息之间需要等待的最小时间间隔")

        while True:
            seconds = input("请输入冷却时间（秒）: ").strip()
            try:
                seconds = int(seconds)
                if seconds < 0:
                    print("冷却时间不能为负数，请重新输入")
                    continue
                break
            except ValueError:
                print("请输入有效的数字")

        # 获取当前配置以保留其他设置
        current_config = await self.db_manager.get_channel_config(
            self.guild_id, self.channel_id
        )

        # 保存配置（保留现有设置）
        await self.db_manager.update_channel_config(
            guild_id=self.guild_id,
            entity_id=self.channel_id,
            entity_type="channel",
            is_chat_enabled=current_config["is_chat_enabled"]
            if current_config
            else None,
            cooldown_seconds=seconds,
            cooldown_duration=None,
            cooldown_limit=None,
        )

        print(f"\n✓ 频道 #{channel.name} 的固定冷却已设置为 {seconds} 秒")

    async def set_rate_limit(self, channel):
        """设置频率限制模式"""
        assert self.db_manager is not None, "Database manager not initialized"
        assert self.channel_id is not None, "Channel ID must be set in modify mode"

        print("\n【设置频率限制模式】")
        print("说明：在指定时间窗口内，用户最多可以发送多少条消息")

        while True:
            duration = input("请输入时间窗口（秒）: ").strip()
            try:
                duration = int(duration)
                if duration <= 0:
                    print("时间窗口必须大于0，请重新输入")
                    continue
                break
            except ValueError:
                print("请输入有效的数字")

        while True:
            limit = input("请输入消息数量限制: ").strip()
            try:
                limit = int(limit)
                if limit <= 0:
                    print("消息数量必须大于0，请重新输入")
                    continue
                break
            except ValueError:
                print("请输入有效的数字")

        # 获取当前配置以保留其他设置
        current_config = await self.db_manager.get_channel_config(
            self.guild_id, self.channel_id
        )

        # 保存配置（保留现有设置）
        await self.db_manager.update_channel_config(
            guild_id=self.guild_id,
            entity_id=self.channel_id,
            entity_type="channel",
            is_chat_enabled=current_config["is_chat_enabled"]
            if current_config
            else None,
            cooldown_seconds=0,
            cooldown_duration=duration,
            cooldown_limit=limit,
        )

        print(
            f"\n✓ 频道 #{channel.name} 的频率限制已设置为：{duration}秒内最多{limit}条消息"
        )

    async def clear_cooldown(self, channel):
        """清除冷却设置"""
        assert self.db_manager is not None, "Database manager not initialized"
        assert self.channel_id is not None, "Channel ID must be set in modify mode"

        print("\n【清除冷却设置】")

        confirm = (
            input(f"确认清除频道 #{channel.name} 的冷却设置？(y/n): ").strip().lower()
        )
        if confirm != "y":
            print("已取消")
            return

        # 获取当前配置
        current_config = await self.db_manager.get_channel_config(
            self.guild_id, self.channel_id
        )

        # 保存配置（清除冷却）
        await self.db_manager.update_channel_config(
            guild_id=self.guild_id,
            entity_id=self.channel_id,
            entity_type="channel",
            is_chat_enabled=current_config["is_chat_enabled"]
            if current_config
            else None,
            cooldown_seconds=0,
            cooldown_duration=None,
            cooldown_limit=None,
        )

        print(f"\n✓ 频道 #{channel.name} 的冷却设置已清除")


async def main():
    parser = argparse.ArgumentParser(
        description="管理类脑娘频道配置",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 列出服务器的所有频道配置
  python scripts/manage_channel_config.py --list 123456789

  # 修改特定频道的配置（交互式）
  python scripts/manage_channel_config.py 123456789 987654321
        """,
    )

    parser.add_argument(
        "--list",
        metavar="GUILD_ID",
        help="列出指定服务器的所有频道配置",
    )
    parser.add_argument(
        "guild_id",
        nargs="?",
        metavar="GUILD_ID",
        help="服务器ID（修改模式必需）",
    )
    parser.add_argument(
        "channel_id",
        nargs="?",
        metavar="CHANNEL_ID",
        help="频道ID（修改模式可选）",
    )

    args = parser.parse_args()

    # 处理参数
    if args.list:
        # 列表模式
        guild_id = args.list
        channel_id = None
        mode = "list"
    else:
        # 修改模式
        if not args.guild_id:
            print("错误：修改模式需要 GUILD_ID")
            print(
                "用法: python scripts/manage_channel_config.py <GUILD_ID> [CHANNEL_ID]"
            )
            print("       python scripts/manage_channel_config.py --list <GUILD_ID>")
            sys.exit(1)
        guild_id = args.guild_id
        channel_id = args.channel_id
        mode = "modify"

    if not BOT_TOKEN:
        print("错误：在 .env 文件中未找到 DISCORD_TOKEN")
        print("请确保 .env 文件在项目根目录，并且包含 'DISCORD_TOKEN=你的令牌'")
        sys.exit(1)

    intents = discord.Intents.default()
    intents.guilds = True
    intents.message_content = True

    client = ChannelConfigBot(
        mode=mode, guild_id=guild_id, channel_id=channel_id, intents=intents
    )

    try:
        await client.start(BOT_TOKEN)
    except discord.LoginFailure:
        print("错误：机器人令牌无效，请检查令牌是否正确")
    except KeyboardInterrupt:
        print("\n操作已取消")


if __name__ == "__main__":
    asyncio.run(main())
