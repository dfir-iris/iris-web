#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Runtime access to mail config on `ServerSettings`.

Kept thin so callers don't scatter `ServerSettings.query.first()`
across the mail engine — both outbound and inbound need the same
"is this configured and enabled?" answer and it's easy to skew
between call sites otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.iris_engine.mail.secrets import decrypt_secret
from app.models.models import ServerSettings


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: Optional[str]
    password: Optional[str]  # plaintext, already decrypted
    use_tls: bool
    use_ssl: bool
    from_address: str
    from_name: Optional[str]


@dataclass(frozen=True)
class ImapConfig:
    host: str
    port: int
    user: str
    password: str  # plaintext, already decrypted
    use_ssl: bool
    mailbox: str
    poll_interval_sec: int
    max_attachment_mb: int


def _srv() -> Optional[ServerSettings]:
    return ServerSettings.query.first()


def get_smtp_config() -> Optional[SmtpConfig]:
    """Return the outbound config, or None if disabled / incomplete.

    "Incomplete" is treated the same as disabled: no host, no port,
    no `from_address` → we can't send, don't half-try. Callers use
    the None return to short-circuit — see `send_notification_email`.
    """
    srv = _srv()
    if srv is None or not srv.mail_smtp_enabled:
        return None
    if not (srv.mail_smtp_host and srv.mail_smtp_port and srv.mail_from_address):
        return None
    return SmtpConfig(
        host=srv.mail_smtp_host,
        port=int(srv.mail_smtp_port),
        user=srv.mail_smtp_user or None,
        password=decrypt_secret(srv.mail_smtp_password),
        use_tls=bool(srv.mail_smtp_use_tls),
        use_ssl=bool(srv.mail_smtp_use_ssl),
        from_address=srv.mail_from_address,
        from_name=srv.mail_from_name or None,
    )


def get_imap_config() -> Optional[ImapConfig]:
    """Return the inbound config, or None if disabled / incomplete."""
    srv = _srv()
    if srv is None or not srv.mail_imap_enabled:
        return None
    if not (srv.mail_imap_host and srv.mail_imap_port
            and srv.mail_imap_user and srv.mail_imap_password):
        return None
    pw = decrypt_secret(srv.mail_imap_password)
    if not pw:
        return None
    return ImapConfig(
        host=srv.mail_imap_host,
        port=int(srv.mail_imap_port),
        user=srv.mail_imap_user,
        password=pw,
        use_ssl=bool(srv.mail_imap_use_ssl),
        mailbox=srv.mail_imap_mailbox or 'INBOX',
        poll_interval_sec=int(srv.mail_imap_poll_interval_sec or 300),
        max_attachment_mb=int(srv.mail_imap_max_attachment_mb or 20),
    )


def smtp_is_configured() -> bool:
    return get_smtp_config() is not None


def imap_is_configured() -> bool:
    return get_imap_config() is not None
