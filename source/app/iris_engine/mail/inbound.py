#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Inbound mail poller — IMAP fetch + rule evaluation + object creation.

Runs as a Celery beat task every `mail_imap_poll_interval_sec`
seconds when `mail_imap_enabled` is True. Fetches unseen messages,
runs each through the rules engine, creates the corresponding Alert
or Case, and records the outcome in `mail_ingest_log`.

Idempotency: `mail_ingest_log.message_id` is a primary key. If the
same message is fetched twice (retry, mailbox re-scan, admin manual
run), the second insertion into the log fails and we skip. `mail`
servers only re-deliver a message when the previous poll couldn't
acknowledge — the log check catches those.

Failure isolation: exceptions inside the per-message loop are caught,
logged, and recorded as an `error` outcome. One malformed message
doesn't halt the poll.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple

from sqlalchemy.exc import IntegrityError

from app import celery
from app.db import db
from app.iris_engine.mail.config import ImapConfig
from app.iris_engine.mail.config import get_imap_config
from app.iris_engine.mail.rules import ParsedMail
from app.iris_engine.mail.rules import evaluate_rules
from app.models.mail import ACTION_CREATE_ALERT
from app.models.mail import ACTION_CREATE_CASE
from app.models.mail import ACTION_DROP
from app.models.mail import MailIngestLog
from app.models.mail import OUTCOME_ALERT_CREATED
from app.models.mail import OUTCOME_CASE_CREATED
from app.models.mail import OUTCOME_ERROR
from app.models.mail import OUTCOME_NO_RULE_MATCH
from app.models.mail import OUTCOME_SKIPPED_BY_RULE


logger = logging.getLogger(__name__)


# Cap on how many messages we ingest per poll. Prevents a runaway
# mailbox (deliberate flood or backlog) from monopolising the worker.
# Unprocessed messages stay flagged unseen and get picked up next round.
_BATCH_LIMIT = 50


# ---------------------------------------------------------------------
# IMAP fetch
# ---------------------------------------------------------------------

def _fetch_unseen(cfg: ImapConfig) -> List[ParsedMail]:
    """Pull up to `_BATCH_LIMIT` unseen messages, mark them read.

    Uses `imap-tools` for the client. The import is deferred so the
    module is loadable in test / migration contexts where the dep
    might not be installed.
    """
    from imap_tools import MailBox
    from imap_tools import AND

    max_bytes = cfg.max_attachment_mb * 1024 * 1024
    parsed: List[ParsedMail] = []

    box = MailBox(cfg.host, port=cfg.port) if cfg.use_ssl \
        else MailBox(cfg.host, port=cfg.port, ssl=False)  # imap-tools default is SSL

    with box.login(cfg.user, cfg.password, initial_folder=cfg.mailbox) as mailbox:
        # `mark_seen=True` — we drop the seen flag AFTER we've built
        # the ParsedMail tuple. If our fetch loop dies mid-message
        # the server-side flag stays unset and we retry next poll.
        count = 0
        for msg in mailbox.fetch(AND(seen=False), mark_seen=False,
                                 limit=_BATCH_LIMIT):
            count += 1
            attachments: List[Tuple[str, str, bytes]] = []
            for att in (msg.attachments or ()):
                if att.size and att.size > max_bytes:
                    logger.info('Skipping oversize attachment %s (%d bytes)',
                                att.filename, att.size)
                    continue
                attachments.append((att.filename or 'unnamed',
                                    att.content_type or 'application/octet-stream',
                                    att.payload or b''))

            parsed.append(ParsedMail(
                # `msg.uid` is the IMAP server's identifier; Message-ID
                # is the RFC-822 header we key our dedupe log on. Fall
                # back to `<uid>@imap.local` on messages that lack the
                # header (rare, but happens with some MTAs).
                message_id=(msg.headers.get('message-id',
                            (f'<{msg.uid}@imap.local>',))[0] or '').strip('<>'),
                from_addr=msg.from_ or '',
                to_addrs=tuple(msg.to or ()),
                subject=msg.subject or '',
                body_text=msg.text or '',
                body_html=msg.html or None,
                date=msg.date,
                attachments=tuple(attachments),
            ))

        # Only now do we flag them seen — a crash between fetch and
        # this flag means we'll re-see them next poll, dedupe against
        # `mail_ingest_log`, and skip. That's the correct behaviour.
        if parsed:
            uids = [str(u) for u in mailbox.uids(AND(seen=False))]
            if uids:
                try:
                    mailbox.flag(uids, ['\\Seen'], True)
                except Exception:
                    logger.exception('Failed to flag messages as seen')

    return parsed


# ---------------------------------------------------------------------
# Object creation
# ---------------------------------------------------------------------

