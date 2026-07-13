#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Outbound mail — SMTP send + notification-email Celery task.

Direct `smtplib`/`email.message` rather than Flask-Mail: we don't
need the app-context glue or the CLI it ships, and using stdlib
keeps the dependency footprint smaller. The Celery task handles
retries with exponential backoff.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional
from typing import Sequence

from app import app
from app import celery
from app.iris_engine.mail.config import SmtpConfig
from app.iris_engine.mail.config import get_smtp_config


logger = logging.getLogger(__name__)


def _build_message(cfg: SmtpConfig,
                   to: Sequence[str],
                   subject: str,
                   body_text: str,
                   body_html: Optional[str] = None) -> EmailMessage:
    msg = EmailMessage()
    msg['Subject'] = subject
    if cfg.from_name:
        msg['From'] = f'{cfg.from_name} <{cfg.from_address}>'
    else:
        msg['From'] = cfg.from_address
    msg['To'] = ', '.join(to)
    # Plain-text is the primary body — HTML is added as an alternative
    # part so text-only mail clients still get a readable message. Some
    # notifications legitimately have no HTML variant; keep them plain.
    msg.set_content(body_text or '')
    if body_html:
        msg.add_alternative(body_html, subtype='html')
    return msg


def _send_via_smtp(cfg: SmtpConfig, msg: EmailMessage) -> None:
    """Open, authenticate, deliver, close. Blocking."""
    ctx = ssl.create_default_context()
    if cfg.use_ssl:
        with smtplib.SMTP_SSL(cfg.host, cfg.port, context=ctx, timeout=30) as srv:
            if cfg.user and cfg.password:
                srv.login(cfg.user, cfg.password)
            srv.send_message(msg)
        return

    with smtplib.SMTP(cfg.host, cfg.port, timeout=30) as srv:
        srv.ehlo()
        if cfg.use_tls:
            srv.starttls(context=ctx)
            srv.ehlo()
        if cfg.user and cfg.password:
            srv.login(cfg.user, cfg.password)
        srv.send_message(msg)


def send_email(to: Sequence[str],
               subject: str,
               body_text: str,
               body_html: Optional[str] = None,
               cfg: Optional[SmtpConfig] = None) -> bool:
    """Send a mail synchronously. Returns True on delivery.

    Public helper for callers that already run off the request path
    (tests, celery tasks). REST paths should use the Celery task
    below so a slow SMTP endpoint doesn't stall the HTTP request.
    """
    if not to:
        return False
    cfg = cfg or get_smtp_config()
    if cfg is None:
        logger.info('SMTP not configured — dropping mail to %s', to)
        return False
    msg = _build_message(cfg, to, subject, body_text, body_html)
    _send_via_smtp(cfg, msg)
    return True


# ---- Celery task -----------------------------------------------------
#
# `autoretry_for` + exponential backoff bounded at 5 attempts. Beyond
# that we log-and-drop rather than piling up in the queue — SMTP
# failures that persist that long are usually config problems the
# admin has to fix, not transient network glitches.
_RETRY_BACKOFF_MAX = 600     # seconds (10 minutes cap)
_RETRY_MAX_ATTEMPTS = 5


@celery.task(
    bind=True,
    autoretry_for=(smtplib.SMTPException, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=_RETRY_BACKOFF_MAX,
    retry_jitter=True,
    max_retries=_RETRY_MAX_ATTEMPTS,
)
def send_notification_email(self, notification_id: int) -> bool:
    """Deliver a notification via SMTP. Fetches title/body from the
    persisted row, renders a minimal template, sends, then stamps
    `emailed_at`. Idempotent-ish: a retry re-sends the same message,
    which is acceptable — SMTP has no client-side dedupe primitive
    and the alternative (skip on `emailed_at` set) would silently
    drop legitimate retries.
    """
    # Late imports so this module is importable in contexts (worker
    # bootstrap, alembic) that don't have every model wired yet.
    from datetime import datetime
    from app.db import db
    from app.models.notifications import Notification

    cfg = get_smtp_config()
    if cfg is None:
        logger.debug('send_notification_email(%s): SMTP disabled, skipping',
                     notification_id)
        return False

    n = Notification.query.filter(Notification.id == notification_id).first()
    if n is None:
        logger.warning('send_notification_email(%s): row not found',
                       notification_id)
        return False

    user = getattr(n, 'user', None)
    to_addr = getattr(user, 'email', None) if user is not None else None
    if not to_addr:
        logger.info('send_notification_email(%s): recipient has no email',
                    notification_id)
        return False

    # Minimal template — sender-side rendering is deliberately terse
    # to keep this dependency-free. If a follow-up wants richer HTML,
    # switch to Jinja `render_template` over the templates under
    # `app/templates/email/*.html`.
    base_url = app.config.get('IRIS_ALLOW_ORIGIN') or ''
    link_line = f'\n\nOpen: {base_url}{n.link}' if n.link else ''
    body_text = f'{n.title}\n\n{n.body or ""}{link_line}\n'
    subject = f'[IRIS] {n.title}'

    try:
        send_email([to_addr], subject, body_text, cfg=cfg)
    except Exception:
        # Autoretry handles the SMTPException/network subclasses;
        # anything else (schema mismatch, bad config) we log and
        # give up on to avoid infinite retry storms.
        logger.exception('send_notification_email(%s) failed permanently',
                         notification_id)
        return False

    n.emailed_at = datetime.utcnow()
    db.session.commit()
    return True


def mail_send_system(to: Sequence[str], subject: str, body: str) -> bool:
    """One-off system mail (test emails, admin alerts, …).

    Returns True on delivery. Wraps `send_email` so callers don't
    need to know about `get_smtp_config`.
    """
    return send_email(to, subject, body)
