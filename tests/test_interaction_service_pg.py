import pytest
from datetime import datetime

from sqlalchemy import select

from src.database.models import InteractionLog


@pytest.mark.asyncio
class TestFeedingService:
    async def test_record_feeding(self, feeding_svc, clean_tables):
        await feeding_svc.record_feeding("123456")
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            result = await s.execute(
                select(InteractionLog).where(
                    InteractionLog.user_id == "123456",
                    InteractionLog.interaction_type == "feeding",
                )
            )
            assert result.scalar_one() is not None

    async def test_can_feed_first_time(self, feeding_svc, clean_tables):
        can, msg = await feeding_svc.can_feed("123456")
        assert can is True
        assert msg == ""

    async def test_can_feed_cooldown(self, feeding_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(
                    InteractionLog(
                        user_id="123456",
                        interaction_type="feeding",
                        timestamp=datetime.utcnow(),
                    )
                )
        can, msg = await feeding_svc.can_feed("123456")
        assert can is False
        assert "饱啦饱啦" in msg


@pytest.mark.asyncio
class TestConfessionService:
    async def test_record_confession(self, confession_svc, clean_tables):
        await confession_svc.record_confession("123456")
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            result = await s.execute(
                select(InteractionLog).where(
                    InteractionLog.user_id == "123456",
                    InteractionLog.interaction_type == "confession",
                )
            )
            assert result.scalar_one() is not None

    async def test_can_confess_first_time(self, confession_svc, clean_tables):
        can, msg = await confession_svc.can_confess("123456")
        assert can is True
        assert msg == ""

    async def test_can_confess_cooldown(self, confession_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(
                    InteractionLog(
                        user_id="123456",
                        interaction_type="confession",
                        timestamp=datetime.utcnow(),
                    )
                )
        can, msg = await confession_svc.can_confess("123456")
        assert can is False
        assert "忏悔太频繁" in msg
