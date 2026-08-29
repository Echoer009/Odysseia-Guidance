"""add ab_test schema and tables

Revision ID: 81ae9d79793e
Revises: add_content_filter_keywords
Create Date: 2026-08-29

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text
import sqlalchemy as sa


revision: str = "81ae9d79793e"
down_revision: Union[str, Sequence[str], None] = "add_content_filter_keywords"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text("CREATE SCHEMA IF NOT EXISTS ab_test"))

    op.create_table(
        "ab_experiments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        schema="ab_test",
    )

    op.create_table(
        "ab_arms",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("ab_test.ab_experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("model_full_id", sa.String(200), nullable=False),
        sa.Column("traffic_percent", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Index("ix_ab_arms_experiment_id", "experiment_id"),
        schema="ab_test",
    )

    op.create_table(
        "ab_routed_replies",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "experiment_id",
            sa.Integer(),
            sa.ForeignKey("ab_test.ab_experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "arm_id",
            sa.Integer(),
            sa.ForeignKey("ab_test.ab_arms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=True),
        sa.Column("trigger_user_id", sa.BigInteger(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("reply_text", sa.Text(), nullable=False),
        sa.Column("model_full_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Index("ix_ab_routed_replies_message_id", "message_id", unique=True),
        schema="ab_test",
    )

    op.create_table(
        "ab_votes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "reply_id",
            sa.BigInteger(),
            sa.ForeignKey("ab_test.ab_routed_replies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("voter_id", sa.BigInteger(), nullable=False),
        sa.Column("vote", sa.SmallInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("reply_id", "voter_id", name="uq_ab_votes_reply_voter"),
        schema="ab_test",
    )

    op.create_table(
        "ab_feedback",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "reply_id",
            sa.BigInteger(),
            sa.ForeignKey("ab_test.ab_routed_replies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("free_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        schema="ab_test",
    )


def downgrade() -> None:
    op.drop_table("ab_feedback", schema="ab_test")
    op.drop_table("ab_votes", schema="ab_test")
    op.drop_table("ab_routed_replies", schema="ab_test")
    op.drop_table("ab_arms", schema="ab_test")
    op.drop_table("ab_experiments", schema="ab_test")
    op.execute(text("DROP SCHEMA IF EXISTS ab_test"))
