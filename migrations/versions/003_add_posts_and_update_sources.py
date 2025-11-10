"""Add posts table and update sources for content scraping

Revision ID: 003
Revises: 002
Create Date: 2025-11-10 06:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update sources table for content scraping functionality

    # Change platform from Text to String(50) and make NOT NULL
    # First set default for existing rows, then make NOT NULL
    op.execute("UPDATE sources SET platform = 'telegram' WHERE platform IS NULL")
    op.alter_column('sources', 'platform',
                    existing_type=sa.Text(),
                    type_=sa.String(length=50),
                    nullable=False)

    # Make url NOT NULL (set default for existing rows first)
    op.execute("UPDATE sources SET url = '' WHERE url IS NULL")
    op.alter_column('sources', 'url',
                    existing_type=sa.Text(),
                    nullable=False)

    # Add new columns to sources
    op.add_column('sources', sa.Column('handle', sa.Text(), nullable=True))
    op.add_column('sources', sa.Column('is_private', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('sources', sa.Column('post_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('sources', sa.Column('status', sa.String(length=20), nullable=False, server_default='new'))
    op.add_column('sources', sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('sources', sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))

    # Add check constraint for platform
    op.create_check_constraint(
        'check_platform',
        'sources',
        "platform IN ('telegram', 'vk', 'instagram')"
    )

    # Create posts table
    op.create_table(
        'posts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('platform_post_id', sa.Text(), nullable=False),
        sa.Column('author_handle', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('media', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reactions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('link', sa.Text(), nullable=True),
        sa.Column('lang', sa.String(length=10), nullable=True),
        sa.Column('qdrant_point_id', sa.Text(), nullable=True),
        sa.Column('raw', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("platform IN ('telegram', 'vk', 'instagram')", name='check_post_platform'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for posts table
    op.create_index(op.f('ix_posts_user_id'), 'posts', ['user_id'], unique=False)
    op.create_index(op.f('ix_posts_source_id'), 'posts', ['source_id'], unique=False)

    # Create unique constraint on source_id + platform_post_id to prevent duplicates
    op.create_index('ix_posts_source_platform_post', 'posts', ['source_id', 'platform_post_id'], unique=True)


def downgrade() -> None:
    # Drop posts table
    op.drop_index('ix_posts_source_platform_post', table_name='posts')
    op.drop_index(op.f('ix_posts_source_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_user_id'), table_name='posts')
    op.drop_table('posts')

    # Remove new columns from sources
    op.drop_constraint('check_platform', 'sources', type_='check')
    op.drop_column('sources', 'updated_at')
    op.drop_column('sources', 'meta')
    op.drop_column('sources', 'status')
    op.drop_column('sources', 'post_count')
    op.drop_column('sources', 'is_private')
    op.drop_column('sources', 'handle')

    # Revert sources table changes
    op.alter_column('sources', 'url',
                    existing_type=sa.Text(),
                    nullable=True)
    op.alter_column('sources', 'platform',
                    existing_type=sa.String(length=50),
                    type_=sa.Text(),
                    nullable=True)
