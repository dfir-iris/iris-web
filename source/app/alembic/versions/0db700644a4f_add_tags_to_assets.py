"""Add tags to assets

Revision ID: 0db700644a4f
Revises: 6a3b3b627d45
Create Date: 2022-01-06 13:47:12.648707

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
from app.alembic.alembic_utils import _table_has_column

revision = '0db700644a4f'
down_revision = '6a3b3b627d45'
branch_labels = None
depends_on = None


def upgrade():
    # Now issue changes on existing tables and migrate Asset tags
    # Add column asset_tags to CaseAssets if not existing
    if not _table_has_column('case_assets', 'asset_tags'):
        op.add_column('case_assets',
                      sa.Column('asset_tags', sa.Text)
                      )

    if _table_has_column('case_assets', 'asset_tags'):
        # Set schema and make migration of data
        t_case_assets = sa.Table(
            'case_assets',
            sa.MetaData(),
            sa.Column('asset_id', sa.Integer, primary_key=True),
            sa.Column('asset_name', sa.Text),
            sa.Column('asset_description', sa.Text),
            sa.Column('asset_domain', sa.Text),
            sa.Column('asset_ip', sa.Text),
            sa.Column('asset_info', sa.Text),
            sa.Column('asset_compromised', sa.Boolean),
            sa.Column('asset_type_id', sa.ForeignKey('asset_type.asset_id')),
            sa.Column('asset_tags', sa.Text),
            sa.Column('case_id', sa.ForeignKey('cases.case_id')),
            sa.Column('date_added', sa.DateTime),
            sa.Column('date_update', sa.DateTime),
            sa.Column('user_id', sa.ForeignKey('user.id')),
            sa.Column('analysis_status_id', sa.ForeignKey('analysis_status.id'))
        )

        # Migrate existing Assets
        conn = op.get_bind()
        res = conn.execute(text("SELECT asset_id from case_assets WHERE asset_tags IS NULL;"))
        results = res.fetchall()

        if results:

            for res in results:
                conn.execute(t_case_assets.update().where(t_case_assets.c.asset_id == res[0]).values(
                    asset_tags=''
                ))


def downgrade():
    pass
