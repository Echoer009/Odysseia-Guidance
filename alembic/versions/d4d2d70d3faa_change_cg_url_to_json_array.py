"""change_cg_url_to_json_array

Revision ID: d4d2d70d3faa
Revises: add_user_tool_settings
Create Date: 2026-02-10 15:44:06.504861

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4d2d70d3faa"
down_revision: Union[str, Sequence[str], None] = "add_user_tool_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 先清空 cg_url 字段
    op.execute("UPDATE shop.shop_items SET cg_url = NULL")

    # 使用原生 SQL 修改列类型，添加 USING 子句处理类型转换
    op.execute(
        "ALTER TABLE shop.shop_items ALTER COLUMN cg_url TYPE JSON USING '{}'::json"
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 将 cg_url 字段从 JSON 改回 String(1000) 类型
    op.alter_column(
        "shop_items",
        "cg_url",
        existing_type=postgresql.JSON(),
        type_=sa.String(1000),
        nullable=True,
        schema="shop",
    )
