# -*- coding: utf-8 -*-
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.database import AsyncSessionLocal
from src.database.models import ThreadSetting

log = logging.getLogger(__name__)


class ThreadSettingsService:
    """用于管理帖子设置的服务，例如教程搜索模式。"""

    def __init__(self):
        log.info("ThreadSettingsService 已初始化")

    async def get_search_mode(self, thread_id: str) -> str:
        """
        获取指定帖子的搜索模式。
        如果帖子没有设置，返回默认的 'ISOLATED' 模式。
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ThreadSetting.search_mode).where(
                        ThreadSetting.thread_id == thread_id
                    )
                )
                mode = result.scalar_one_or_none()
                if mode:
                    log.info(f"帖子 {thread_id} 的搜索模式为: {mode}")
                    return mode
                else:
                    log.info(f"帖子 {thread_id} 没有设置，使用默认模式: ISOLATED")
                    return "ISOLATED"
        except Exception as e:
            log.error(
                f"获取帖子 {thread_id} 的搜索模式时出错: {e}",
                exc_info=True,
            )
            return "ISOLATED"  # 出错时回退到默认模式

    async def set_search_mode(self, thread_id: str, mode: str) -> bool:
        """
        设置指定帖子的搜索模式。
        如果设置已存在则更新，不存在则创建。
        """
        if mode not in ["ISOLATED", "PRIORITY"]:
            log.warning(f"尝试设置无效的搜索模式: {mode}")
            return False

        try:
            async with AsyncSessionLocal() as session:
                # 检查是否已存在
                existing_setting = await session.execute(
                    select(ThreadSetting).where(ThreadSetting.thread_id == thread_id)
                )
                setting = existing_setting.scalar_one_or_none()

                if setting:
                    # 使用 setattr 以避免静态类型检查器的误报，并确保动态属性赋值正确
                    setattr(setting, "search_mode", mode)
                    log.info(f"更新帖子 {thread_id} 的搜索模式为: {mode}")
                else:
                    new_setting = ThreadSetting(thread_id=thread_id, search_mode=mode)
                    session.add(new_setting)
                    log.info(f"为帖子 {thread_id} 创建新的搜索模式设置: {mode}")

                await session.commit()
                return True
        except Exception as e:
            log.error(
                f"设置帖子 {thread_id} 的搜索模式时出错: {e}",
                exc_info=True,
            )
            return False


# 创建服务的单例
thread_settings_service = ThreadSettingsService()
