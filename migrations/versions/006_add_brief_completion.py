"""Add completion field to briefs table

Revision ID: 006
Revises: 005
Create Date: 2025-11-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add completion field to briefs table for T6.1

    completion: 0 = не пройден, 1 = пройден
    """
    # Add completion column with default value 0
    op.add_column(
        'briefs',
        sa.Column('completion', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    """Remove completion field"""
    op.drop_column('briefs', 'completion')
