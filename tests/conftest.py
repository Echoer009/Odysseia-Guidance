import os
import sys

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

_TEST_DATABASE_URL = os.getenv("DATABASE_URL")

if not _TEST_DATABASE_URL:
    _db_user = os.getenv("POSTGRES_USER", "user")
    _db_password = os.getenv("POSTGRES_PASSWORD", "password")
    _db_name = os.getenv("POSTGRES_DB", "bot_db")
    _db_port = os.getenv("DB_PORT", "5432")
    _db_host = os.getenv("DB_HOST", "db") if os.getenv("RUNNING_IN_DOCKER") else os.getenv("DB_HOST", "localhost")
    _TEST_DATABASE_URL = (
        f"postgresql+asyncpg://{_db_user}:{_db_password}"
        f"@{_db_host}:{_db_port}/{_db_name}"
    )

_test_engine = create_async_engine(_TEST_DATABASE_URL, echo=False, poolclass=NullPool)
_TestSessionFactory = async_sessionmaker(_test_engine, expire_on_commit=False)

ECONOMY_TABLES = [
    "economy.user_coins",
    "economy.coin_transactions",
    "economy.coin_loans",
    "economy.interaction_logs",
]

USER_TABLES = [
    "user.user_affection",
    "user.user_warnings",
    "user.user_persona_preference",
]

_ALL_TABLES = ECONOMY_TABLES + USER_TABLES


async def _truncate_all():
    table_refs = ", ".join(
        f'"{schema}"."{name}"'
        for t in _ALL_TABLES
        for schema, name in [t.split(".", 1)]
    )
    async with _TestSessionFactory() as session:
        await session.execute(text(f"TRUNCATE TABLE {table_refs} CASCADE"))
        await session.commit()


@pytest_asyncio.fixture
async def db_session():
    await _truncate_all()
    async with _TestSessionFactory() as session:
        async with session.begin():
            yield session
    await _truncate_all()


@pytest_asyncio.fixture
async def clean_tables():
    await _truncate_all()
    yield
    await _truncate_all()


@pytest.fixture
def coin_svc():
    from src.chat.features.odysseia_coin.service.coin_service import CoinService

    return CoinService()


@pytest.fixture
def aff_svc():
    from unittest.mock import patch, MagicMock

    mock_levels = [
        {
            "id": "lv0",
            "min_affection": 0,
            "max_affection": 19,
            "level_name": "陌生",
            "prompt": "...",
        },
        {
            "id": "lv1",
            "min_affection": 20,
            "max_affection": 49,
            "level_name": "熟悉",
            "prompt": "...",
        },
        {
            "id": "lv2",
            "min_affection": 50,
            "max_affection": 99,
            "level_name": "亲密",
            "prompt": "...",
        },
    ]

    with (
        patch("builtins.open", MagicMock()),
        patch("yaml.safe_load", return_value=mock_levels),
    ):
        from src.chat.features.affection.service.affection_service import (
            AffectionService,
        )

        svc = AffectionService()
        svc.affection_levels = mock_levels
        return svc


@pytest.fixture
def feeding_svc():
    from unittest.mock import AsyncMock
    from src.chat.features.affection.service.feeding_service import FeedingService

    svc = FeedingService()
    svc.db_manager = AsyncMock()
    return svc


@pytest.fixture
def confession_svc():
    from unittest.mock import AsyncMock
    from src.chat.features.affection.service.confession_service import ConfessionService

    svc = ConfessionService()
    svc.db_manager = AsyncMock()
    return svc
