# -*- coding: utf-8 -*-

import asyncio
import argparse
import logging
import os
import sys

# 将 src 目录添加到 Python 路径中，以便能够导入项目模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.guidance.utils.database import guidance_db_manager as db_manager

# 配置日志记录
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


async def diagnose_single_tag(guild_id: int, tag_name: str):
    """
    诊断单个兴趣标签的引导路径部署状态。
    """
    log.info(f"--- 开始诊断标签: '{tag_name}' (服务器 ID: {guild_id}) ---")

    # 1. 根据标签名称查找标签信息
    tag = await db_manager.get_tag_by_name(guild_id, tag_name)
    if not tag:
        log.error(f"错误: 在服务器 {guild_id} 中找不到名为 '{tag_name}' 的标签。")
        print("-" * 50)
        return

    log.info(f"成功找到标签 ID: {tag['tag_id']}")

    # 2. 获取该标签对应的引导路径
    path_steps = await db_manager.get_path_for_tag(tag["tag_id"])
    if not path_steps:
        log.warning(f"警告: 标签 '{tag_name}' 没有配置任何引导路径。")
        print("-" * 50)
        return

    log.info(f"为标签 '{tag_name}' 生成的路径包含 {len(path_steps)} 个步骤。")
    print("-" * 40)

    # 3. 逐一检查路径中每个步骤的部署状态
    entry_point_found = False
    for i, step in enumerate(path_steps):
        location_id = step["location_id"]
        channel_config = await db_manager.get_channel_message(location_id)

        status_symbol = "❌"
        status_text = "未部署"
        message_id_info = ""

        if channel_config and channel_config.get("deployed_message_id"):
            status_symbol = "✅"
            status_text = "已部署"
            message_id_info = f"(Message ID: {channel_config['deployed_message_id']})"
            if not entry_point_found:
                entry_point_found = True

        print(
            f"步骤 {i + 1}: 频道 ID {location_id}\n"
            f"  状态: {status_symbol} {status_text} {message_id_info}\n"
        )

    # 4. 打印最终诊断结论
    print("-" * 40)
    log.info("--- 诊断结论 ---")
    if entry_point_found:
        log.info(f"✅ 标签 '{tag_name}' 的引导路径至少有一个有效的入口点。")
    else:
        log.error(f"❌ 严重错误: 标签 '{tag_name}' 的引导路径没有任何一个步骤被部署！")
        log.error("   这会导致新用户选择此标签后，看到“入口点尚未部署”的错误信息。")
    print("-" * 50)


async def main():
    """
    主执行函数，解析参数并调用相应的诊断功能。
    """
    parser = argparse.ArgumentParser(
        description="诊断 Guidance 系统中特定标签或所有标签的路径部署状态。"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--tag-name",
        type=str,
        help="需要诊断的单个兴趣标签的准确名称。",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="诊断所有已配置的兴趣标签。",
    )
    parser.add_argument(
        "--guild-id",
        type=int,
        required=True,
        help="需要进行诊断的服务器（Guild）的 ID。",
    )
    args = parser.parse_args()

    await db_manager.init_async()
    try:
        if args.all:
            log.info(f"--- 开始对服务器 {args.guild_id} 进行全面诊断 ---")
            all_tags = await db_manager.get_all_tags(args.guild_id)
            if not all_tags:
                log.warning(
                    f"在服务器 {args.guild_id} 的数据库中没有找到任何已配置的兴趣标签。"
                )
                return

            log.info(f"共找到 {len(all_tags)} 个标签，将逐一进行诊断...")
            print("=" * 50)

            for tag in all_tags:
                await diagnose_single_tag(args.guild_id, tag["tag_name"])

        elif args.tag_name:
            await diagnose_single_tag(args.guild_id, args.tag_name)
    finally:
        await db_manager.close()
        log.info("数据库连接已关闭。")


if __name__ == "__main__":
    asyncio.run(main())
