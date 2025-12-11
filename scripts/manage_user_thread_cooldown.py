import asyncio
import argparse
import os
import sys
from typing import Optional
import discord
from dotenv import load_dotenv

# --- 路径设置，确保能导入项目模块 ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.chat.utils.database import ChatDatabaseManager

# --- 全局变量 ---
# 加载 .env 文件中的环境变量
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")


async def find_thread_owner(thread_id: int, guild_id_override: Optional[int] = None):
    """
    连接到 Discord 并查找指定帖子的创建者。
    """
    if not DISCORD_TOKEN:
        print("❌ 错误：请确保 .env 文件中已配置 DISCORD_TOKEN。")
        return

    # 决定使用哪个 Guild ID
    target_guild_id_str = None
    if guild_id_override:
        target_guild_id_str = str(guild_id_override)
        print(f"ℹ️ 已通过命令行参数指定服务器 ID: {target_guild_id_str}")
    elif GUILD_ID:
        # 如果环境变量包含多个ID，取第一个
        if "," in GUILD_ID:
            first_id = GUILD_ID.split(",")[0].strip()
            print(
                f"⚠️ 检测到 .env 文件中的 GUILD_ID 包含多个值。将自动使用第一个 ID: {first_id}"
            )
            target_guild_id_str = first_id
        else:
            target_guild_id_str = GUILD_ID
            print(f"ℹ️ 将使用 .env 文件中配置的服务器 ID: {target_guild_id_str}")

    if not target_guild_id_str:
        print(
            "❌ 错误：必须提供服务器 ID。请在 .env 文件中设置 GUILD_ID 或使用 --guild_id 参数。"
        )
        return

    intents = discord.Intents.default()
    intents.guilds = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"✅ 以 {client.user} 的身份成功连接到 Discord。")
        guild = None
        try:
            guild = client.get_guild(int(target_guild_id_str))
            if not guild:
                print(
                    f"❌ 错误：找不到服务器 ID: {target_guild_id_str}。请检查提供的 ID 是否正确。"
                )
                return

            print(f"🔍 正在服务器 '{guild.name}' 中查找帖子 ID: {thread_id}...")
            thread = await guild.fetch_channel(thread_id)

            if isinstance(thread, discord.Thread):
                print("\n-------------------------------------------")
                print("🎉 查找成功！")
                print(f"  帖子名称: {thread.name}")
                print(f"  帖子ID:   {thread.id}")
                print(f"  创建者ID: {thread.owner_id}")
                print("-------------------------------------------\n")
                print("下一步：请使用 'set-cooldown' 命令和上面的创建者ID来设置冷却。")
            else:
                print(
                    f"❌ 错误：找到的实体是一个 '{type(thread).__name__}'，而不是一个帖子。"
                )

        except discord.errors.NotFound:
            print(
                f"❌ 错误：在服务器 {target_guild_id_str} 中找不到 ID 为 {thread_id} 的频道或帖子。"
            )
        except discord.errors.Forbidden:
            # 安全地访问 guild.name
            guild_name = guild.name if guild else "未知"
            print(
                f"❌ 错误：机器人权限不足，无法获取频道信息。请检查机器人在服务器 '{guild_name}' 的权限设置。"
            )
        except Exception as e:
            print(f"❌ 发生未知错误: {e}")
        finally:
            await client.close()
            print("Discord 连接已关闭。")

    try:
        await client.start(DISCORD_TOKEN)
    except discord.errors.LoginFailure:
        print(
            "❌ 错误：机器人 TOKEN 无效，登录失败。请检查 .env 文件中的 DISCORD_TOKEN。"
        )


async def set_user_cooldown(
    user_id: int,
    cooldown_seconds: Optional[int],
    cooldown_duration: Optional[int],
    cooldown_limit: Optional[int],
):
    """
    为指定用户设置全局的帖子冷却时间。
    """
    # 验证CD模式
    is_simple_cooldown = cooldown_seconds is not None
    is_rate_limit = cooldown_duration is not None and cooldown_limit is not None

    if is_simple_cooldown and is_rate_limit:
        print("❌ 错误：不能同时设置两种冷却模式。请只选择一种。")
        return
    if not is_simple_cooldown and not is_rate_limit:
        print("❌ 错误：必须提供一种冷却模式的参数。")
        print("  模式1 (简单冷却): --cooldown_seconds <秒数>")
        print(
            "  模式2 (频率限制): --cooldown_duration <秒数> --cooldown_limit <消息数>"
        )
        return

    print("- 正在连接到数据库...")
    db_manager = ChatDatabaseManager()
    await db_manager.init_async()

    settings = {
        "cooldown_seconds": cooldown_seconds,
        "cooldown_duration": cooldown_duration,
        "cooldown_limit": cooldown_limit,
    }

    try:
        await db_manager.update_user_thread_cooldown_settings(user_id, settings)
        print("\n-------------------------------------------")
        print("✅ 操作成功！")
        print(f"  用户ID (User ID): {user_id}")
        if is_simple_cooldown:
            print("  冷却模式:         简单冷却")
            print(f"  冷却时间:         {cooldown_seconds} 秒")
        if is_rate_limit:
            print("  冷却模式:         频率限制")
            print(
                f"  设置:             {cooldown_limit} 条消息 / {cooldown_duration} 秒"
            )
        print("-------------------------------------------\n")
        print("该设置将应用于此用户未来创建的所有新帖子。")

    except Exception as e:
        print(f"❌ 操作失败：在更新数据库时发生错误: {e}")
    finally:
        await db_manager.disconnect()
        print("数据库连接已关闭。")


def main():
    parser = argparse.ArgumentParser(
        description="管理用户的个人帖子默认冷却设置。",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="可用的命令")

    # --- 查找帖主命令 ---
    parser_find = subparsers.add_parser(
        "find-owner",
        help="根据帖子ID查找其创建者的用户ID。",
        description="连接到Discord并查找指定帖子的创建者ID。",
    )
    parser_find.add_argument("thread_id", type=int, help="要查询的帖子 (Thread) 的ID。")
    parser_find.add_argument(
        "--guild_id",
        type=int,
        help="可选：指定在哪个服务器 (Guild) 中进行搜索。如果 .env 文件中有多个ID，建议使用此参数。",
    )

    # --- 设置CD命令 ---
    parser_set = subparsers.add_parser(
        "set-cooldown",
        help="为指定的用户ID设置全局的帖子冷却规则。",
        description="为指定的用户ID设置其未来所有帖子的默认冷却规则。\n"
        "提供两种冷却模式：\n"
        "1. 简单冷却：在指定秒数内只能发一条消息。\n"
        "2. 频率限制：在指定时间内不能超过最大消息数。",
    )
    parser_set.add_argument("user_id", type=int, help="要设置冷却规则的用户ID。")
    parser_set.add_argument(
        "--cooldown_seconds", type=int, help="简单冷却模式的秒数 (例如: 30)。"
    )
    parser_set.add_argument(
        "--cooldown_duration",
        type=int,
        help="频率限制模式的时间窗口（秒） (例如: 60)。",
    )
    parser_set.add_argument(
        "--cooldown_limit", type=int, help="在时间窗口内允许的最大消息数量 (例如: 15)。"
    )

    args = parser.parse_args()

    if args.command == "find-owner":
        asyncio.run(find_thread_owner(args.thread_id, args.guild_id))
    elif args.command == "set-cooldown":
        asyncio.run(
            set_user_cooldown(
                args.user_id,
                args.cooldown_seconds,
                args.cooldown_duration,
                args.cooldown_limit,
            )
        )


if __name__ == "__main__":
    main()
