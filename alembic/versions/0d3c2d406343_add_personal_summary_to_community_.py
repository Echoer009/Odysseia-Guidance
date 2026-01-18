"""add personal summary to community member profiles

Revision ID: 0d3c2d406343
Revises: 696a5de05b3f
Create Date: 2026-01-18 06:07:21.516141

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0d3c2d406343"
down_revision: Union[str, Sequence[str], None] = "fe7cfa779ace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "member_profiles",
        sa.Column(
            "personal_summary", sa.Text(), nullable=True, comment="成员的个人记忆摘要"
        ),
        schema="community",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("member_profiles", "personal_summary", schema="community")
