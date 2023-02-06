"""Add IocType validation

Revision ID: ad4e0cd17597
Revises: cd519d2d24df
Create Date: 2022-08-04 15:37:44.484997

"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _table_has_column

# revision identifiers, used by Alembic.

revision = 'ad4e0cd17597'
down_revision = '875edc4adb40'
branch_labels = None
depends_on = None


def upgrade():
    if not _table_has_column('ioc_type', 'type_validation_regex'):
        op.add_column('ioc_type',
                      sa.Column('type_validation_regex', sa.Text)
                      )

    if not _table_has_column('ioc_type', 'type_validation_expect'):
        op.add_column('ioc_type',
                      sa.Column('type_validation_expect', sa.Text)
                      )

    # Migrate known existing rows if any
    migration_map = {
        "authentihash": "[a-f0-9]{64}",
        "filename|authentihash": ".+\|[a-f0-9]{64}",
        "filename|imphash": ".+\|[a-f0-9]{32}",
        "filename|md5": ".+\|[a-f0-9]{32}",
        "filename|pehash": ".+\|[a-f0-9]{40}",
        "filename|sha1": ".+\|[a-f0-9]{40}",
        "filename|sha224": ".+\|[a-f0-9]{56}",
        "filename|sha256": ".+\|[a-f0-9]{64}",
        "filename|sha3-224": ".+\|[a-f0-9]{56}",
        "filename|sha3-256": ".+\|[a-f0-9]{64}",
        "filename|sha3-384": ".+\|[a-f0-9]{96}",
        "filename|sha3-512": ".+\|[a-f0-9]{128}",
        "filename|sha384": ".+\|[a-f0-9]{96}",
        "filename|sha512": ".+\|[a-f0-9]{128}",
        "filename|sha512/224": ".+\|[a-f0-9]{56}",
        "filename|sha512/256": ".+\|[a-f0-9]{64}",
        "filename|tlsh": ".+\|t?[a-f0-9]{35,}",
        "git-commit-id": "[a-f0-9]{40}",
        "hassh-md5": "[a-f0-9]{32}",
        "hasshserver-md5": "[a-f0-9]{32}",
        "imphash": "[a-f0-9]{32}",
        "ja3-fingerprint-md5": "[a-f0-9]{32}",
        "jarm-fingerprint": "[a-f0-9]{62}",
        "md5": "[a-f0-9]{32}",
        "pehash": "[a-f0-9]{40}",
        "sha1": "[a-f0-9]{40}",
        "sha224": "[a-f0-9]{56}",
        "sha256": "[a-f0-9]{64}",
        "sha3-224": "[a-f0-9]{56}",
        "sha3-256": "[a-f0-9]{64}",
        "sha3-384": "[a-f0-9]{96}",
        "sha3-512": "[a-f0-9]{128}",
        "sha384": "[a-f0-9]{96}",
        "sha512": "[a-f0-9]{128}",
        "sha512/224": "[a-f0-9]{56}",
        "sha512/256": "[a-f0-9]{64}",
        "telfhash": "[a-f0-9]{70}",
        "tlsh": "^t?[a-f0-9]{35,}",
        "x509-fingerprint-md5": "[a-f0-9]{32}",
        "x509-fingerprint-sha1": "[a-f0-9]{40}",
        "x509-fingerprint-sha256": "[a-f0-9]{64}"
    }

    t_tasks = sa.Table(
        'ioc_type',
        sa.MetaData(),
        sa.Column('type_id', sa.Integer, primary_key=True),
        sa.Column('type_name', sa.Text),
        sa.Column('type_validation_regex', sa.Text),
        sa.Column('type_validation_expect', sa.Text),
    )

    conn = op.get_bind()
    for type_name in migration_map:
        conn.execute(t_tasks.update().where(t_tasks.c.type_name == type_name).values(
            type_validation_regex=migration_map[type_name]
        ))


def downgrade():
    op.drop_column('ioc_type', 'type_validation_regex')
    op.drop_column('ioc_type', 'type_validation_expect')

