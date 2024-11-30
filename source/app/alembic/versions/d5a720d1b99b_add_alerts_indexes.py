"""Add alerts indexes

Revision ID: d5a720d1b99b
Revises: 11aa5b725b8e
Create Date: 2024-10-28 12:54:22.782313

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from app.alembic.alembic_utils import _has_table, index_exists

# revision identifiers, used by Alembic.
revision = 'd5a720d1b99b'
down_revision = '11aa5b725b8e'
branch_labels = None
depends_on = None


def upgrade():
    # Adding indexes to the Alerts table
    if _has_table('alerts'):
        if not index_exists('alerts', 'idx_alerts_title'):
            op.create_index('idx_alerts_title', 'alerts', ['alert_title'])
        if not index_exists('alerts', 'idx_alerts_creation_time'):
            op.create_index('idx_alerts_creation_time', 'alerts', ['alert_creation_time'])
        if not index_exists('alerts', 'idx_alerts_source_event_time'):
            op.create_index('idx_alerts_source_event_time', 'alerts', ['alert_source_event_time'])
        if not index_exists('alerts', 'idx_alerts_customer_id'):
            op.create_index('idx_alerts_customer_id', 'alerts', ['alert_customer_id'])
        if not index_exists('alerts', 'alert_source_ref'):
            op.create_index('idx_alert_source_ref', 'alerts', ['alert_source_ref'])

    # Adding indexes to the Ioc table
    if _has_table('ioc'):
        if not index_exists('ioc', 'idx_ioc_value_hash'):
            # Create an index on the MD5 hash of ioc_value to handle large values
            op.execute(text("CREATE INDEX idx_ioc_value_hash ON ioc (md5(ioc_value::text))"))
        if not index_exists('ioc', 'idx_ioc_tags'):
            op.create_index('idx_ioc_tags', 'ioc', ['ioc_tags'])

    # Adding indexes to the CaseAssets table
    if _has_table('case_assets'):
        if not index_exists('case_assets', 'idx_case_assets_name'):
            op.create_index('idx_case_assets_name', 'case_assets', ['asset_name'])
        if not index_exists('case_assets', 'idx_case_assets_case_id'):
            op.create_index('idx_case_assets_case_id', 'case_assets', ['case_id'])
        if not index_exists('case_assets', 'idx_case_assets_date_added'):
            op.create_index('idx_case_assets_date_added', 'case_assets', ['date_added'])
        if not index_exists('case_assets', 'idx_case_assets_date_update'):
            op.create_index('idx_case_assets_date_update', 'case_assets', ['date_update'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_alert_similarity_alert_id', table_name='alert_similarity')
    op.drop_index('ix_alert_similarity_similar_alert_id', table_name='alert_similarity')
    op.drop_index('ix_alert_similarity_matching_asset_id', table_name='alert_similarity')
    op.drop_index('ix_alert_similarity_matching_ioc_id', table_name='alert_similarity')
    op.drop_index('ix_alert_similarity_similarity_type', table_name='alert_similarity')

    # Drop AlertSimilarity table
    op.drop_table('alert_similarity')

