#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Mail subsystem — outbound (SMTP) + inbound (IMAP) + rules engine."""

from app.iris_engine.mail.outbound import mail_send_system
from app.iris_engine.mail.outbound import send_notification_email
from app.iris_engine.mail.inbound import poll_inbound_mail
from app.iris_engine.mail.rules import evaluate_rules

__all__ = [
    'mail_send_system',
    'send_notification_email',
    'poll_inbound_mail',
    'evaluate_rules',
]
