# -*- coding: utf-8 -*-
"""
管理后台同步 Cog

轮询管理后台写入的 SQLite 标记，及时应用活动重载与派系选择。
配置覆盖类改动由 ConfigOverrideService 的 TTL 缓存自动生效，无需此处处理。
"""

import logging

from discord.ext import commands, tasks

from src.chat.services.event_service import event_service
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)


class AdminSyncCog(commands.Cog):
    """
    处理管理后台写入的同步标记。
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.event_reload_check.start()

    async def cog_unload(self):
        self.event_reload_check.cancel()

    async def _consume_flag(self, key: str) -> bool:
        value = await chat_db_manager.get_global_setting(key)
        if value == "1":
            await chat_db_manager.delete_global_setting(key)
            return True
        return False

    @tasks.loop(seconds=30)
    async def event_reload_check(self):
        try:
            if await self._consume_flag("event_reload_pending"):
                log.info("[AdminSync] 检测到活动重载标记，开始重新扫描活动配置。")
                event_service._load_and_check_events()

                faction_value = await chat_db_manager.get_global_setting(
                    "event_selected_faction"
                )
                if faction_value:
                    await chat_db_manager.delete_global_setting(
                        "event_selected_faction"
                    )
                    faction_id = faction_value.split(":")[-1].strip()
                    if faction_id:
                        event_service.set_selected_faction(faction_id)
                        log.info(
                            f"[AdminSync] 已应用管理后台选择的派系: {faction_id}"
                        )
                log.info("[AdminSync] 活动配置重载完成。")
        except Exception as e:
            log.error(f"[AdminSync] 处理活动重载标记时出错: {e}", exc_info=True)

    @event_reload_check.before_loop
    async def before_event_reload_check(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminSyncCog(bot))
    log.info("AdminSyncCog 已加载。")
