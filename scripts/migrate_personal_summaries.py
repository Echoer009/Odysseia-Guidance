# -*- coding: utf-8 -*-

import asyncio
import logging
import sys
import argparse
import os
import aiohttp

# --- 修正 sys.path ---
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

# --- 配置日志 ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- 导入项目模块 ---
from sqlalchemy.future import select
from src.database.database import AsyncSessionLocal
from src.chat.utils.database import chat_db_manager
from src.database.models import CommunityMemberProfile

# --- Discord API 配置 ---
DISCORD_API_BASE_URL = "https://discord.com/api/v10"


async def get_users_with_summaries():
    """从 SQLite 获取所有拥有记忆摘要的用户信息。"""
    logging.info("从 SQLite 读取所有用户的详细信息...")
    query = "SELECT * FROM users WHERE personal_summary IS NOT NULL AND personal_summary != ''"
    return await chat_db_manager._execute(
        chat_db_manager._db_transaction, query, (), fetch="all"
    )


async def find_missing_profiles(sqlite_users):
    """找出在 ParadeDB 中不存在档案的用户。"""
    missing_users = []
    async with AsyncSessionLocal() as session:
        for user in sqlite_users:
            user_id = str(user["user_id"])
            stmt = select(CommunityMemberProfile).where(
                CommunityMemberProfile.discord_id == user_id
            )
            result = await session.execute(stmt)
            if not result.scalars().first():
                missing_users.append(user)
    return missing_users


async def get_user_display_name(user_id: str, guild_id: str, bot_token: str) -> str:
    """
    通过 Discord API 获取用户在特定服务器上的显示昵称。
    如果获取失败或用户不在服务器上，则回退到获取全局用户名。
    """
    headers = {"Authorization": f"Bot {bot_token}"}
    # 优先尝试获取服务器成员信息
    member_url = f"{DISCORD_API_BASE_URL}/guilds/{guild_id}/members/{user_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(member_url, headers=headers) as response:
            if response.status == 200:
                member_data = await response.json()
                # display_name 会优先使用服务器昵称(nick)，否则回退到全局名
                # 优先使用服务器昵称，其次是全局显示名，最后才是全局用户名
                nick = member_data.get("nick")
                user_info = member_data.get("user", {})
                global_name = user_info.get("global_name")
                username = user_info.get("username")

                display_name = nick or global_name or username
                if display_name:
                    return display_name

    # 如果无法获取成员信息（例如用户已离开服务器），则回退到获取全局用户信息
    user_url = f"{DISCORD_API_BASE_URL}/users/{user_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(user_url, headers=headers) as response:
            if response.status == 200:
                user_data = await response.json()
                return user_data.get("username", "未知用户")
            else:
                logging.error(
                    f"无法从 Discord API 获取用户 {user_id} 的信息, 状态码: {response.status}"
                )
                return "未知用户"


async def run_check_mode(sqlite_users):
    """执行检查模式，并返回缺失档案的数量。"""
    logging.info("--- 运行模式: 检查 (Check) ---")
    missing_profiles = await find_missing_profiles(sqlite_users)

    if not missing_profiles:
        logging.info("恭喜！所有在 SQLite 中有记忆的用户在 ParadeDB 中都有对应的档案。")
    else:
        logging.warning(f"发现 {len(missing_profiles)} 个有记忆但无档案的用户:")
        for user in missing_profiles:
            logging.warning(f"  - 用户信息 (来自 SQLite): {dict(user)}")

    return len(missing_profiles)


async def run_repair_mode(sqlite_users, guild_id: str, bot_token: str):
    """执行修复模式，并返回缺失和修复的数量。"""
    logging.info("--- 运行模式: 修复 (Repair) ---")
    missing_profiles = await find_missing_profiles(sqlite_users)
    missing_count = len(missing_profiles)

    if not missing_profiles:
        logging.info("无需修复，所有用户档案均存在。")
        return missing_count, 0

    logging.info(f"开始为 {missing_count} 个缺失档案的用户进行修复...")
    repaired_count = 0
    async with AsyncSessionLocal() as session:
        for user in missing_profiles:
            user_id = str(user["user_id"])
            display_name = await get_user_display_name(user_id, guild_id, bot_token)

            # 创建新的个人档案
            new_profile = CommunityMemberProfile(
                discord_id=user_id,
                external_id=user_id,  # 使用 discord_id 作为外部ID
                title=display_name,
                full_text="""- background: 默认
- attitude: 默认
- notes: 该用户档案由迁移脚本自动生成。""",
                source_metadata={"source": "repair_script"},
                personal_summary=user["personal_summary"],
            )
            session.add(new_profile)
            await session.commit()
            logging.info(
                f"成功为用户 '{display_name}' (ID: {user_id}) 创建了新的档案。"
            )
            repaired_count += 1

    return missing_count, repaired_count