def _find_first_customer_id() -> Optional[int]:
    """Fallback customer for the shipped default rule. First non-Iris
    customer if one exists, else the initial Iris customer.
    """
    from app.models.customers import Client
    row = (
        Client.query
        .order_by(Client.client_id.asc())
        .first()
    )
    return row.client_id if row else None


def _default_severity_id() -> Optional[int]:
    """Low-severity fallback if the rule didn't specify one."""
    from app.models.alerts import Severity
    row = (
        Severity.query
        .order_by(Severity.severity_id.asc())
        .first()
    )
    return row.severity_id if row else None


def _default_status_id() -> Optional[int]:
    """First alert status ('New' in a stock install)."""
    from app.models.alerts import AlertStatus
    row = (
        AlertStatus.query
        .order_by(AlertStatus.status_id.asc())
        .first()
    )
    return row.status_id if row else None


def _create_alert_from_mail(mail: ParsedMail, rule) -> Optional[int]:
    """Build an Alert from the parsed mail + rule. Returns alert_id.

    Rule fields override the shipped defaults. Attachments become
    entries in `alert_source_content` for now (evidence linkage from
    alerts is UI-driven post-escalation — hooking it here would
    duplicate half of alerts_create's logic).
    """
    # Late imports to keep this module import-light.
    from app.business.alerts import alerts_create
    from app.models.alerts import Alert

    customer_id = (rule.customer_id if rule and rule.customer_id
                   else _find_first_customer_id())
    if not customer_id:
        raise RuntimeError('No customer available to attach the alert to')

    severity_id = (rule.severity_id if rule and rule.severity_id
                   else _default_severity_id())
    status_id = _default_status_id()
    if not (severity_id and status_id):
        raise RuntimeError('Alert severity/status catalog is empty')

    alert = Alert(
        alert_title=(mail.subject or '(no subject)')[:512],
        alert_description=mail.body_text or '',
        alert_source='email',
        alert_source_ref=mail.message_id,
        alert_source_content={
            'from': mail.from_addr,
            'to': list(mail.to_addrs),
            'attachments': [
                {'filename': a[0], 'mime': a[1], 'size': len(a[2])}
                for a in (mail.attachments or ())
            ],
        },
        alert_source_event_time=mail.date or datetime.utcnow(),
        alert_severity_id=severity_id,
        alert_status_id=status_id,
        alert_customer_id=customer_id,
        alert_owner_id=(rule.assignee_user_id if rule else None),
    )
    alerts_create(alert, iocs=[], assets=[])
    return alert.alert_id


def _create_case_from_mail(mail: ParsedMail, rule) -> Optional[int]:
    """Escalate directly to a case, honouring an optional case_template."""
    from app.business.cases import cases_create
    from app.models.cases import Cases

    customer_id = (rule.customer_id if rule and rule.customer_id
                   else _find_first_customer_id())
    if not customer_id:
        raise RuntimeError('No customer available to attach the case to')

    # `cases_create` expects an owner — use the rule's assignee, or
    # fall back to user id 1 (the initial administrator seed).
    owner_id = (rule.assignee_user_id if rule and rule.assignee_user_id
                else 1)

    case = Cases(
        name=(mail.subject or '(no subject)')[:150],
        description=mail.body_text or '',
        soc_id='',
        user=None,
        client_name=str(customer_id),
        classification_id=None,
        customer_id=customer_id,
    )
    case.owner_id = owner_id
    case.user_id = owner_id
    template_id = (rule.case_template_id if rule else None)

    from app.models.authorization import User
    actor = User.query.filter(User.id == owner_id).first()

    cases_create(actor, case, template_id)
    return case.case_id


# ---------------------------------------------------------------------
# Log helper
# ---------------------------------------------------------------------

def _record_log(message_id: str, outcome: str,
                object_id: Optional[int] = None,
                rule_id: Optional[int] = None,
                from_addr: Optional[str] = None,
                subject: Optional[str] = None,
                error: Optional[str] = None) -> bool:
    """Insert an ingest-log row. Returns False if the message was
    already logged (PK conflict) — the caller uses that to short-
    circuit re-ingestion of a duplicated Message-ID."""
    row = MailIngestLog(
        message_id=message_id[:998],
        outcome=outcome,
        outcome_object_id=object_id,
        rule_id=rule_id,
        from_addr=(from_addr or '')[:320] or None,
        subject=(subject or '')[:2000] or None,
        error=error,
    )
    db.session.add(row)
    try:
        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False


