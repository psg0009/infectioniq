"""Add supabase_id column to users

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7g8h9i0"
down_revision = "c4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("supabase_id", sa.String(255), nullable=True))
    op.create_index("ix_users_supabase_id", "users", ["supabase_id"], unique=True)


def downgrade():
    op.drop_index("ix_users_supabase_id", table_name="users")
    op.drop_column("users", "supabase_id")
