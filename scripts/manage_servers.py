import discord
import os
import asyncio
import argparse
from dotenv import load_dotenv

# --- 配置区 ---
# 加载 .env 文件中的环境变量
load_dotenv()

# 从环境变量中获取机器人令牌
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

# 在退出服务器前发送的消息。留空字符串 ("") 则不发送任何消息。
LEAVE_MESSAGE = ""
# --- 配置区结束 ---


class ManagementBot(discord.Client):
    def __init__(self, mode, whitelist_ids=None, **options):
        super().__init__(**options)
        self.mode = mode
        self.whitelist = [str(gid) for gid in whitelist_ids] if whitelist_ids else []

    async def on_ready(self):
        print(f"以 {self.user} 的身份登录成功！")
        print("-" * 30)

        if self.mode == "list":
            await self.list_servers()
        elif self.mode == "prune":
            await self.prune_servers()

        await self.close()

    async def list_servers(self):
        print("机器人当前所在的服务器列表:")
        if not self.guilds:
            print("机器人目前不在任何服务器中。")
            return

        for guild in self.guilds:
            print(f"- 服务器名称: {guild.name}, ID: {guild.id}")
        print("-" * 30)
        print("列表显示完毕。")

    async def prune_servers(self):
        if not self.whitelist:
            print("错误：清理模式需要提供至少一个服务器ID作为白名单。")
            print("用法: python scripts/manage_servers.py --prune <ID1> <ID2> ...")
            return

        print(f"白名单已设置，将保留以下服务器: {', '.join(self.whitelist)}")

        guilds_to_leave = [g for g in self.guilds if str(g.id) not in self.whitelist]

        if not guilds_to_leave:
            print("所有当前所在的服务器都在白名单上，无需执行任何操作。")
            return

        print("-" * 30)
        print("以下服务器将被移除:")
        for guild in guilds_to_leave:
            print(f"- 服务器名称: {guild.name}, ID: {guild.id}")
        print("-" * 30)

        confirm = input(
            f"你确定要让机器人退出这 {len(guilds_to_leave)} 个服务器吗? (输入 'yes' 以确认): "
        )
        if confirm.lower() != "yes":
            print("操作已取消。")
            return

        print("开始执行退出操作...")
        for guild in guilds_to_leave:
            # 在退出前发送消息
            if LEAVE_MESSAGE:
                target_channel = guild.system_channel
                # 如果没有系统频道，则寻找第一个能发言的文字频道
                if not target_channel:
                    for channel in guild.text_channels:
                        if channel.permissions_for(guild.me).send_messages:
                            target_channel = channel
                            break

                if target_channel:
                    try:
                        await target_channel.send(LEAVE_MESSAGE)
                        print(f"向服务器 '{guild.name}' 发送了告别消息。")
                        await asyncio.sleep(1)  # 短暂延迟以确保消息发送
                    except discord.Forbidden:
                        print(f"在服务器 '{guild.name}' 中没有发送消息的权限，已跳过。")
                    except Exception as e:
                        print(f"向服务器 '{guild.name}' 发送消息时出错: {e}")
                else:
                    print(
                        f"在服务器 '{guild.name}' 中找不到可以发送消息的频道，已跳过。"
                    )

            # 退出服务器
            try:
                await guild.leave()
                print(f"成功退出服务器: {guild.name} ({guild.id})")
            except Exception as e:
                print(f"退出服务器 {guild.name} ({guild.id}) 时发生错误: {e}")

        print("-" * 30)
        print("清理操作执行完毕。")


async def main():
    parser = argparse.ArgumentParser(description="管理 Discord 机器人所在的服务器。")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--list", action="store_true", help="仅列出机器人所在的所有服务器。"
    )
    group.add_argument(
        "--prune",
        nargs="+",
        metavar="SERVER_ID",
        help="退出所有不在提供的白名单ID列表中的服务器。",
    )

    args = parser.parse_args()

    if not BOT_TOKEN:
        print("错误：在 .env 文件中未找到 DISCORD_TOKEN。")
        print(
            "请确保你的 .env 文件在项目根目录，并且其中包含一行 'DISCORD_TOKEN=你的令牌'。"
        )
        return

    intents = discord.Intents.default()
    intents.guilds = True

    mode = "list" if args.list else "prune"

    client = ManagementBot(mode=mode, whitelist_ids=args.prune, intents=intents)

    try:
        await client.start(BOT_TOKEN)
    except discord.LoginFailure:
        print("错误：机器人令牌无效。请检查你的令牌是否正确。")


if __name__ == "__main__":
    asyncio.run(main())
