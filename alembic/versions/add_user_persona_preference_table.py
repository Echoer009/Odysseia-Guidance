"""add user persona preference table

Revision ID: add_user_persona_preference
Revises: add_economy_and_user_tables
Create Date: 2026-05-13

添加用户人设偏好表，存储每个用户对类脑娘人设风格的选择。

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "add_user_persona_preference"
down_revision: Union[str, Sequence[str], None] = "add_ai_config_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text('CREATE SCHEMA IF NOT EXISTS "user"'))

    op.execute(
        text("""
        CREATE TABLE "user".user_persona_preference (
            id SERIAL NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            persona_style VARCHAR(50) NOT NULL DEFAULT 'default',
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id),
            UNIQUE (user_id)
        )
    """)
    )

    op.execute(
        text(
            'CREATE INDEX ix_user_persona_preference_id ON "user".user_persona_preference (id)'
        )
    )


def downgrade() -> None:
    op.execute(
        text('DROP INDEX IF EXISTS "user".ix_user_persona_preference_id')
    )
    op.execute(text('DROP TABLE IF EXISTS "user".user_persona_preference'))
