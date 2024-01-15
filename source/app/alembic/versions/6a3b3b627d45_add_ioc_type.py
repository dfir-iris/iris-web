"""Add IOC type

Revision ID: 6a3b3b627d45
Revises:
Create Date: 2022-01-01 23:40:35.283005

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
from app.alembic.alembic_utils import _table_has_column

revision = '6a3b3b627d45'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # IOC types is created by post init if not existing
    # Now issue changes on existing tables and migrate IOC types
    # Add column ioc_type_id to IOC if not existing
    if not _table_has_column('ioc', 'ioc_type_id'):
        op.add_column('ioc',
                      sa.Column('ioc_type_id', sa.Integer, sa.ForeignKey('ioc_type.type_id'))
                      )

        # Add the foreign key of ioc_type to ioc
        op.create_foreign_key(
            constraint_name='ioc_ioc_type_id',
            source_table="ioc",
            referent_table="ioc_type",
            local_cols=["ioc_type_id"],
            remote_cols=["type_id"])

    if _table_has_column('ioc', 'ioc_type'):
        # Set schema and make migration of data
        t_ioc = sa.Table(
            'ioc',
            sa.MetaData(),
            sa.Column('ioc_id', sa.Integer, primary_key=True),
            sa.Column('ioc_value', sa.Text),
            sa.Column('ioc_type', sa.Unicode(length=50)),
            sa.Column('ioc_type_id', sa.ForeignKey('ioc_type.type_id')),
            sa.Column('ioc_tags', sa.Text),
            sa.Column('user_id', sa.ForeignKey('user.id')),
            sa.Column('ioc_misp', sa.Text),
            sa.Column('ioc_tlp_id', sa.ForeignKey('tlp.tlp_id'))
        )
        to_update = [('Domain', 'domain'), ('IP', 'ip-any'), ('Hash', 'other'), ('File', 'filename'),
                     ('Path', 'file-path'), ('Account', 'account'), ("Other", 'other')]

        # Migrate existing IOCs
        for src_up, dst_up in to_update:
            conn = op.get_bind()
            res = conn.execute(text(f"select ioc_id from ioc where ioc_type = '{src_up}';"))
            results = res.fetchall()
            res = conn.execute(text(f"select type_id from ioc_type where type_name = '{dst_up}';"))
            e_info = res.fetchall()

            if e_info:
                domain_id = e_info[0][0]

                for res in results:
                    conn.execute(t_ioc.update().where(t_ioc.c.ioc_id == res[0]).values(
                        ioc_type_id=domain_id
                    ))

        op.drop_column(
            table_name='ioc',
            column_name='ioc_type'
        )

    pass


def downgrade():
    pass
