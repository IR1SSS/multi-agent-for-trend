"""add domain_config and domain_id

Revision ID: a1b2c3d4e5f6
Revises: b31ce6892e4b
Create Date: 2026-05-21 12:00:00.000000

Adds:
1. domain_configs table
2. domain_id column to trend_keywords, crawl_tasks, cleaned_trend_data
3. Seeds beauty domain configuration
4. Backfills domain_id for existing data
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'b31ce6892e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create domain_configs table
    op.create_table(
        'domain_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('domain', sa.String(length=64), nullable=False, comment="Unique domain identifier"),
        sa.Column('display_name', sa.String(length=128), nullable=False, comment="Human-readable domain name"),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='active', comment="Status: active / archived"),
        sa.Column('expander_skill', sa.JSON(), nullable=True, comment="Expander skill config"),
        sa.Column('crawler_skill', sa.JSON(), nullable=True, comment="Crawler skill config"),
        sa.Column('cleaning_skill', sa.JSON(), nullable=True, comment="Cleaning skill config"),
        sa.Column('insight_skill', sa.JSON(), nullable=True, comment="Insight skill config"),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_domain_configs_domain', 'domain_configs', ['domain'], unique=True)

    # 2. Seed the beauty domain configuration
    op.execute(text("""
        INSERT INTO domain_configs (domain, display_name, status, expander_skill, crawler_skill, cleaning_skill, insight_skill)
        VALUES (
            'beauty',
            '美妆护肤',
            'active',
            '{"strategy": "hierarchical", "negative_keywords": ["宠物", "汽车", "房产", "游戏"], "max_depth": 2, "levels": ["品类", "成分", "痛点"]}'::jsonb,
            '{"target_platforms": ["xiaohongshu", "douyin", "bilibili", "weibo"], "concurrency_limit": 5, "crawl_speed": "daily", "platform_weights": {"xiaohongshu": 1.0, "douyin": 0.8, "bilibili": 0.5, "weibo": 0.4}}'::jsonb,
            '{"required_entities": ["成分", "肤感", "功效宣称", "产品形态"], "noise_filters": ["包含推销广告链接", "纯抽奖博文"], "eval_metrics": ["schema_alignment", "factuality"], "judge_enabled": true, "judge_model": "gpt-4o-mini", "max_retries": 1}'::jsonb,
            '{"scoring_weights": {"likes": 0.3, "comments": 0.4, "shares": 0.3}, "anomaly_threshold_sigma": 3.0, "aggregation_window_days": 14, "decay_delta": 0.15, "report_template": "beauty_trend_report"}'::jsonb
        )
    """))

    # 3. Add domain_id columns (nullable first for backfill)
    op.add_column('trend_keywords', sa.Column('domain_id', sa.Integer(), nullable=True, comment="FK to domain_configs.id"))
    op.add_column('crawl_tasks', sa.Column('domain_id', sa.Integer(), nullable=True, comment="FK to domain_configs.id"))
    op.add_column('cleaned_trend_data', sa.Column('domain_id', sa.Integer(), nullable=True, comment="FK to domain_configs.id"))

    # 4. Backfill: set all existing data to beauty domain (id=1)
    op.execute(text("UPDATE trend_keywords SET domain_id = 1 WHERE domain_id IS NULL"))
    op.execute(text("UPDATE crawl_tasks SET domain_id = 1 WHERE domain_id IS NULL"))
    op.execute(text("UPDATE cleaned_trend_data SET domain_id = 1 WHERE domain_id IS NULL"))

    # 5. Create indexes on domain_id
    op.create_index('ix_trend_keywords_domain_id', 'trend_keywords', ['domain_id'])
    op.create_index('ix_crawl_tasks_domain_id', 'crawl_tasks', ['domain_id'])
    op.create_index('ix_cleaned_trend_data_domain_id', 'cleaned_trend_data', ['domain_id'])


def downgrade() -> None:
    # Remove domain_id indexes
    op.drop_index('ix_cleaned_trend_data_domain_id', table_name='cleaned_trend_data')
    op.drop_index('ix_crawl_tasks_domain_id', table_name='crawl_tasks')
    op.drop_index('ix_trend_keywords_domain_id', table_name='trend_keywords')

    # Remove domain_id columns
    op.drop_column('cleaned_trend_data', 'domain_id')
    op.drop_column('crawl_tasks', 'domain_id')
    op.drop_column('trend_keywords', 'domain_id')

    # Drop domain_configs table
    op.drop_index('ix_domain_configs_domain', table_name='domain_configs')
    op.drop_table('domain_configs')