async def run_migrate_mode(sqlite_users):
    """执行迁移模式，并返回迁移和跳过的数量。"""
    logging.info("--- 运行模式: 迁移 (Migrate) ---")
    migrated_count = 0
    skipped_count = 0
    async with AsyncSessionLocal() as session:
        for user in sqlite_users:
            user_id = str(user["user_id"])
            personal_summary = user["personal_summary"]

            stmt = select(CommunityMemberProfile).where(
                CommunityMemberProfile.discord_id == user_id
            )
            result = await session.execute(stmt)
            profile = result.scalars().first()

            if profile:
                # 检查是否已有摘要，避免重复写入（虽然无害但可以更高效）
                if profile.personal_summary != personal_summary:
                    profile.personal_summary = personal_summary
                    session.add(profile)
                    await session.commit()
                    logging.info(f"成功为用户 ID {user_id} 更新了个人记忆摘要。")
                else:
                    logging.info(f"用户 ID {user_id} 的记忆摘要已是最新，无需更新。")
                migrated_count += 1
            else:
                logging.warning(
                    f"用户 ID {user_id} 在 ParadeDB 中无档案，跳过迁移。请先运行 'check' 或 'repair' 模式。"
                )
                skipped_count += 1

    return migrated_count, skipped_count


# --- 全局报告变量 ---
report_stats = {
    "total_users_with_summaries": 0,
    "missing_profiles_found": 0,
    "repaired_profiles": 0,
    "migrated_summaries": 0,
    "skipped_migrations": 0,
}


def print_final_report(mode: str):
    """打印格式化的最终报告。"""
    print("\n" + "=" * 50)
    print(" 脚本执行摘要报告")
    print("=" * 50)
    print(f"执行模式: {mode.upper()}")
    print("-" * 50)
    print(f"拥有记忆的用户总数: {report_stats['total_users_with_summaries']}")
    if mode in ["check", "repair"]:
        print(f"发现缺失的档案数: {report_stats['missing_profiles_found']}")
    if mode == "repair":
        print(f"成功修复的档案数: {report_stats['repaired_profiles']}")
    if mode == "migrate":
        print(f"成功迁移的记忆数: {report_stats['migrated_summaries']}")
        print(f"因档案缺失而跳过的数量: {report_stats['skipped_migrations']}")
    print("=" * 50 + "\n")


async def main(args):
    """主函数，根据参数选择执行模式。"""

    # 在所有模式开始前，先获取基础数据
    sqlite_users = await get_users_with_summaries()
    if not sqlite_users:
        logging.info("在 SQLite 中没有找到任何拥有记忆摘要的用户。脚本执行结束。")
        return
    report_stats["total_users_with_summaries"] = len(sqlite_users)

    if args.mode == "check":
        missing_count = await run_check_mode(sqlite_users)
        report_stats["missing_profiles_found"] = missing_count
    elif args.mode == "repair":
        bot_token = os.getenv("DISCORD_TOKEN")
        if bot_token and args.guild_id:
            missing_count, repaired_count = await run_repair_mode(
                sqlite_users, args.guild_id, bot_token
            )
            report_stats["missing_profiles_found"] = missing_count
            report_stats["repaired_profiles"] = repaired_count
        else:
            if not bot_token:
                logging.error("错误: 环境变量 DISCORD_TOKEN 未设置。")
            if not args.guild_id:
                logging.error("错误: --guild-id 参数在 'repair' 模式下是必需的。")
            logging.error("无法执行修复操作。")
    elif args.mode == "migrate":
        migrated_count, skipped_count = await run_migrate_mode(sqlite_users)
        report_stats["migrated_summaries"] = migrated_count
        report_stats["skipped_migrations"] = skipped_count
    else:
        logging.error(f"未知的模式: {args.mode}")

    # 在所有操作结束后打印报告
    print_final_report(args.mode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="个人记忆摘要数据迁移和修复工具")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["check", "repair", "migrate"],
        required=True,
        help="脚本运行模式: 'check' (检查), 'repair' (修复), 'migrate' (迁移)",
    )
    parser.add_argument(
        "--guild-id",
        type=str,
        help="在 'repair' 模式下需要指定的 Discord 服务器（公会）ID",
    )
    args = parser.parse_args()

    # 导入 database 会自动触发 load_dotenv()

    asyncio.run(main(args))
