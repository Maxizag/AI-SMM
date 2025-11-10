"""Add scraping_jobs table for async content scraping

Revision ID: 004
Revises: 003
Create Date: 2025-11-10 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create scraping_jobs table
    op.create_table(
        'scraping_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='queued'),
        sa.Column('target_posts', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('min_posts', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('total_collected', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'running', 'done', 'partial', 'error')", name='check_job_status'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(op.f('ix_scraping_jobs_user_id'), 'scraping_jobs', ['user_id'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_status'), 'scraping_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_scraping_jobs_created_at'), 'scraping_jobs', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_scraping_jobs_created_at'), table_name='scraping_jobs')
    op.drop_index(op.f('ix_scraping_jobs_status'), table_name='scraping_jobs')
    op.drop_index(op.f('ix_scraping_jobs_user_id'), table_name='scraping_jobs')

    # Drop table
    op.drop_table('scraping_jobs')
