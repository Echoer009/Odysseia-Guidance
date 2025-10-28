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
    log.info("--- [deploy_all_panels] 服务已启动 ---")
    log.info("正在从数据库获取所有频道消息配置...")
    all_configs = await db_manager.get_all_channel_messages(guild.id)
    log.info(f"数据库查询完成，共获取 {len(all_configs)} 条配置。")

    deploy_targets = [c for c in all_configs if c.get("permanent_message_data")]
    log.info(f"筛选后，有 {len(deploy_targets)} 个地点需要部署永久面板。")

    if not deploy_targets:
        return 0, 0, ["没有找到任何已配置永久消息的地点可供部署。"]

    success_count, fail_count, report_lines = 0, 0, []

    for config_item in deploy_targets:
        channel_id = config_item["channel_id"]
        channel = guild.get_channel_or_thread(channel_id)

        # 在处理前添加日志
        log.info(f"正在为地点 ID: {channel_id} 部署永久面板...")

        if not channel:
            try:
                # 尝试强制获取，以支持已归档的帖子
                channel = await guild.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                report_lines.append(f"❌ **未知地点 (ID: {channel_id})**: 跳过。")
                fail_count += 1
                continue

        # 检查更全面的权限
        perms = channel.permissions_for(guild.me)
        required_perms = {
            "view_channel": perms.view_channel,
            "send_messages": perms.send_messages,
            "manage_messages": perms.manage_messages,
            "read_message_history": perms.read_message_history,
        }
        missing_perms = [p for p, v in required_perms.items() if not v]

        if missing_perms:
            report_lines.append(
                f"❌ **#{channel.name}**: 权限不足 (缺少: {', '.join(missing_perms)})。"
            )
            fail_count += 1
            continue

        try:
            perm_data = config_item.get("permanent_message_data") or {}
            if not perm_data:
                report_lines.append(f"⚠️ **#{channel.name}**: 缺少永久消息的配置数据。")
                fail_count += 1
                continue

            # 1. 主动扫描并清理频道内所有符合特征的旧面板
            expected_footer = perm_data.get("footer_text")
            if expected_footer:
                log.info(f"正在主动扫描并清理频道 #{channel.name} 中的旧面板...")
                try:
                    deleted_count = 0
                    async for message in channel.history(limit=50):
                        if (
                            message.author.id == guild.me.id
                            and message.embeds
                            and message.embeds[0].footer
                            and message.embeds[0].footer.text == expected_footer
                        ):
                            await message.delete()
                            deleted_count += 1
                            log.info(f"  - 已删除一个匹配的旧面板 (ID: {message.id})")
                    if deleted_count > 0:
                        report_lines.append(
                            f"  - 在 **#{channel.name}** 通过主动扫描删除了 **{deleted_count}** 个旧面板。"
                        )
                except discord.Forbidden:
                    log.warning(f"⚠️ 在主动清理频道 #{channel.name} 时因权限不足跳过。")
                    report_lines.append(
                        f"  - ⚠️ 在 **#{channel.name}** 主动清理失败 (权限不足)。"
                    )
                except Exception as e:
                    log.error(
                        f"在主动清理频道 #{channel.name} 时发生未知错误: {e}",
                        exc_info=True,
                    )
                    report_lines.append(
                        f"  - ❌ 在 **#{channel.name}** 主动清理时发生未知错误。"
                    )

            # 清理数据库中记录的旧消息ID
            old_message_id = config_item.get("deployed_message_id")
            if old_message_id:
                try:
                    log.info(f"正在尝试删除数据库记录的旧面板 (ID: {old_message_id})")
                    old_message = await channel.fetch_message(old_message_id)
                    await old_message.delete()
                    log.info(f"  - 成功删除数据库记录的旧面板。")
                    report_lines.append(
                        f"  - 在 **#{channel.name}** 删除了数据库记录的旧面板。"
                    )
                except discord.NotFound:
                    log.info(
                        f"数据库记录的旧面板 (ID: {old_message_id}) 已不存在，跳过删除。"
                    )
                    # 即使找不到，也要在报告中体现
                    report_lines.append(
                        f"  - ℹ️ 在 **#{channel.name}** 数据库记录的旧面板已不存在。"
                    )
                except discord.Forbidden:
                    log.warning(
                        f"删除数据库记录的旧面板 (ID: {old_message_id}) 时权限不足。"
                    )
                    report_lines.append(
                        f"  - ⚠️ 在 **#{channel.name}** 删除数据库记录的旧面板失败 (权限不足)。"
                    )
                except Exception as e:
                    log.error(
                        f"删除数据库记录的旧面板时发生未知错误: {e}", exc_info=True
                    )
                    report_lines.append(
                        f"  - ❌ 在 **#{channel.name}** 删除数据库记录的旧面板时发生未知错误。"
                    )
                finally:
                    # 无论如何都清除旧ID，因为我们要部署新的
                    await db_manager.update_channel_deployment_id(channel_id, None)

            # 2. 创建并发送新消息
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
            # 细化错误报告
            if isinstance(e, discord.Forbidden):
                report_lines.append(f"❌ **#{channel.name}**: 部署失败 (权限不足)。")
            elif isinstance(e, discord.NotFound):
                report_lines.append(
                    f"❌ **#{channel.name}**: 部署失败 (目标频道或线程不存在)。"
                )
            else:
                report_lines.append(
                    f"❌ **#{channel.name}**: 发生未知错误 ({type(e).__name__})。"
                )
            fail_count += 1

    return success_count, fail_count, report_lines