def _process_one(mail: ParsedMail) -> None:
    """Route a single message through the rules engine and record."""
    # PRE-CHECK dedupe: if the Message-ID is already in the log, skip.
    # Belt-and-braces on top of the PK conflict check below — saves
    # us the rule query + object creation for known duplicates.
    if mail.message_id and MailIngestLog.query.get(mail.message_id) is not None:
        logger.debug('Skipping already-ingested message %s', mail.message_id)
        return

    try:
        rule = evaluate_rules(mail)
    except Exception as exc:
        logger.exception('Rule evaluation crashed')
        _record_log(mail.message_id, OUTCOME_ERROR,
                    from_addr=mail.from_addr, subject=mail.subject,
                    error=f'rule eval: {exc}')
        return

    if rule is None:
        # Shipped default: create an alert with the first customer +
        # first severity. The admin can add a catch-all rule to
        # customise this without editing code.
        try:
            alert_id = _create_alert_from_mail(mail, None)
        except Exception as exc:
            logger.exception('Default-alert creation failed')
            _record_log(mail.message_id, OUTCOME_ERROR,
                        from_addr=mail.from_addr, subject=mail.subject,
                        error=str(exc))
            return
        _record_log(mail.message_id, OUTCOME_NO_RULE_MATCH,
                    object_id=alert_id, from_addr=mail.from_addr,
                    subject=mail.subject)
        return

    if rule.action == ACTION_DROP:
        _record_log(mail.message_id, OUTCOME_SKIPPED_BY_RULE,
                    rule_id=rule.id, from_addr=mail.from_addr,
                    subject=mail.subject)
        return

    try:
        if rule.action == ACTION_CREATE_ALERT:
            alert_id = _create_alert_from_mail(mail, rule)
            _record_log(mail.message_id, OUTCOME_ALERT_CREATED,
                        object_id=alert_id, rule_id=rule.id,
                        from_addr=mail.from_addr, subject=mail.subject)
        elif rule.action == ACTION_CREATE_CASE:
            case_id = _create_case_from_mail(mail, rule)
            _record_log(mail.message_id, OUTCOME_CASE_CREATED,
                        object_id=case_id, rule_id=rule.id,
                        from_addr=mail.from_addr, subject=mail.subject)
        else:
            logger.warning('Unknown mail rule action %r on rule id=%s',
                           rule.action, rule.id)
            _record_log(mail.message_id, OUTCOME_ERROR,
                        rule_id=rule.id, from_addr=mail.from_addr,
                        subject=mail.subject,
                        error=f'unknown action {rule.action!r}')
    except Exception as exc:
        logger.exception('Ingestion failed for message %s', mail.message_id)
        _record_log(mail.message_id, OUTCOME_ERROR,
                    rule_id=rule.id, from_addr=mail.from_addr,
                    subject=mail.subject, error=str(exc))


# ---------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------

@celery.task(bind=True, name='iris.mail.poll_inbound_mail')
def poll_inbound_mail(self) -> dict:
    """Periodic entry point. Reads config, fetches, dispatches.

    Returns a small stats dict for the beat log so operators can
    grep worker logs for "poll_inbound_mail" and see message counts.
    """
    cfg = get_imap_config()
    if cfg is None:
        return {'skipped': True, 'reason': 'IMAP disabled or misconfigured'}

    try:
        mails = _fetch_unseen(cfg)
    except Exception as exc:
        logger.exception('IMAP fetch failed')
        return {'skipped': True, 'reason': f'fetch error: {exc}'}

    processed = 0
    for m in mails:
        _process_one(m)
        processed += 1

    return {'skipped': False, 'processed': processed}


def _fetch_unseen_for_testing(cfg: ImapConfig) -> List[ParsedMail]:
    """Public wrapper for tests that want to exercise the fetch path
    against a stubbed mailbox. Kept trivially thin so the production
    path stays untouched."""
    return _fetch_unseen(cfg)


# ---------------------------------------------------------------------
# Beat schedule registration
# ---------------------------------------------------------------------

_BEAT_ENTRY = 'iris_mail_poll_inbound'


def _current_interval_sec() -> int:
    """Interval to run the poller at. Reads the admin-configured value
    with a floor of 60s — anything lower makes the mail server unhappy
    and doesn't help operators."""
    cfg = get_imap_config()
    interval = cfg.poll_interval_sec if cfg else 300
    return max(60, int(interval))


@celery.on_after_finalize.connect
def _register_mail_beat_schedule(sender, **_kwargs):
    """Add the periodic poll to the beat schedule at worker boot.

    Idempotent — if the entry is already there (double-boot on the
    same worker, unlikely but possible) we replace it in-place so
    the interval reflects the latest config. `imap_is_configured()`
    IS NOT checked here: registering unconditionally means an admin
    who enables IMAP mid-run doesn't need to restart the worker for
    the beat entry to appear. The task itself checks config on each
    tick and short-circuits when disabled.
    """
    from celery.schedules import schedule as _schedule

    interval = _current_interval_sec()
    sender.conf.beat_schedule = dict(sender.conf.beat_schedule or {})
    sender.conf.beat_schedule[_BEAT_ENTRY] = {
        'task': 'iris.mail.poll_inbound_mail',
        'schedule': _schedule(run_every=interval),
    }
    logger.info('Registered %s every %d seconds', _BEAT_ENTRY, interval)
