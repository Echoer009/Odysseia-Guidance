import logging
from datetime import time, timedelta, timezone

from discord.ext import commands, tasks

from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)


class DBCleanupCog(commands.Cog):
    """
    定期清理数据库中的过期数据，防止表无限增长。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cleanup_timestamps.start()

    async def cog_unload(self):
        self.cleanup_timestamps.cancel()

    @tasks.loop(time=time(hour=4, minute=0, tzinfo=timezone(timedelta(hours=8))))
    async def cleanup_timestamps(self):
        """
        每天北京时间凌晨 4:00 清理过期的频率限制时间戳。

        删除超过 24 小时的旧记录，这些记录已不再被任何滑动窗口查询使用。
        """
        try:
            deleted = await chat_db_manager.cleanup_old_timestamps(max_age_hours=24)
            if deleted > 0:
                log.info(f"[DB清理] 已清理 {deleted} 条过期的频率限制时间戳记录。")
            else:
                log.debug("[DB清理] 无需清理过期时间戳。")
        except Exception as e:
            log.error(f"[DB清理] 清理频率限制时间戳时出错: {e}", exc_info=True)

    @cleanup_timestamps.before_loop
    async def before_cleanup_timestamps(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(DBCleanupCog(bot))
    log.info("DBCleanupCog 已加载。")
