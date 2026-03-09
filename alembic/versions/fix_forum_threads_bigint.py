"""fix_forum_threads_bigint

Revision ID: fix_forum_threads_bigint
Revises: add_forum_threads
Create Date: 2026-03-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "fix_forum_threads_bigint"
down_revision: Union[str, Sequence[str], None] = "add_forum_threads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - change INTEGER to BIGINT for Discord IDs"""
    # 由于表已经存在，只需要修改列类型
    op.execute(
        text("""
        ALTER TABLE forum.forum_threads
        ALTER COLUMN thread_id TYPE BIGINT
    """)
    )
    op.execute(
        text("""
        ALTER TABLE forum.forum_threads
        ALTER COLUMN author_id TYPE BIGINT
    """)
    )
    op.execute(
        text("""
        ALTER TABLE forum.forum_threads
        ALTER COLUMN channel_id TYPE BIGINT
    """)
    )
    op.execute(
        text("""
        ALTER TABLE forum.forum_threads
        ALTER COLUMN guild_id TYPE BIGINT
    """)
    )


def downgrade() -> None:
    """Downgrade schema"""
    op.execute(
        text("""
        ALTER TABLE forum.forum_threads
        ALTER COLUMN thread_id TYPE INTEGER
    """)
    )
    op.execute(
        text("""
        ALTER TABLE forum.forum_threads
        ALTER COLUMN author_id TYPE INTEGER
    """)
    )
    op.execute(
        text("""
        ALTER TABLE forum.forum_threads
        ALTER COLUMN channel_id TYPE INTEGER
    """)
    )
    op.execute(
        text("""
        ALTER TABLE forum.forum_threads
        ALTER COLUMN guild_id TYPE INTEGER
    """)
    )
