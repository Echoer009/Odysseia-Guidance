import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from src.chat.services.event_service import event_service
from src.chat.services.faction_service import faction_service

log = logging.getLogger(__name__)


class EventCog(commands.Cog):
    """
    处理与节日活动相关的后台任务和命令。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.faction_service = faction_service
        self.check_event_status.start()

    async def cog_unload(self):
        self.check_event_status.cancel()

    @tasks.loop(minutes=1)
    async def check_event_status(self):
        """
        每分钟刷新活动状态（自动上线/下线），并对刚到期的活动执行结算与公告。
        """
        # 刷新前的活动快照：refresh 会将到期活动下线，结算依据此快照进行
        previous_event = event_service.get_active_event()

        # 自动激活/下线活动（is_active 为总开关，时间窗决定上线与下线）
        event_service.refresh()

        active_event = event_service.get_active_event()
        still_active = (
            previous_event is not None
            and active_event is not None
            and active_event.get("event_id") == previous_event.get("event_id")
        )

        # 活动刚被下线且确因到期（而非手动禁用）时执行结算
        if previous_event and not still_active:
            now = datetime.now(timezone.utc)
            end_date = datetime.fromisoformat(
                previous_event["end_date"].replace("Z", "+00:00")
            )
            if now >= end_date:
                await self._settle_event(previous_event)

    async def _settle_event(self, event_data: dict):
        """结算已到期的活动，并按 manifest 配置发送结算公告。"""
        event_id = event_data["event_id"]
        event_name = event_data.get("event_name", event_id)
        log.info(f"活动 '{event_name}' 已结束，开始执行结算...")

        try:
            winner = await self.faction_service.determine_winner_and_end_event(event_id)
        except Exception as e:
            log.error(f"活动 '{event_name}' 结算失败: {e}", exc_info=True)
            return

        if not winner:
            log.warning(f"活动 '{event_name}' 未能产生结算结果。")
            return

        log.info(f"活动 '{event_name}' 结算成功。")
        await self._announce_settlement(event_data, winner)

    async def _announce_settlement(self, event_data: dict, winner: dict):
        """若 manifest 配置了 announcement_channel_id，则向该频道发送结算公告（失败只记录日志）。"""
        channel_id = event_data.get("announcement_channel_id")
        if not channel_id:
            return

        event_name = event_data.get("event_name", event_data["event_id"])
        winning_faction_name = next(
            (
                f["faction_name"]
                for f in event_data.get("factions", [])
                if f["faction_id"] == winner["faction_id"]
            ),
            winner["faction_id"],
        )

        theme = event_data.get("theme") or {}
        embed = discord.Embed(
            title=f"{theme.get('emoji', '🎊')} {event_name} 圆满落幕 — 获胜阵营: {winning_faction_name}",
            description=(
                f"感谢所有参与者的奉献！最终 **{winning_faction_name}** 阵营以 "
                f"**{winner['total_points']}** 点贡献赢得了这场活动的胜利！"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text=theme.get("footer", "期待下一次重逢..."))

        try:
            channel = self.bot.get_channel(int(channel_id))
            if channel is None:
                channel = await self.bot.fetch_channel(int(channel_id))
            if not isinstance(channel, discord.abc.Messageable):
                log.error(
                    f"活动 '{event_name}' 的公告频道 {channel_id} 不支持发送消息。"
                )
                return
            await channel.send(embed=embed)
            log.info(f"已向频道 {channel_id} 发送活动 '{event_name}' 的结算公告。")
        except Exception as e:
            log.error(
                f"发送活动 '{event_name}' 的结算公告失败: {e}", exc_info=True
            )

    @check_event_status.before_loop
    async def before_check_event_status(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(EventCog(bot))
