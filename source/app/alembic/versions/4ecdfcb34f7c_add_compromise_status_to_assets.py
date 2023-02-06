"""Add compromise status to assets

Revision ID: 4ecdfcb34f7c
Revises: a929ef458490
Create Date: 2022-11-26 17:06:33.061363

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
from app.alembic.alembic_utils import _table_has_column
from app.models import CompromiseStatus

revision = '4ecdfcb34f7c'
down_revision = 'a929ef458490'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('case_assets', 'asset_compromise_status_id'):
        op.add_column('case_assets',
                      sa.Column('asset_compromise_status_id',
                                sa.Integer(),
                                nullable=True))
        # Set schema and make migration of data
        t_assets = sa.Table(
            'case_assets',
            sa.MetaData(),
            sa.Column('asset_id', sa.BigInteger, primary_key=True),
            sa.Column('asset_compromise_status_id', sa.Integer, nullable=True),
            sa.Column('asset_compromised', sa.Boolean, nullable=True)
        )

        conn = op.get_bind()
        conn.execute(t_assets.update().values(
            asset_compromise_status_id=CompromiseStatus.compromised.value
        ).where(t_assets.c.asset_compromised == True))

        conn.execute(t_assets.update().values(
            asset_compromise_status_id=CompromiseStatus.not_compromised.value
        ).where(t_assets.c.asset_compromised == False))

        op.drop_column('case_assets', 'asset_compromised')

    pass


def downgrade():
    pass
