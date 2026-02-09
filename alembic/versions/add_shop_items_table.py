"""add_shop_items_table

Revision ID: add_shop_items
Revises: fe7cfa779ace
Create Date: 2026-02-06 14:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "add_shop_items"
down_revision: Union[str, Sequence[str], None] = "fe7cfa779ace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 创建 shop schema
    op.execute("CREATE SCHEMA IF NOT EXISTS shop;")

    # 创建 shop_items 表
    op.create_table(
        "shop_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("target", sa.String(50), nullable=False, server_default="self"),
        sa.Column("effect_id", sa.String(100), nullable=True),
        sa.Column("cg_url", sa.String(1000), nullable=True),
        sa.Column("is_available", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        schema="shop",
    )

    # 创建索引
    op.create_index(
        op.f("ix_shop_shop_items_id"), "shop_items", ["id"], unique=False, schema="shop"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 删除索引
    op.drop_index(op.f("ix_shop_shop_items_id"), table_name="shop_items", schema="shop")

    # 删除表
    op.drop_table("shop_items", schema="shop")

    # 删除 schema
    op.execute("DROP SCHEMA IF EXISTS shop;")
