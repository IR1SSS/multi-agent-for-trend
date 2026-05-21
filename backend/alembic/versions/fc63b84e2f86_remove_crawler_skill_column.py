"""remove_crawler_skill_column

Revision ID: fc63b84e2f86
Revises: 942701524c78
Create Date: 2026-05-22 00:31:47.391651
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'fc63b84e2f86'
down_revision: Union[str, None] = '942701524c78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('domain_configs', 'crawler_skill')


def downgrade() -> None:
    op.add_column(
        'domain_configs',
        sa.Column('crawler_skill', sa.JSON(), nullable=True, comment='Crawler skill config: target_platforms, concurrency_limit, crawl_speed, platform_weights'),
    )
