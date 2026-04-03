"""add economy and user tables

Revision ID: add_economy_and_user_tables
Revises: add_user_command_settings
Create Date: 2026-04-02

添加 economy schema 和 user schema 扩展表，
用于从 SQLite 迁移类脑币经济系统和用户相关数据。

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "add_economy_and_user_tables"
down_revision: Union[str, Sequence[str], None] = "add_user_command_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text('CREATE SCHEMA IF NOT EXISTS "economy"'))
    op.execute(text('CREATE SCHEMA IF NOT EXISTS "user"'))

    op.execute(
        text("""
        CREATE TABLE economy.user_coins (
            id BIGSERIAL NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            balance INTEGER DEFAULT 0,
            last_daily_message_date VARCHAR(20),
            last_red_envelope_date VARCHAR(20),
            coffee_effect_expires_at TIMESTAMP WITHOUT TIME ZONE,
            has_withered_sunflower INTEGER DEFAULT NULL,
            blocks_thread_replies INTEGER DEFAULT 0,
            thread_cooldown_seconds INTEGER,
            thread_cooldown_duration INTEGER,
            thread_cooldown_limit INTEGER,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        text("CREATE UNIQUE INDEX ix_coins_user_id ON economy.user_coins (user_id)")
    )

    op.execute(
        text("""
        CREATE TABLE economy.coin_transactions (
            id BIGSERIAL NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            amount INTEGER NOT NULL,
            reason VARCHAR(255) NOT NULL,
            timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        text("CREATE INDEX ix_tx_user_id ON economy.coin_transactions (user_id)")
    )
    op.execute(
        text("CREATE INDEX ix_tx_timestamp ON economy.coin_transactions (timestamp)")
    )

    op.execute(
        text("""
        CREATE TABLE economy.coin_loans (
            id BIGSERIAL NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            amount INTEGER NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            paid_at TIMESTAMP WITHOUT TIME ZONE,
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(text("CREATE INDEX ix_loans_user ON economy.coin_loans (user_id)"))

    op.execute(
        text("""
        CREATE TABLE economy.interaction_logs (
            id BIGSERIAL NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            interaction_type VARCHAR(20) NOT NULL,
            timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        text(
            "CREATE INDEX ix_interact_user_type ON economy.interaction_logs (user_id, interaction_type)"
        )
    )

    op.execute(
        text("""
        CREATE TABLE "user".user_affection (
            id BIGSERIAL NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            affection_points INTEGER DEFAULT 0,
            daily_affection_gain INTEGER DEFAULT 0,
            last_update_date VARCHAR(20),
            last_interaction_date VARCHAR(20),
            last_gift_date VARCHAR(20),
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        text(
            'CREATE UNIQUE INDEX ix_affection_user_id ON "user".user_affection (user_id)'
        )
    )

    op.execute(
        text("""
        CREATE TABLE "user".user_warnings (
            id BIGSERIAL NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            guild_id VARCHAR(50) NOT NULL,
            warning_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        text(
            'CREATE UNIQUE INDEX ix_warnings_user_guild ON "user".user_warnings (user_id, guild_id)'
        )
    )


def downgrade() -> None:
    op.execute(text('DROP TABLE IF EXISTS "user".user_warnings'))
    op.execute(text('DROP TABLE IF EXISTS "user".user_affection'))
    op.execute(text("DROP TABLE IF EXISTS economy.interaction_logs"))
    op.execute(text("DROP TABLE IF EXISTS economy.coin_loans"))
    op.execute(text("DROP TABLE IF EXISTS economy.coin_transactions"))
    op.execute(text("DROP TABLE IF EXISTS economy.user_coins"))
    op.execute(text('DROP SCHEMA IF EXISTS "economy"'))
