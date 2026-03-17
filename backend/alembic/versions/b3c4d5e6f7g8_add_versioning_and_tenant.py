"""add_versioning_and_tenant

Revision ID: b3c4d5e6f7g8
Revises: a2b3c4d5e6f7
Create Date: 2026-02-13 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b3c4d5e6f7g8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_ORG_ID = '00000000-0000-0000-0000-000000000001'


def upgrade() -> None:
    # --- Organizations table ---
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('slug', sa.String(100), nullable=False, unique=True),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('settings', sa.Text(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'])

    # Insert default organization
    op.execute(
        f"INSERT INTO organizations (id, name, slug, is_active, settings) "
        f"VALUES ('{DEFAULT_ORG_ID}', 'Default Organization', 'default', 1, '{{}}')"
    )

    # --- GestureProfile versioning ---
    op.add_column('gesture_profiles', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('gesture_profiles', sa.Column('calibration_session_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_gesture_profiles_cal_session', 'gesture_profiles',
        'gesture_calibration_sessions', ['calibration_session_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_gesture_profiles_name_version', 'gesture_profiles', ['name', 'version'])

    # --- SurgicalCase → GestureProfile FK ---
    op.add_column('surgical_cases', sa.Column('gesture_profile_id', sa.String(36), nullable=True))
    op.create_foreign_key(
        'fk_surgical_cases_gesture_profile', 'surgical_cases',
        'gesture_profiles', ['gesture_profile_id'], ['id']
    )

    # --- organization_id on tenant-scoped tables ---
    for table in ['users', 'staff', 'surgical_cases', 'gesture_profiles', 'gesture_calibration_sessions']:
        op.add_column(table, sa.Column('organization_id', sa.String(36), nullable=True))
        op.create_foreign_key(
            f'fk_{table}_organization', table,
            'organizations', ['organization_id'], ['id']
        )
        op.create_index(f'ix_{table}_organization_id', table, ['organization_id'])


def downgrade() -> None:
    for table in ['gesture_calibration_sessions', 'gesture_profiles', 'surgical_cases', 'staff', 'users']:
        op.drop_index(f'ix_{table}_organization_id', table)
        op.drop_constraint(f'fk_{table}_organization', table, type_='foreignkey')
        op.drop_column(table, 'organization_id')

    op.drop_constraint('fk_surgical_cases_gesture_profile', 'surgical_cases', type_='foreignkey')
    op.drop_column('surgical_cases', 'gesture_profile_id')

    op.drop_index('ix_gesture_profiles_name_version', 'gesture_profiles')
    op.drop_constraint('fk_gesture_profiles_cal_session', 'gesture_profiles', type_='foreignkey')
    op.drop_column('gesture_profiles', 'calibration_session_id')
    op.drop_column('gesture_profiles', 'version')

    op.drop_index('ix_organizations_slug', 'organizations')
    op.drop_table('organizations')
