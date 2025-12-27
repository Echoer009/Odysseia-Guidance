"""Add author_id and thread_id to TutorialDocument

Revision ID: 88ba317c09e7
Revises: 43ecab4319d0
Create Date: 2025-12-25 15:11:09.645694

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "88ba317c09e7"
down_revision: Union[str, Sequence[str], None] = "43ecab4319d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "tutorial_documents",
        sa.Column(
            "author_id", sa.String(), nullable=True, comment="作者的Discord用户ID。"
        ),
        schema="tutorials",
    )
    op.add_column(
        "tutorial_documents",
        sa.Column(
            "thread_id", sa.String(), nullable=True, comment="原始Discord帖子的ID。"
        ),
        schema="tutorials",
    )
    op.create_index(
        "ix_tutorial_documents_author_id",
        "tutorial_documents",
        ["author_id"],
        unique=False,
        schema="tutorials",
    )

    # 将 author_id 设为非空，并从 author 列填充数据
    op.execute("""
    UPDATE tutorials.tutorial_documents
    SET author_id = author
    WHERE author IS NOT NULL;
    """)
    op.alter_column(
        "tutorial_documents", "author_id", nullable=False, schema="tutorials"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_tutorial_documents_author_id",
        table_name="tutorial_documents",
        schema="tutorials",
    )
    op.drop_column("tutorial_documents", "thread_id", schema="tutorials")
    op.drop_column("tutorial_documents", "author_id", schema="tutorials")
