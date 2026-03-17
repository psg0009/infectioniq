"""add_gesture_and_validation_tables

Revision ID: a2b3c4d5e6f7
Revises: 1fc6fa33b536
Create Date: 2026-02-13 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '1fc6fa33b536'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Gesture profiles (per-camera/OR gesture thresholds)
    op.create_table(
        'gesture_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('palm_distance_threshold', sa.Float(), server_default='0.15'),
        sa.Column('palm_variance_threshold', sa.Float(), server_default='0.001'),
        sa.Column('motion_threshold', sa.Float(), server_default='0.02'),
        sa.Column('oscillation_threshold', sa.Integer(), server_default='4'),
        sa.Column('score_threshold', sa.Float(), server_default='0.7'),
        sa.Column('min_duration_sec', sa.Float(), server_default='3.0'),
        sa.Column('weight_palm_close', sa.Float(), server_default='0.3'),
        sa.Column('weight_palm_variance', sa.Float(), server_default='0.2'),
        sa.Column('weight_motion', sa.Float(), server_default='0.2'),
        sa.Column('weight_oscillation', sa.Float(), server_default='0.3'),
        sa.Column('is_default', sa.Boolean(), server_default='0'),
        sa.Column('or_number', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Gesture calibration sessions
    op.create_table(
        'gesture_calibration_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('or_number', sa.String(length=20), nullable=True),
        sa.Column('observer_name', sa.String(length=255), nullable=True),
        sa.Column('glove_type', sa.String(length=100), nullable=True),
        sa.Column('dispenser_type', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('total_samples', sa.Integer(), server_default='0'),
        sa.Column('sanitizing_count', sa.Integer(), server_default='0'),
        sa.Column('not_sanitizing_count', sa.Integer(), server_default='0'),
        sa.Column('best_accuracy', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Gesture calibration samples
    op.create_table(
        'gesture_calibration_samples',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('label', sa.String(length=20), nullable=False),
        sa.Column('palm_distance', sa.Float(), nullable=False),
        sa.Column('palm_distance_var', sa.Float(), server_default='0.0'),
        sa.Column('avg_motion', sa.Float(), nullable=False),
        sa.Column('oscillation_count', sa.Integer(), nullable=False),
        sa.Column('score', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['gesture_calibration_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Validation sessions
    op.create_table(
        'validation_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('case_id', sa.String(length=36), nullable=False),
        sa.Column('observer_name', sa.String(length=255), nullable=False),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['surgical_cases.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Validation observations (with system_gesture_score column)
    op.create_table(
        'validation_observations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('observed_compliant', sa.Boolean(), nullable=False),
        sa.Column('system_compliant', sa.Boolean(), nullable=True),
        sa.Column('system_gesture_score', sa.Float(), nullable=True),
        sa.Column('staff_id', sa.String(length=36), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['validation_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('validation_observations')
    op.drop_table('validation_sessions')
    op.drop_table('gesture_calibration_samples')
    op.drop_table('gesture_calibration_sessions')
    op.drop_table('gesture_profiles')
