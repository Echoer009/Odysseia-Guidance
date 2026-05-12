import logging
from datetime import datetime, timezone
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
        每分钟检查一次当前活动的状态，并在活动结束后执行结算。
        """
        active_event = event_service.get_active_event()
        if not active_event:
            return

        # 检查活动是否已经有获胜者，如果有，则说明已经结算过了
        if event_service.get_winning_faction():
            return

        now = datetime.now(timezone.utc)
        end_date = datetime.fromisoformat(active_event["end_date"])

        if now >= end_date:
            log.info(f"活动 '{active_event['event_name']}' 已结束，开始执行结算...")
            try:
                await self.faction_service.determine_winner_and_end_event()
                log.info(f"活动 '{active_event['event_name']}' 结算成功。")
            except Exception as e:
                log.error(
                    f"活动 '{active_event['event_name']}' 结算失败: {e}", exc_info=True
                )

    @check_event_status.before_loop
    async def before_check_event_status(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(EventCog(bot))
