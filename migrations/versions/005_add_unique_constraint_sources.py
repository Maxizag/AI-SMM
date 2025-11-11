"""Add unique constraint on sources (user_id, url)

Revision ID: 005
Revises: 004
Create Date: 2025-11-11 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add unique constraint on (user_id, url) to prevent duplicate sources

    Note: This will fail if there are existing duplicates in the database.
    If you have duplicates, clean them up first:

    DELETE FROM sources s1
    USING sources s2
    WHERE s1.id > s2.id
    AND s1.user_id = s2.user_id
    AND s1.url = s2.url;
    """
    # Add unique constraint on (user_id, url)
    op.create_unique_constraint(
        'uniq_user_url',
        'sources',
        ['user_id', 'url']
    )


def downgrade() -> None:
    """Remove unique constraint"""
    op.drop_constraint('uniq_user_url', 'sources', type_='unique')
