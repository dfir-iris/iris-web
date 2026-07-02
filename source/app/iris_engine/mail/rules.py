#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Rule evaluator for inbound mail.

Rules are ordered by `priority ASC` (lower runs first). The first
enabled rule whose predicates all match decides the action. If no
rule matches, the caller falls back to a shipped default (create
an alert on the first customer, low severity — the admin can
override this by adding an explicit catch-all rule).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.models.mail import MailIngestRule


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParsedMail:
    """The subset of mail fields the router cares about.

    Fully separated from any IMAP client type so the evaluator can be
    unit-tested without a live server (see tests/.../test_rules.py).
    """
    message_id: str
    from_addr: str
    to_addrs: tuple
    subject: str
    body_text: str
    body_html: Optional[str]
    date: Optional[object]  # datetime or None
    attachments: tuple      # tuple of (filename, mime, bytes)


def _regex_matches(pattern: Optional[str], value: Optional[str]) -> bool:
    """None predicate matches anything. Bad regex is treated as a
    non-match and logged — an admin typo shouldn't crash the poller.
    """
    if not pattern:
        return True
    if value is None:
        return False
    try:
        return re.search(pattern, value, re.IGNORECASE) is not None
    except re.error as exc:
        logger.warning('Invalid regex %r in mail_ingest_rule: %s', pattern, exc)
        return False


def evaluate_rules(mail: ParsedMail) -> Optional[MailIngestRule]:
    """Return the first matching enabled rule, or None if none match.

    Predicates are AND-composed within a rule and OR-composed across
    the `to_addrs` list (a message with 3 recipients matches if any
    of them matches the `to_regex`).
    """
    rules = (
        MailIngestRule.query
        .filter(MailIngestRule.enabled.is_(True))
        .order_by(MailIngestRule.priority.asc(), MailIngestRule.id.asc())
        .all()
    )
    for rule in rules:
        if not _regex_matches(rule.match_subject_regex, mail.subject):
            continue
        if not _regex_matches(rule.match_from_regex, mail.from_addr):
            continue
        if rule.match_to_regex:
            if not any(
                _regex_matches(rule.match_to_regex, addr)
                for addr in mail.to_addrs
            ):
                continue
        return rule
    return None
