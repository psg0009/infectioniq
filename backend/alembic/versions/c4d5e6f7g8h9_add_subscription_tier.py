"""Add subscription tier and max_ors to users

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-03-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "c4d5e6f7g8h9"
down_revision = "b3c4d5e6f7g8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "subscription_tier",
            sa.Enum("STARTER", "PROFESSIONAL", "ENTERPRISE", "TRIAL", name="subscriptiontier"),
            nullable=False,
            server_default="TRIAL",
        ),
    )
    op.add_column(
        "users",
        sa.Column("max_ors", sa.Integer(), nullable=False, server_default="2"),
    )


def downgrade() -> None:
    op.drop_column("users", "max_ors")
    op.drop_column("users", "subscription_tier")
