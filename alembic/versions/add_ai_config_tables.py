"""add ai_config schema and ai_providers/ai_models tables

Revision ID: add_ai_config_tables
Revises: add_conversation_blocks, add_economy_and_user_tables, add_thread_name_bm25
Create Date: 2026-04-30

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "add_ai_config_tables"
down_revision: Union[str, Sequence[str], None] = (
    "add_conversation_blocks",
    "add_economy_and_user_tables",
    "add_thread_name_bm25",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("CREATE SCHEMA IF NOT EXISTS ai_config"))

    op.execute(
        text("""
        CREATE TABLE ai_config.ai_providers (
            id BIGSERIAL NOT NULL,
            name VARCHAR(100) NOT NULL,
            provider_type VARCHAR(50) NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            api_key_encrypted TEXT NOT NULL,
            base_url TEXT,
            extra JSON,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        text("CREATE UNIQUE INDEX ix_ai_provider_name ON ai_config.ai_providers (name)")
    )

    op.execute(
        text("""
        CREATE TABLE ai_config.ai_models (
            id BIGSERIAL NOT NULL,
            model_name VARCHAR(200) NOT NULL,
            display_name VARCHAR(200) NOT NULL,
            provider_id BIGINT NOT NULL,
            actual_model VARCHAR(200) NOT NULL,
            description TEXT,
            supports_vision INTEGER NOT NULL DEFAULT 0,
            supports_tools INTEGER NOT NULL DEFAULT 1,
            supports_thinking INTEGER NOT NULL DEFAULT 0,
            max_output_tokens INTEGER NOT NULL DEFAULT 8192,
            generation_config JSON,
            prompt_config JSON,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id),
            FOREIGN KEY (provider_id) REFERENCES ai_config.ai_providers (id)
        )
    """)
    )
    op.execute(
        text("CREATE UNIQUE INDEX ix_ai_model_name ON ai_config.ai_models (model_name)")
    )
    op.execute(
        text("CREATE INDEX ix_ai_model_provider ON ai_config.ai_models (provider_id)")
    )


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS ai_config.ai_models"))
    op.execute(text("DROP TABLE IF EXISTS ai_config.ai_providers"))
    op.execute(text("DROP SCHEMA IF EXISTS ai_config"))
