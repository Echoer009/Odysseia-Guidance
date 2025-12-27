"""Set server_default for timestamps on tutorial tables

Revision ID: ec507c9addb9
Revises: 88ba317c09e7
Create Date: 2025-12-25 09:26:12.238585

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ec507c9addb9"
down_revision: Union[str, Sequence[str], None] = "88ba317c09e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### 手动修复Alembic脚本 ###

    # 步骤1: 更新现有数据，将所有NULL的时间戳设置为当前时间
    op.execute(
        sa.text("""
        UPDATE tutorials.tutorial_documents
        SET created_at = NOW()
        WHERE created_at IS NULL;
    """)
    )
    op.execute(
        sa.text("""
        UPDATE tutorials.tutorial_documents
        SET updated_at = NOW()
        WHERE updated_at IS NULL;
    """)
    )
    op.execute(
        sa.text("""
        UPDATE tutorials.knowledge_chunks
        SET created_at = NOW()
        WHERE created_at IS NULL;
    """)
    )
    op.execute(
        sa.text("""
        UPDATE tutorials.knowledge_chunks
        SET updated_at = NOW()
        WHERE updated_at IS NULL;
    """)
    )

    # 步骤2: 在数据修复后，安全地应用 server_default 和 NOT NULL 约束
    op.alter_column(
        "tutorial_documents",
        "created_at",
        existing_type=sa.DateTime(),
        server_default=sa.text("now()"),
        nullable=False,
        schema="tutorials",
    )
    op.alter_column(
        "tutorial_documents",
        "updated_at",
        existing_type=sa.DateTime(),
        server_default=sa.text("now()"),
        nullable=False,
        schema="tutorials",
    )

    op.alter_column(
        "knowledge_chunks",
        "created_at",
        existing_type=sa.DateTime(),
        server_default=sa.text("now()"),
        nullable=False,
        schema="tutorials",
    )
    op.alter_column(
        "knowledge_chunks",
        "updated_at",
        existing_type=sa.DateTime(),
        server_default=sa.text("now()"),
        nullable=False,
        schema="tutorials",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### 手动修复Alembic脚本 ###

    # 移除 knowledge_chunks 表的 server_default
    op.alter_column(
        "knowledge_chunks",
        "updated_at",
        existing_type=sa.DateTime(),
        server_default=None,
        nullable=True,
        schema="tutorials",
    )
    op.alter_column(
        "knowledge_chunks",
        "created_at",
        existing_type=sa.DateTime(),
        server_default=None,
        nullable=True,
        schema="tutorials",
    )

    # 移除 tutorial_documents 表的 server_default
    op.alter_column(
        "tutorial_documents",
        "updated_at",
        existing_type=sa.DateTime(),
        server_default=None,
        nullable=True,
        schema="tutorials",
    )
    op.alter_column(
        "tutorial_documents",
        "created_at",
        existing_type=sa.DateTime(),
        server_default=None,
        nullable=True,
        schema="tutorials",
    )
    # ### end Alembic commands ###
