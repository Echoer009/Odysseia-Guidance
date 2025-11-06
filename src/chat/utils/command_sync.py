import discord
from discord.ext import commands
from discord import app_commands


import logging

# 设置日志记录
logger = logging.getLogger(__name__)


async def sync_commands(
    tree: app_commands.CommandTree,
    bot: commands.Bot,
    *,
    blacklist: list[str] | None = None,
):
    """
    智能同步应用命令，保留服务器上不由机器人代码管理的命令（例如活动入口点），并可选择忽略黑名单中的本地命令。

    :param tree: The command tree to sync.
    :param bot: The bot instance.
    :param blacklist: A list of local command names to exclude from syncing.
    """
    if blacklist is None:
        blacklist = []

    # 1. 获取所有本地命令，并排除黑名单中的命令
    local_commands_to_sync = [
        cmd for cmd in tree.get_commands() if cmd.name not in blacklist
    ]
    local_payload = [cmd.to_dict(tree=tree) for cmd in local_commands_to_sync]
    synced_local_names = {cmd.name for cmd in local_commands_to_sync}
    logger.info(f"本地待同步命令: {[cmd['name'] for cmd in local_payload]}")

    # 2. 获取服务器上所有的全局命令
    try:
        logger.info("正在从 Discord 获取所有全局命令...")
        remote_payload = await bot.http.get_global_commands(bot.application_id)
        logger.info(f"从 Discord 成功获取 {len(remote_payload)} 个命令。")
    except discord.HTTPException as e:
        logger.error(f"从 Discord 获取命令失败: {e}")
        # 如果无法获取远程命令，则中止同步以避免意外删除
        return

    # 3. 识别出服务器上存在但不由本地代码管理的命令
    unmanaged_remote_commands_payload = [
        cmd for cmd in remote_payload if cmd["name"] not in synced_local_names
    ]

    if unmanaged_remote_commands_payload:
        unmanaged_names = [cmd["name"] for cmd in unmanaged_remote_commands_payload]
        logger.info(
            f"发现服务器上存在但本地代码未管理的命令，将保留它们: {unmanaged_names}"
        )

    # 4. 合并本地待同步命令和需要保留的远程命令
    # 4. 从不由本地管理的远程命令中，只保留我们明确想要保留的（如活动入口点）
    commands_to_keep_remotely = ["launch"]
    kept_unmanaged_commands = [
        cmd
        for cmd in unmanaged_remote_commands_payload
        if cmd["name"] in commands_to_keep_remotely
    ]
    if kept_unmanaged_commands:
        kept_names = [cmd["name"] for cmd in kept_unmanaged_commands]
        logger.info(f"根据白名单，将从服务器保留以下命令: {kept_names}")

    # 5. 合并本地命令和需要保留的远程命令，形成最终的命令列表
    final_payload = local_payload + kept_unmanaged_commands

    # 6. 执行批量更新
    try:
        logger.info(f"正在向 Discord 推送 {len(final_payload)} 个命令进行同步...")
        await bot.http.bulk_upsert_global_commands(
            bot.application_id, payload=final_payload
        )
        final_names = [p["name"] for p in final_payload]
        logger.info(f"命令同步成功! 当前服务器命令: {final_names}")
    except discord.HTTPException as e:
        logger.error(f"命令同步期间发生 HTTP 错误: {e}")
        raise  # 重新抛出异常，以便上层调用者知道同步失败
