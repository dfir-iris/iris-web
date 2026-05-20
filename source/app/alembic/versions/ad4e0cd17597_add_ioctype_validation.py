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
        "authentihash": r"[a-f0-9]{64}",
        "filename|authentihash": r".+\|[a-f0-9]{64}",
        "filename|imphash": r".+\|[a-f0-9]{32}",
        "filename|md5": r".+\|[a-f0-9]{32}",
        "filename|pehash": r".+\|[a-f0-9]{40}",
        "filename|sha1": r".+\|[a-f0-9]{40}",
        "filename|sha224": r".+\|[a-f0-9]{56}",
        "filename|sha256": r".+\|[a-f0-9]{64}",
        "filename|sha3-224": r".+\|[a-f0-9]{56}",
        "filename|sha3-256": r".+\|[a-f0-9]{64}",
        "filename|sha3-384": r".+\|[a-f0-9]{96}",
        "filename|sha3-512": r".+\|[a-f0-9]{128}",
        "filename|sha384": r".+\|[a-f0-9]{96}",
        "filename|sha512": r".+\|[a-f0-9]{128}",
        "filename|sha512/224": r".+\|[a-f0-9]{56}",
        "filename|sha512/256": r".+\|[a-f0-9]{64}",
        "filename|tlsh": r".+\|t?[a-f0-9]{35,}",
        "git-commit-id": r"[a-f0-9]{40}",
        "hassh-md5": r"[a-f0-9]{32}",
        "hasshserver-md5": r"[a-f0-9]{32}",
        "imphash": r"[a-f0-9]{32}",
        "ja3-fingerprint-md5": r"[a-f0-9]{32}",
        "jarm-fingerprint": r"[a-f0-9]{62}",
        "md5": r"[a-f0-9]{32}",
        "pehash": r"[a-f0-9]{40}",
        "sha1": r"[a-f0-9]{40}",
        "sha224": r"[a-f0-9]{56}",
        "sha256": r"[a-f0-9]{64}",
        "sha3-224": r"[a-f0-9]{56}",
        "sha3-256": r"[a-f0-9]{64}",
        "sha3-384": r"[a-f0-9]{96}",
        "sha3-512": r"[a-f0-9]{128}",
        "sha384": r"[a-f0-9]{96}",
        "sha512": r"[a-f0-9]{128}",
        "sha512/224": r"[a-f0-9]{56}",
        "sha512/256": r"[a-f0-9]{64}",
        "telfhash": r"[a-f0-9]{70}",
        "tlsh": r"^t?[a-f0-9]{35,}",
        "x509-fingerprint-md5": r"[a-f0-9]{32}",
        "x509-fingerprint-sha1": r"[a-f0-9]{40}",
        "x509-fingerprint-sha256": r"[a-f0-9]{64}"
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
