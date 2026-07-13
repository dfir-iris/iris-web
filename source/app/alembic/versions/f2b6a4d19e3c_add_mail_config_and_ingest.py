"""Mail feature — extend server_settings + add ingest rule/log tables.

Outbound + inbound mail config lives on the singleton `server_settings`
row alongside proxy + password-policy config; there's only ever one
outbound relay and one inbound mailbox per deployment, so a dedicated
table would be pure overhead. Passwords (`mail_smtp_password`,
`mail_imap_password`) are stored ENCRYPTED using the app SECRET_KEY —
the columns hold ciphertext, never plaintext. See
`app/iris_engine/mail/secrets.py` for the wrap/unwrap helpers.

`mail_ingest_rule` drives the inbound router: incoming messages are
matched against enabled rules in `priority` order (lowest first) and
the first hit decides `create_alert` / `create_case` / `drop`.

`mail_ingest_log` is an audit trail keyed by `Message-ID` so re-polls
of the mailbox can dedupe cheaply. `outcome_object_id` points at the
alert or case the message became (or NULL for `drop` / `error`).

Idempotent via `_has_table` / `_table_has_column`.

Revision ID: f2b6a4d19e3c
Revises: e7b1f4a8c920
Create Date: 2026-07-02 15:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

from app.alembic.alembic_utils import _has_table
from app.alembic.alembic_utils import _table_has_column
from app.alembic.alembic_utils import index_exists


revision = 'f2b6a4d19e3c'
down_revision = 'e7b1f4a8c920'
branch_labels = None
depends_on = None


_MAIL_COLUMNS = [
    # ---- Outbound (SMTP) ----
    ('mail_smtp_enabled', sa.Boolean(), sa.text('false')),
    ('mail_smtp_host', sa.String(length=255), None),
    ('mail_smtp_port', sa.Integer(), None),
    ('mail_smtp_user', sa.String(length=255), None),
    # Encrypted at rest via Fernet(SECRET_KEY) — never plaintext.
    ('mail_smtp_password', sa.Text(), None),
    ('mail_smtp_use_tls', sa.Boolean(), sa.text('true')),
    ('mail_smtp_use_ssl', sa.Boolean(), sa.text('false')),
    ('mail_from_address', sa.String(length=255), None),
    ('mail_from_name', sa.String(length=255), None),
    # ---- Inbound (IMAP) ----
    ('mail_imap_enabled', sa.Boolean(), sa.text('false')),
    ('mail_imap_host', sa.String(length=255), None),
    ('mail_imap_port', sa.Integer(), None),
    ('mail_imap_user', sa.String(length=255), None),
    ('mail_imap_password', sa.Text(), None),
    ('mail_imap_use_ssl', sa.Boolean(), sa.text('true')),
    ('mail_imap_mailbox', sa.String(length=255), sa.text("'INBOX'")),
    ('mail_imap_poll_interval_sec', sa.Integer(), sa.text('300')),
    ('mail_imap_max_attachment_mb', sa.Integer(), sa.text('20')),
]


def upgrade():
    if _has_table('server_settings'):
        for name, type_, default in _MAIL_COLUMNS:
            if not _table_has_column('server_settings', name):
                op.add_column(
                    'server_settings',
                    sa.Column(name, type_, nullable=True,
                              server_default=default) if default is not None
                    else sa.Column(name, type_, nullable=True),
                )

    # -----------------------------------------------------------------
    # mail_ingest_rule
    # -----------------------------------------------------------------
    if not _has_table('mail_ingest_rule'):
        op.create_table(
            'mail_ingest_rule',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            # Lower runs first. A rule with priority 100 is applied
            # before priority 200. Idiomatic for ordered-rules systems.
            sa.Column('priority', sa.Integer(), nullable=False,
                      server_default=sa.text('100')),
            sa.Column('enabled', sa.Boolean(), nullable=False,
                      server_default=sa.text('true')),
            # Match predicates — all nullable, all optional. A rule
            # with no predicates matches every message (fallback rule).
            sa.Column('match_subject_regex', sa.Text(), nullable=True),
            sa.Column('match_from_regex', sa.Text(), nullable=True),
            sa.Column('match_to_regex', sa.Text(), nullable=True),
            # `create_alert` | `create_case` | `drop`. Free-form string
            # (not a Postgres enum) so adding a new action doesn't need
            # a migration.
            sa.Column('action', sa.String(length=32), nullable=False,
                      server_default=sa.text("'create_alert'")),
            sa.Column('customer_id',
                      sa.BigInteger(), nullable=True),
            sa.Column('case_template_id', sa.Integer(), nullable=True),
            sa.Column('severity_id', sa.Integer(), nullable=True),
            sa.Column('assignee_user_id', sa.BigInteger(), nullable=True),
            sa.Column('created_by_id', sa.BigInteger(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['customer_id'], ['client.client_id'],
                                     ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['case_template_id'], ['case_template.id'],
                                     ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['severity_id'], ['severities.severity_id'],
                                     ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['assignee_user_id'], ['user.id'],
                                     ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['created_by_id'], ['user.id'],
                                     ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
    if not index_exists('mail_ingest_rule', 'ix_mail_ingest_rule_priority'):
        op.create_index('ix_mail_ingest_rule_priority',
                        'mail_ingest_rule', ['priority', 'enabled'])

    # -----------------------------------------------------------------
    # mail_ingest_log
    # -----------------------------------------------------------------
    if not _has_table('mail_ingest_log'):
        op.create_table(
            'mail_ingest_log',
            # `message_id` from the RFC-822 header (`Message-ID:` value,
            # angle brackets stripped). Primary key: the same message
            # arriving twice must be a no-op. Length 998 matches the
            # RFC 5322 line-length ceiling.
            sa.Column('message_id', sa.String(length=998), nullable=False),
            sa.Column('received_at', sa.DateTime(), nullable=False,
                      server_default=sa.text('now()')),
            # `alert_created` | `case_created` | `skipped_by_rule`
            # | `no_rule_match` | `error`. Free-form to allow evolution.
            sa.Column('outcome', sa.String(length=32), nullable=False),
            sa.Column('outcome_object_id', sa.BigInteger(), nullable=True),
            sa.Column('rule_id', sa.BigInteger(), nullable=True),
            # `from_addr` + `subject` kept for the admin log UI so
            # operators can eyeball what got in without opening every
            # source object.
            sa.Column('from_addr', sa.String(length=320), nullable=True),
            sa.Column('subject', sa.Text(), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['rule_id'], ['mail_ingest_rule.id'],
                                     ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('message_id'),
        )
    if not index_exists('mail_ingest_log', 'ix_mail_ingest_log_received_at'):
        op.create_index('ix_mail_ingest_log_received_at',
                        'mail_ingest_log', ['received_at'])


def downgrade():
    if index_exists('mail_ingest_log', 'ix_mail_ingest_log_received_at'):
        op.drop_index('ix_mail_ingest_log_received_at',
                      table_name='mail_ingest_log')
    if _has_table('mail_ingest_log'):
        op.drop_table('mail_ingest_log')

    if index_exists('mail_ingest_rule', 'ix_mail_ingest_rule_priority'):
        op.drop_index('ix_mail_ingest_rule_priority',
                      table_name='mail_ingest_rule')
    if _has_table('mail_ingest_rule'):
        op.drop_table('mail_ingest_rule')

    if _has_table('server_settings'):
        for name, _type_, _default in _MAIL_COLUMNS:
            if _table_has_column('server_settings', name):
                op.drop_column('server_settings', name)
