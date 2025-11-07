"""Add briefs and style_seed tables, update sources

Revision ID: 002
Revises: 001
Create Date: 2025-11-05 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update sources table: remove 'text' column, add 'url' column
    op.drop_column('sources', 'text')
    op.add_column('sources', sa.Column('url', sa.Text(), nullable=True))
    op.alter_column('sources', 'platform',
                    existing_type=sa.String(length=100),
                    type_=sa.Text(),
                    nullable=True)

    # Create briefs table
    op.create_table(
        'briefs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('audience', sa.Text(), nullable=True),
        sa.Column('tone', sa.Text(), nullable=True),
        sa.Column('topic', sa.Text(), nullable=True),
        sa.Column('frequency', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_briefs_user_id'), 'briefs', ['user_id'], unique=False)

    # Create style_seed table
    op.create_table(
        'style_seed',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tone', sa.Text(), nullable=True),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('topic', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_style_seed_user_id'), 'style_seed', ['user_id'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_index(op.f('ix_style_seed_user_id'), table_name='style_seed')
    op.drop_table('style_seed')

    op.drop_index(op.f('ix_briefs_user_id'), table_name='briefs')
    op.drop_table('briefs')

    # Revert sources table changes
    op.alter_column('sources', 'platform',
                    existing_type=sa.Text(),
                    type_=sa.String(length=100),
                    nullable=False)
    op.drop_column('sources', 'url')
    op.add_column('sources', sa.Column('text', sa.Text(), nullable=False))
