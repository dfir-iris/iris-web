"""Adding IOC and assets enrichments

Revision ID: 2a4a8330b908
Revises: f727badcc4e1
Create Date: 2023-04-26 08:42:19.397146

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.
revision = '2a4a8330b908'
down_revision = 'f727badcc4e1'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('case_assets', 'asset_enrichment'):
        # Add asset_enrichment column to case_assets
        op.add_column('case_assets', sa.Column('asset_enrichment', JSONB, nullable=True))

    if not _table_has_column('ioc', 'ioc_enrichment'):
        # Add ioc_enrichment column to ioc
        op.add_column('ioc', sa.Column('ioc_enrichment', JSONB, nullable=True))


def downgrade():
    if not _table_has_column('case_assets', 'asset_enrichment'):
        # Remove asset_enrichment column from case_assets
        op.drop_column('case_assets', 'asset_enrichment')

    if _table_has_column('ioc', 'ioc_enrichment'):
        # Remove ioc_enrichment column from ioc
        op.drop_column('ioc', 'ioc_enrichment')
