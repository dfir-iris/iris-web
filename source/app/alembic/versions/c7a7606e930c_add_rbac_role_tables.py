"""Add RBAC Role tables

Revision ID: c7a7606e930c
Revises: 11aa5b725b8e
Create Date: 2024-07-04 12:26:01.299980

"""
from alembic import op
import sqlalchemy as sa
from app.alembic.alembic_utils import _has_table

# revision identifiers, used by Alembic.
revision = 'c7a7606e930c'
down_revision = '11aa5b725b8e'
branch_labels = None
depends_on = None


def upgrade():
    """Apply this upgrade by creating all the new RBAC tables"""

    bind = op.get_bind()

    # Create `role` table
    if not _has_table("role"):
        role_table = sa.Table(
            'role', sa.MetaData(),
            sa.Column('role_id', sa.BigInteger, primary_key=True),
            sa.Column('name', sa.String(64)),
            sa.Column('description', sa.Text),
            sa.Column('entitlements', sa.JSON)
        )
        role_table.create(bind)

    # Create `organisation_role` table
    if not _has_table("organisation_role"):
        organisation_role_table = sa.Table(
            'organisation_role', sa.MetaData(),
            sa.Column('role_id', sa.BigInteger, sa.ForeignKey(
                'role.role_id'), primary_key=True),
            sa.Column('org_id', sa.BigInteger, sa.ForeignKey(
                'organisations.org_id'), primary_key=True),
            sa.UniqueConstraint('role_id', 'org_id')
        )
        organisation_role_table.create(bind)

    # Create `case_role` table
    if not _has_table("case_role"):
        case_role_table = sa.Table(
            'case_role', sa.MetaData(),
            sa.Column('role_id', sa.BigInteger, sa.ForeignKey(
                'role.role_id'), primary_key=True),
            sa.Column('case_id', sa.BigInteger, sa.ForeignKey(
                'cases.case_id'), primary_key=True),
            sa.UniqueConstraint('role_id', 'case_id')
        )
        case_role_table.create(bind)

    bind.commit()


def downgrade():
    """
    Downgrade this migration by dropping all the newly created tables
    """

    op.drop_table('role')
    op.drop_table('organisation_role')
    op.drop_table('case_role')
