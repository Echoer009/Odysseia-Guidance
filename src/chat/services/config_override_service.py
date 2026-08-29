import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select

from src.database.database import AsyncSessionLocal
from src.database.models import ConfigOverride

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 15.0

_MISSING = object()


class ConfigOverrideService:
    """
    读取 admin.config_overrides 表的运行时配置覆盖服务。
    Bot 热路径按消息读取，因此内置每进程 15 秒 TTL 缓存，
    set/delete 时主动失效。get 在数据库故障时安全回退默认值。
    """

    def __init__(self, cache_ttl: float = CACHE_TTL_SECONDS):
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._cache_ttl = cache_ttl

    def _cache_get(self, key: str) -> tuple[bool, Any]:
        entry = self._cache.get(key)
        if entry is None:
            return False, None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            self._cache.pop(key, None)
            return False, None
        return True, value

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = (time.monotonic() + self._cache_ttl, value)

    def invalidate(self, key: Optional[str] = None) -> None:
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    async def get(self, key: str, default: Any = None) -> Any:
        try:
            hit, value = self._cache_get(key)
            if not hit:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(
                        select(ConfigOverride.value).where(
                            ConfigOverride.key == key
                        )
                    )
                    row = result.scalar_one_or_none()
                value = row if row is not None else _MISSING
                self._cache_set(key, value)
            return default if value is _MISSING else value
        except Exception as e:
            log.warning(f"读取配置覆盖 '{key}' 失败，回退默认值: {e}")
            return default

    async def get_json(self, key: str, default: Any) -> Any:
        return await self.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                await session.merge(ConfigOverride(key=key, value=value))
        self.invalidate(key)

    async def delete(self, key: str) -> bool:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConfigOverride.key).where(ConfigOverride.key == key)
            )
            exists = result.scalar_one_or_none() is not None
            if exists:
                await session.execute(
                    delete(ConfigOverride).where(ConfigOverride.key == key)
                )
                await session.commit()
        self.invalidate(key)
        return exists

    async def list_overrides(self) -> List[Dict]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ConfigOverride).order_by(ConfigOverride.key)
            )
            rows = list(result.scalars().all())
        return [
            {
                "key": row.key,
                "value": row.value,
                "updated_at": row.updated_at.isoformat()
                if row.updated_at
                else None,
            }
            for row in rows
        ]


config_override_service = ConfigOverrideService()
