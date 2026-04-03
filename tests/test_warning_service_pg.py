import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from src.database.models import UserWarningRecord, UserAffection


@pytest.mark.asyncio
class TestWarningService:
    async def test_first_warning(self, clean_tables):
        from src.chat.services import warning_service
        from src.database.database import AsyncSessionLocal

        future_time = datetime.now(timezone.utc) + timedelta(days=7)

        with patch.object(
            warning_service.chat_db_manager,
            "add_to_blacklist",
            new_callable=AsyncMock,
        ):
            result = await warning_service.record_warning_and_check_blacklist(
                100, 200, future_time
            )

        assert result["was_blacklisted"] is True
        assert result["new_warning_count"] == 0

        async with AsyncSessionLocal() as s:
            db_result = await s.execute(
                select(UserWarningRecord).where(
                    UserWarningRecord.user_id == "100",
                    UserWarningRecord.guild_id == "200",
                )
            )
            record = db_result.scalar_one()
            assert record.warning_count == 0

    async def test_warning_deducts_affection(self, clean_tables):
        from src.chat.services import warning_service
        from src.chat.config.chat_config import AFFECTION_CONFIG
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserAffection(user_id="100", affection_points=50))

        future_time = datetime.now(timezone.utc) + timedelta(days=7)
        with patch.object(
            warning_service.chat_db_manager,
            "add_to_blacklist",
            new_callable=AsyncMock,
        ):
            await warning_service.record_warning_and_check_blacklist(
                100, 200, future_time
            )

        async with AsyncSessionLocal() as s:
            result = await s.execute(
                select(UserAffection).where(UserAffection.user_id == "100")
            )
            affection = result.scalar_one()
            assert (
                affection.affection_points == 50 + AFFECTION_CONFIG["BLACKLIST_PENALTY"]
            )
