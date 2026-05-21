"""add_domain_description_column

Revision ID: 942701524c78
Revises: a1b2c3d4e5f6
Create Date: 2026-05-22 00:04:52.229338
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '942701524c78'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'domain_configs',
        sa.Column('domain_description', sa.Text(), nullable=False, server_default='', comment='Natural language description of the domain for LLM-based skill inference'),
    )


def downgrade() -> None:
    op.drop_column('domain_configs', 'domain_description')
