import pytest
from datetime import datetime

from src.chat.utils.time_utils import BEIJING_TZ


@pytest.mark.asyncio
class TestAffectionService:
    async def test_get_or_create_new_user(self, aff_svc, clean_tables):
        status = await aff_svc.get_affection_status(100)
        assert status["points"] == 0

    async def test_increase_affection_on_message(self, aff_svc, clean_tables):
        from unittest.mock import patch

        with patch("random.random", return_value=0.0):
            result = await aff_svc.increase_affection_on_message(100)
            assert result is not None
            assert result > 0

    async def test_increase_affection_on_message_miss(self, aff_svc, clean_tables):
        from unittest.mock import patch

        with patch("random.random", return_value=1.0):
            result = await aff_svc.increase_affection_on_message(100)
            assert result is None

    async def test_increase_affection_for_gift(self, aff_svc, clean_tables):
        result, msg = await aff_svc.increase_affection_for_gift(100, points_to_add=50)
        assert result is True
        status = await aff_svc.get_affection_status(100)
        assert status["points"] >= 50

    async def test_increase_affection_for_gift_twice_same_day(
        self, aff_svc, clean_tables
    ):
        await aff_svc.increase_affection_for_gift(100, points_to_add=10)
        result, msg = await aff_svc.increase_affection_for_gift(100, points_to_add=10)
        assert result is False

    async def test_decrease_affection_on_blacklist(self, aff_svc, clean_tables):
        await aff_svc.increase_affection_for_gift(100, points_to_add=50)
        new_points = await aff_svc.decrease_affection_on_blacklist(100)
        assert new_points == 40

    async def test_decrease_affection_on_blacklist_new_user(
        self, aff_svc, clean_tables
    ):
        from src.chat.config.chat_config import AFFECTION_CONFIG

        new_points = await aff_svc.decrease_affection_on_blacklist(99999)
        assert new_points == AFFECTION_CONFIG["BLACKLIST_PENALTY"]

    async def test_add_affection_points(self, aff_svc, clean_tables):
        new_points = await aff_svc.add_affection_points(100, 30)
        assert new_points == 30
        new_points = await aff_svc.add_affection_points(100, 20)
        assert new_points == 50

    async def test_get_affection_level_info(self, aff_svc):
        level = aff_svc.get_affection_level_info(0)
        assert level["level_name"] == "陌生"

        level = aff_svc.get_affection_level_info(25)
        assert level["level_name"] == "熟悉"

        level = aff_svc.get_affection_level_info(75)
        assert level["level_name"] == "亲密"

    async def test_daily_gain_resets(self, aff_svc, clean_tables):
        await aff_svc.increase_affection_for_gift(100, points_to_add=10)
        today = datetime.now(BEIJING_TZ).date().isoformat()
        await aff_svc.reset_daily_affection_gain(today)
        status = await aff_svc.get_affection_status(100)
        assert status["daily_gain"] == 0
