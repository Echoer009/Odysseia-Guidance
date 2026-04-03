import sqlite3
import os
import pytest
from sqlalchemy import text

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chat.db")


def _get_sqlite_connection():
    if not os.path.exists(SQLITE_DB_PATH):
        pytest.skip("SQLite database not found at data/chat.db")
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.mark.asyncio
class TestMigrationRowCount:
    async def test_user_coins_count(self, clean_economy_tables):
        session = clean_economy_tables
        conn = _get_sqlite_connection()
        try:
            sqlite_count = conn.execute("SELECT COUNT(*) FROM user_coins").fetchone()[0]
            pg_count = session.execute(
                text("SELECT COUNT(*) FROM economy.user_coins")
            ).scalar()
            assert sqlite_count == pg_count
        finally:
            conn.close()

    async def test_coin_transactions_count(self, clean_economy_tables):
        session = clean_economy_tables
        conn = _get_sqlite_connection()
        try:
            sqlite_count = conn.execute(
                "SELECT COUNT(*) FROM coin_transactions"
            ).fetchone()[0]
            pg_count = session.execute(
                text("SELECT COUNT(*) FROM economy.coin_transactions")
            ).scalar()
            assert sqlite_count == pg_count
        finally:
            conn.close()

    async def test_interaction_logs_merged_count(self, clean_economy_tables):
        session = clean_economy_tables
        conn = _get_sqlite_connection()
        try:
            feed_count = conn.execute("SELECT COUNT(*) FROM feeding_log").fetchone()[0]
            confess_count = conn.execute(
                "SELECT COUNT(*) FROM confession_log"
            ).fetchone()[0]
            pg_count = session.execute(
                text("SELECT COUNT(*) FROM economy.interaction_logs")
            ).scalar()
            assert feed_count + confess_count == pg_count
        finally:
            conn.close()

    async def test_user_profiles_count(self, clean_economy_tables):
        session = clean_economy_tables
        conn = _get_sqlite_connection()
        try:
            sqlite_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            pg_count = session.execute(
                text("SELECT COUNT(*) FROM user.user_profiles")
            ).scalar()
            assert sqlite_count == pg_count
        finally:
            conn.close()

    async def test_user_affection_count(self, clean_economy_tables):
        session = clean_economy_tables
        conn = _get_sqlite_connection()
        try:
            sqlite_count = conn.execute("SELECT COUNT(*) FROM ai_affection").fetchone()[
                0
            ]
            pg_count = session.execute(
                text("SELECT COUNT(*) FROM user.user_affection")
            ).scalar()
            assert sqlite_count == pg_count
        finally:
            conn.close()


@pytest.mark.asyncio
class TestMigrationDataIntegrity:
    async def test_total_balance_consistent(self, clean_economy_tables):
        session = clean_economy_tables
        conn = _get_sqlite_connection()
        try:
            sqlite_total = (
                conn.execute("SELECT SUM(balance) FROM user_coins").fetchone()[0] or 0
            )
            pg_total = (
                session.execute(
                    text("SELECT SUM(balance) FROM economy.user_coins")
                ).scalar()
                or 0
            )
            assert sqlite_total == pg_total
        finally:
            conn.close()

    async def test_random_user_balance(self, clean_economy_tables):
        session = clean_economy_tables
        conn = _get_sqlite_connection()
        try:
            sqlite_rows = conn.execute(
                "SELECT user_id, balance FROM user_coins ORDER BY RANDOM() LIMIT 10"
            ).fetchall()
            for user_id, balance in sqlite_rows:
                pg_balance = session.execute(
                    text("SELECT balance FROM economy.user_coins WHERE user_id = :uid"),
                    {"uid": str(user_id)},
                ).scalar()
                assert pg_balance == balance, (
                    f"user_id={user_id}: SQLite={balance}, PG={pg_balance}"
                )
        finally:
            conn.close()

    async def test_affection_points_consistent(self, clean_economy_tables):
        session = clean_economy_tables
        conn = _get_sqlite_connection()
        try:
            sqlite_rows = conn.execute(
                "SELECT user_id, affection_points FROM ai_affection"
            ).fetchall()
            for user_id, points in sqlite_rows:
                pg_points = session.execute(
                    text(
                        "SELECT affection_points FROM user.user_affection WHERE user_id = :uid"
                    ),
                    {"uid": str(user_id)},
                ).scalar()
                assert pg_points == points
        finally:
            conn.close()
