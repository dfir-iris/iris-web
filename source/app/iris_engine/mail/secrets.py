#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Symmetric encryption for mail credentials at rest.

`mail_smtp_password` and `mail_imap_password` are stored as ciphertext
in `server_settings`. We derive a Fernet key from the Flask `SECRET_KEY`
(which every deployment already sets and rotates alongside session
keys) so we don't introduce a new secret to manage.

Rotating `SECRET_KEY` will invalidate any previously stored mail
password — the admin will need to re-enter them. That's acceptable
and mirrors how session cookies behave on rotation.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

from app import app


logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    """Derive a Fernet key from `SECRET_KEY`.

    Fernet requires a URL-safe base64-encoded 32-byte key; SHA-256 of
    the SECRET_KEY gives us those 32 bytes deterministically without
    forcing the operator to add another config knob.
    """
    secret = app.config.get('SECRET_KEY') or ''
    if not secret:
        # Fail loud in dev — a missing SECRET_KEY would let anyone read
        # the "encrypted" password because the derived key is public.
        raise RuntimeError(
            'SECRET_KEY must be set to encrypt mail credentials'
        )
    digest = hashlib.sha256(secret.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: Optional[str]) -> Optional[str]:
    """Return the ciphertext for `plaintext`, or None if empty."""
    if plaintext is None or plaintext == '':
        return None
    token = _fernet().encrypt(plaintext.encode('utf-8'))
    return token.decode('ascii')


def decrypt_secret(ciphertext: Optional[str]) -> Optional[str]:
    """Return the plaintext of `ciphertext`, or None on empty/bad input.

    Failures are logged and return None so a mis-rotated key blocks
    mail delivery (which surfaces cleanly in worker logs) rather than
    crashing the request that queued it.
    """
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode('ascii')).decode('utf-8')
    except (InvalidToken, ValueError) as exc:
        logger.error(
            'Failed to decrypt mail secret — likely a SECRET_KEY '
            'rotation; the admin must re-enter the password. (%s)', exc,
        )
        return None
