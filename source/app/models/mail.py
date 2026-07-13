#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Mail ingest models.

`MailIngestRule` drives the inbound router — incoming email is
matched against enabled rules in `priority` order (lowest first),
first hit wins, and `action` decides `create_alert` / `create_case`
/ `drop`.

`MailIngestLog` is an audit trail keyed by `Message-ID`. Repeat polls
of the mailbox can safely dedupe by INSERT-then-catch on the PK; the
row also records the outcome so the admin log UI can render "3 alerts
created / 2 dropped / 1 error" without scanning source objects.
"""

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db import db


# ---- Action & outcome vocab. Kept as constants (not enums) so a
# ---- follow-up migration isn't needed to add e.g. `create_ioc`.
ACTION_CREATE_ALERT = 'create_alert'
ACTION_CREATE_CASE = 'create_case'
ACTION_DROP = 'drop'
VALID_ACTIONS = (ACTION_CREATE_ALERT, ACTION_CREATE_CASE, ACTION_DROP)

OUTCOME_ALERT_CREATED = 'alert_created'
OUTCOME_CASE_CREATED = 'case_created'
OUTCOME_SKIPPED_BY_RULE = 'skipped_by_rule'
OUTCOME_NO_RULE_MATCH = 'no_rule_match'
OUTCOME_ERROR = 'error'


class MailIngestRule(db.Model):
    __tablename__ = 'mail_ingest_rule'

    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    priority = Column(Integer, nullable=False, default=100)
    enabled = Column(Boolean, nullable=False, default=True)

    # All predicates nullable — a rule with no predicates matches
    # every message and serves as the fallback catch-all. The router
    # applies the predicates as AND when multiple are set.
    match_subject_regex = Column(Text, nullable=True)
    match_from_regex = Column(Text, nullable=True)
    match_to_regex = Column(Text, nullable=True)

    action = Column(String(32), nullable=False, default=ACTION_CREATE_ALERT)

    customer_id = Column(BigInteger, ForeignKey('client.client_id',
                                                ondelete='SET NULL'),
                         nullable=True)
    case_template_id = Column(Integer, ForeignKey('case_template.id',
                                                  ondelete='SET NULL'),
                              nullable=True)
    severity_id = Column(Integer, ForeignKey('severities.severity_id',
                                             ondelete='SET NULL'),
                         nullable=True)
    assignee_user_id = Column(BigInteger, ForeignKey('user.id',
                                                     ondelete='SET NULL'),
                              nullable=True)

    created_by_id = Column(BigInteger, ForeignKey('user.id',
                                                  ondelete='SET NULL'),
                           nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())

    customer = relationship('Client', foreign_keys=[customer_id])
    case_template = relationship('CaseTemplate', foreign_keys=[case_template_id])
    severity = relationship('Severity', foreign_keys=[severity_id])
    assignee = relationship('User', foreign_keys=[assignee_user_id])
    created_by = relationship('User', foreign_keys=[created_by_id])


class MailIngestLog(db.Model):
    __tablename__ = 'mail_ingest_log'

    # The RFC-822 `Message-ID:` header value (angle brackets stripped).
    # PK — the same message arriving twice must be a no-op. We rely on
    # this uniqueness for the poller's dedupe path.
    message_id = Column(String(998), primary_key=True)
    received_at = Column(DateTime, nullable=False, server_default=func.now())
    outcome = Column(String(32), nullable=False)
    outcome_object_id = Column(BigInteger, nullable=True)
    rule_id = Column(BigInteger, ForeignKey('mail_ingest_rule.id',
                                            ondelete='SET NULL'),
                     nullable=True)
    from_addr = Column(String(320), nullable=True)
    subject = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    rule = relationship('MailIngestRule', foreign_keys=[rule_id])
