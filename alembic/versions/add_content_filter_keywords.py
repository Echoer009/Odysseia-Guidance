"""add content_filter schema and keywords table

Revision ID: add_content_filter_keywords
Revises: add_user_memory_notes
Create Date: 2026-06-04

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "add_content_filter_keywords"
down_revision: Union[str, Sequence[str], None] = "add_user_memory_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("CREATE SCHEMA IF NOT EXISTS content_filter"))

    op.execute(
        text("""
        CREATE TABLE content_filter.content_filter_keywords (
            id BIGSERIAL NOT NULL,
            keyword VARCHAR(100) NOT NULL,
            is_ignored INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)
    )
    op.execute(
        text(
            "CREATE UNIQUE INDEX ix_cf_keyword_unique ON content_filter.content_filter_keywords (keyword)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ix_cf_keyword_ignored ON content_filter.content_filter_keywords (is_ignored)"
        )
    )


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS content_filter.content_filter_keywords"))
    op.execute(text("DROP SCHEMA IF EXISTS content_filter"))
