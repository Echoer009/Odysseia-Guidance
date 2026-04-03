import pytest

from sqlalchemy import select, func

from src.database.database import AsyncSessionLocal
from src.database.models import InteractionLog


@pytest.mark.asyncio
class TestEconomyClosedLoop:
    async def test_daily_reward_then_purchase(self, coin_svc, clean_tables):
        await coin_svc.grant_daily_message_reward(100)
        balance = await coin_svc.get_balance(100)
        assert balance > 0
        result = await coin_svc.remove_coins(100, balance, "spend all")
        assert result == 0

    async def test_borrow_then_repay(self, coin_svc, clean_tables):
        await coin_svc.borrow_coins(100, 500)
        assert await coin_svc.get_balance(100) == 500
        await coin_svc.repay_loan(100)
        assert await coin_svc.get_balance(100) == 0

    async def test_work_reward_adds_coins(self, coin_svc, clean_tables):
        initial = await coin_svc.get_balance(100)
        await coin_svc.add_coins(100, 100, "work reward")
        assert await coin_svc.get_balance(100) == initial + 100

    async def test_sell_body_loses_coins(self, coin_svc, clean_tables):
        await coin_svc.add_coins(100, 500, "initial")
        initial = await coin_svc.get_balance(100)
        await coin_svc.remove_coins(100, 50, "sell body loss")
        assert await coin_svc.get_balance(100) == initial - 50


@pytest.mark.asyncio
class TestAffectionGiftIntegration:
    async def test_gift_increases_affection(self, coin_svc, aff_svc, clean_tables):
        await coin_svc.add_coins(100, 10000, "initial")
        before = await aff_svc.get_affection_status(100)
        result, msg = await aff_svc.increase_affection_for_gift(100, points_to_add=50)
        assert result is True
        after = await aff_svc.get_affection_status(100)
        assert after["points"] > before["points"]


@pytest.mark.asyncio
class TestYearlySummaryData:
    async def test_transaction_aggregation(self, coin_svc, clean_tables):
        await coin_svc.add_coins(100, 500, "deposit")
        await coin_svc.remove_coins(100, 200, "purchase")
        transactions = await coin_svc.get_transaction_history(100, limit=10)
        assert len(transactions) == 2
        assert transactions[0]["amount"] == -200
        assert transactions[1]["amount"] == 500

    async def test_feeding_confession_count(
        self, feeding_svc, confession_svc, clean_tables
    ):
        await feeding_svc.record_feeding("100")
        await feeding_svc.record_feeding("100")
        await confession_svc.record_confession("100")

        async with AsyncSessionLocal() as s:
            feed_count = (
                await s.execute(
                    select(func.count())
                    .select_from(InteractionLog)
                    .where(
                        InteractionLog.user_id == "100",
                        InteractionLog.interaction_type == "feeding",
                    )
                )
            ).scalar()
            confess_count = (
                await s.execute(
                    select(func.count())
                    .select_from(InteractionLog)
                    .where(
                        InteractionLog.user_id == "100",
                        InteractionLog.interaction_type == "confession",
                    )
                )
            ).scalar()

        assert feed_count == 2
        assert confess_count == 1
