import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from src.database.models import (
    UserCoins,
    CoinTransaction,
    InteractionLog,
    UserAffection,
    UserWarningRecord,
    CoinLoan,
)


@pytest.mark.asyncio
class TestUserCoinsModel:
    async def test_create_user_coins(self, db_session):
        coins = UserCoins(user_id="123456", balance=100)
        db_session.add(coins)
        await db_session.flush()
        assert coins.user_id == "123456"
        assert coins.balance == 100

    async def test_user_id_unique_constraint(self, db_session):
        db_session.add(UserCoins(user_id="123456", balance=100))
        await db_session.flush()
        db_session.add(UserCoins(user_id="123456", balance=200))
        with pytest.raises(IntegrityError):
            await db_session.flush()

    async def test_nullable_fields(self, db_session):
        coins = UserCoins(user_id="123456", balance=0)
        db_session.add(coins)
        await db_session.flush()
        assert coins.last_daily_message_date is None
        assert coins.has_withered_sunflower is None
        assert coins.thread_cooldown_seconds is None

    async def test_update_balance(self, db_session):
        coins = UserCoins(user_id="123456", balance=100)
        db_session.add(coins)
        await db_session.flush()
        coins.balance += 50
        await db_session.flush()
        await db_session.refresh(coins)
        assert coins.balance == 150

    async def test_default_balance_is_zero(self, db_session):
        coins = UserCoins(user_id="999")
        db_session.add(coins)
        await db_session.flush()
        assert coins.balance == 0


@pytest.mark.asyncio
class TestCoinTransactionModel:
    async def test_create_transaction(self, db_session):
        tx = CoinTransaction(user_id="123456", amount=100, reason="test")
        db_session.add(tx)
        await db_session.flush()
        assert tx.id is not None
        assert tx.timestamp is not None

    async def test_negative_amount(self, db_session):
        tx = CoinTransaction(user_id="123456", amount=-50, reason="deduct")
        db_session.add(tx)
        await db_session.flush()
        assert tx.amount == -50


@pytest.mark.asyncio
class TestInteractionLogModel:
    async def test_feeding_log(self, db_session):
        log = InteractionLog(user_id="123456", interaction_type="feeding")
        db_session.add(log)
        await db_session.flush()
        assert log.interaction_type == "feeding"

    async def test_confession_log(self, db_session):
        log = InteractionLog(user_id="123456", interaction_type="confession")
        db_session.add(log)
        await db_session.flush()
        assert log.interaction_type == "confession"

    async def test_query_by_type(self, db_session):
        db_session.add(InteractionLog(user_id="1", interaction_type="feeding"))
        db_session.add(InteractionLog(user_id="1", interaction_type="confession"))
        db_session.add(InteractionLog(user_id="1", interaction_type="feeding"))
        await db_session.flush()

        result = await db_session.execute(
            select(InteractionLog).where(InteractionLog.interaction_type == "feeding")
        )
        assert len(result.scalars().all()) == 2


@pytest.mark.asyncio
class TestUserAffectionModel:
    async def test_create_affection(self, db_session):
        aff = UserAffection(user_id="123456", affection_points=50)
        db_session.add(aff)
        await db_session.flush()
        assert aff.affection_points == 50

    async def test_all_nullable_date_fields(self, db_session):
        aff = UserAffection(user_id="123456")
        db_session.add(aff)
        await db_session.flush()
        assert aff.last_update_date is None
        assert aff.last_interaction_date is None
        assert aff.last_gift_date is None


@pytest.mark.asyncio
class TestUserWarningRecordModel:
    async def test_create_warning(self, db_session):
        w = UserWarningRecord(user_id="123456", guild_id="789", warning_count=1)
        db_session.add(w)
        await db_session.flush()
        assert w.warning_count == 1

    async def test_unique_user_guild(self, db_session):
        db_session.add(
            UserWarningRecord(user_id="123456", guild_id="789", warning_count=1)
        )
        await db_session.flush()
        db_session.add(
            UserWarningRecord(user_id="123456", guild_id="789", warning_count=2)
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
class TestCoinLoanModel:
    async def test_create_loan(self, db_session):
        loan = CoinLoan(user_id="123456", amount=500, status="active")
        db_session.add(loan)
        await db_session.flush()
        assert loan.status == "active"
        assert loan.paid_at is None


@pytest.mark.asyncio
class TestSchemaAndIndexes:
    async def test_economy_schema_exists(self, db_session):
        result = await db_session.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'economy'"
            )
        )
        assert result.scalar() == "economy"

    async def test_user_schema_exists(self, db_session):
        result = await db_session.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'user'"
            )
        )
        assert result.scalar() == "user"

    async def test_user_coins_indexes(self, db_session):
        result = await db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'economy' AND tablename = 'user_coins'"
            )
        )
        index_names = [row[0] for row in result]
        assert "ix_coins_user_id" in index_names

    async def test_interaction_logs_indexes(self, db_session):
        result = await db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'economy' AND tablename = 'interaction_logs'"
            )
        )
        index_names = [row[0] for row in result]
        assert "ix_interact_user_type" in index_names

    async def test_warnings_unique_index(self, db_session):
        result = await db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'user' AND tablename = 'user_warnings'"
            )
        )
        index_names = [row[0] for row in result]
        assert "ix_warnings_user_guild" in index_names
