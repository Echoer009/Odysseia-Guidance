# -*- coding: utf-8 -*-

import discord
import logging
from typing import Tuple, List

from src.guidance.utils.database import guidance_db_manager as db_manager
from src.guidance.utils.helpers import create_embed_from_template_data

log = logging.getLogger(__name__)


async def deploy_all_panels(guild: discord.Guild) -> Tuple[int, int, List[str]]:
    """
    向服务器中所有已配置永久消息的地点部署或更新引导面板。

    Args:
        guild: 目标 discord.Guild 对象。

    Returns:
        一个元组，包含 (成功数量, 失败数量, 报告行列表)。
    """
    all_configs = await db_manager.get_all_channel_messages(guild.id)
    deploy_targets = [c for c in all_configs if c.get("permanent_message_data")]

    if not deploy_targets:
        return 0, 0, ["没有找到任何已配置永久消息的地点可供部署。"]

    success_count, fail_count, report_lines = 0, 0, []

    for config_item in deploy_targets:
        channel_id = config_item["channel_id"]
        channel = guild.get_channel_or_thread(channel_id)
        if not channel:
            try:
                # 尝试强制获取，以支持已归档的帖子
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                report_lines.append(f"❌ **未知地点 (ID: {channel_id})**: 跳过。")
                fail_count += 1
                continue

        if not channel.permissions_for(guild.me).send_messages:
            report_lines.append(f"❌ **#{channel.name}**: 权限不足。")
            fail_count += 1
            continue

        try:
            # 1. 删除旧消息
            old_message_id = config_item.get("deployed_message_id")
            if old_message_id:
                try:
                    old_message = await channel.fetch_message(old_message_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    # 如果找不到或没权限删除，就当中没这回事，继续
                    pass
                finally:
                    # 确保数据库记录被清除
                    await db_manager.update_channel_deployment_id(channel_id, None)

            # 2. 创建并发送新消息
            perm_data = config_item.get("permanent_message_data") or {}
            perm_embed = create_embed_from_template_data(perm_data, channel=channel)

            from src.guidance.ui.views.channel_panel import PermanentPanelView

            view = PermanentPanelView()
            new_message = await channel.send(embed=perm_embed, view=view)
            await db_manager.update_channel_deployment_id(channel_id, new_message.id)

            report_lines.append(
                f"✅ **#{channel.name}**: [部署成功]({new_message.jump_url})"
            )
            success_count += 1

        except Exception as e:
            log.error(f"部署到地点 {channel_id} 时出错: {e}", exc_info=True)
            report_lines.append(f"❌ **#{channel.name}**: 发生未知错误。")
            fail_count += 1

    return success_count, fail_count, report_lines
