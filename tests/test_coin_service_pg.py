import pytest
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from src.database.models import UserCoins, CoinTransaction, CoinLoan


@pytest.mark.asyncio
class TestCoinServiceGetBalance:
    async def test_existing_user(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=500))
        balance = await coin_svc.get_balance(100)
        assert balance == 500

    async def test_nonexistent_user(self, coin_svc, clean_tables):
        balance = await coin_svc.get_balance(99999)
        assert balance == 0


@pytest.mark.asyncio
class TestCoinServiceAddCoins:
    async def test_add_to_new_user(self, coin_svc, clean_tables):
        new_balance = await coin_svc.add_coins(100, 100, "test deposit")
        assert new_balance == 100

    async def test_add_to_existing_user(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=500))
        new_balance = await coin_svc.add_coins(100, 100, "test add")
        assert new_balance == 600

    async def test_add_creates_transaction(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        await coin_svc.add_coins(100, 100, "test tx")
        async with AsyncSessionLocal() as s:
            result = await s.execute(
                select(CoinTransaction).where(CoinTransaction.user_id == "100")
            )
            tx = result.scalar_one()
            assert tx.amount == 100
            assert tx.reason == "test tx"

    async def test_add_zero_raises(self, coin_svc, clean_tables):
        with pytest.raises(ValueError):
            await coin_svc.add_coins(100, 0, "zero")

    async def test_add_negative_raises(self, coin_svc, clean_tables):
        with pytest.raises(ValueError):
            await coin_svc.add_coins(100, -10, "negative")


@pytest.mark.asyncio
class TestCoinServiceRemoveCoins:
    async def test_remove_success(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=500))
        new_balance = await coin_svc.remove_coins(100, 200, "test deduct")
        assert new_balance == 300

    async def test_remove_insufficient_balance(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=50))
        result = await coin_svc.remove_coins(100, 200, "test deduct")
        assert result is None

    async def test_remove_creates_negative_transaction(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=500))
        await coin_svc.remove_coins(100, 100, "purchase")
        async with AsyncSessionLocal() as s:
            result = await s.execute(
                select(CoinTransaction).where(CoinTransaction.user_id == "100")
            )
            tx = result.scalar_one()
            assert tx.amount == -100

    async def test_remove_exactly_all(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=100))
        new_balance = await coin_svc.remove_coins(100, 100, "clear all")
        assert new_balance == 0


@pytest.mark.asyncio
class TestCoinServiceDailyReward:
    async def test_first_time_today(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=0))
        result = await coin_svc.grant_daily_message_reward(100)
        assert result is True

    async def test_already_claimed_today(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(
                    UserCoins(user_id="100", balance=100, last_daily_message_date=today)
                )
        result = await coin_svc.grant_daily_message_reward(100)
        assert result is False

    async def test_new_day_resets(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        yesterday = (
            (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1))
            .date()
            .isoformat()
        )
        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(
                    UserCoins(
                        user_id="100", balance=100, last_daily_message_date=yesterday
                    )
                )
        result = await coin_svc.grant_daily_message_reward(100)
        assert result is True


@pytest.mark.asyncio
class TestCoinServiceLoan:
    async def test_borrow_success(self, coin_svc, clean_tables):
        result, msg = await coin_svc.borrow_coins(100, 500)
        assert result is True
        balance = await coin_svc.get_balance(100)
        assert balance == 500

    async def test_borrow_with_existing_loan(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(CoinLoan(user_id="100", amount=500, status="active"))
        result, msg = await coin_svc.borrow_coins(100, 200)
        assert result is False

    async def test_repay_success(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=500))
                s.add(CoinLoan(user_id="100", amount=300, status="active"))
        result, msg = await coin_svc.repay_loan(100)
        assert result is True
        balance = await coin_svc.get_balance(100)
        assert balance == 200

    async def test_repay_insufficient_balance(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=100))
                s.add(CoinLoan(user_id="100", amount=500, status="active"))
        result, msg = await coin_svc.repay_loan(100)
        assert result is False


@pytest.mark.asyncio
class TestCoinServiceWarmupPreference:
    async def test_default_no_preference(self, coin_svc, clean_tables):
        result = await coin_svc.has_made_warmup_choice(100)
        assert result is False

    async def test_disable_warmup(self, coin_svc, clean_tables):
        await coin_svc.set_warmup_preference(100, wants_warmup=False)
        result = await coin_svc.has_withered_sunflower(100)
        assert result is True

    async def test_enable_warmup(self, coin_svc, clean_tables):
        await coin_svc.set_warmup_preference(100, wants_warmup=True)
        result = await coin_svc.has_withered_sunflower(100)
        assert result is False


@pytest.mark.asyncio
class TestCoinServiceThreadReplies:
    async def test_default_not_blocked(self, coin_svc, clean_tables):
        result = await coin_svc.blocks_thread_replies(100)
        assert result is False

    async def test_block_then_unblock(self, coin_svc, clean_tables):
        from src.database.database import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            async with s.begin():
                s.add(UserCoins(user_id="100", balance=0, blocks_thread_replies=True))
        assert await coin_svc.blocks_thread_replies(100) is True

        async with AsyncSessionLocal() as s:
            async with s.begin():
                row = (
                    await s.execute(select(UserCoins).where(UserCoins.user_id == "100"))
                ).scalar_one()
                row.blocks_thread_replies = False
        assert await coin_svc.blocks_thread_replies(100) is False


@pytest.mark.asyncio
class TestCoinServiceTransactionHistory:
    async def test_transaction_history(self, coin_svc, clean_tables):
        await coin_svc.add_coins(200, 500, "deposit")
        await coin_svc.remove_coins(200, 200, "purchase")
        history = await coin_svc.get_transaction_history(200, limit=10)
        assert len(history) == 2
        assert history[0]["amount"] == -200
        assert history[1]["amount"] == 500

    async def test_transaction_count(self, coin_svc, clean_tables):
        await coin_svc.add_coins(300, 100, "a")
        await coin_svc.add_coins(300, 100, "b")
        count = await coin_svc.get_transaction_count(300)
        assert count == 2
