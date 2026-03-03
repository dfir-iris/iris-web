#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

import os
import json
from datetime import datetime, date, timezone
from celery import Celery
from celery.security import setup_security
from kombu.serialization import register
from app.configuration import CeleryConfig


def _patch_celery_cert_loading():
    """Patch Celery's Certificate class to work with newer cryptography library."""
    from celery.security import certificate
    from cryptography import x509
    
    _original_init = certificate.Certificate.__init__
    
    def _patched_init(self, *args, **kwargs):
        try:
            _original_init(self, *args, **kwargs)
        except Exception as e:
            if 'MalformedFraming' in str(e):
                cert_path = args[0] if args else kwargs.get('path', '')
                with open(cert_path, 'rb') as f:
                    self._cert = x509.load_pem_x509_certificate(f.read())
            else:
                raise
    
    certificate.Certificate.__init__ = _patched_init


def _patch_celery_cert_datetime():
    from celery.security.certificate import Certificate

    _original_has_expired = Certificate.has_expired

    def _patched_has_expired(self):
        try:
            return _original_has_expired(self)
        except (TypeError, AttributeError):
            try:
                not_valid_after = self._cert.not_valid_after_utc
                return datetime.now(timezone.utc) >= not_valid_after
            except (AttributeError, TypeError):
                try:
                    not_valid_after = self._cert.not_valid_after
                    return datetime.now(timezone.utc) >= not_valid_after.replace(tzinfo=timezone.utc)
                except Exception:
                    return False

    Certificate.has_expired = _patched_has_expired


def _register_auth_serializer():
    """Register a minimal auth serializer before setup_security() is called.
    The actual message signing is handled by setup_security().
    This is needed because setup_security() tries to enable the auth serializer
    but it must be registered first."""
    
    def _encode_auth(data):
        return json.dumps(data).encode('utf-8'), 'application/auth'

    def _decode_auth(data):
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return json.loads(data)

    register('auth', _encode_auth, _decode_auth, content_type='application/auth')


def _check_certificate_files():
    key_path = CeleryConfig.security_key
    cert_path = CeleryConfig.security_certificate
    store_path = CeleryConfig.security_cert_store
    
    if not key_path or not cert_path or not store_path:
        return False
    
    if not os.path.exists(key_path):
        return False
    if not os.path.exists(cert_path):
        return False
    if not os.path.exists(store_path):
        return False
    
    return True


def make_celery(name):
    celery_app = Celery(
        name,
        config_source=CeleryConfig
    )

    if _check_certificate_files():
        _register_auth_serializer()
        _patch_celery_cert_loading()
        _patch_celery_cert_datetime()
        setup_security(
            allowed_serializers=['auth'],
            key=CeleryConfig.security_key,
            cert=CeleryConfig.security_certificate,
            store=CeleryConfig.security_cert_store,
            digest=CeleryConfig.security_digest
        )

    return celery_app


def set_celery_flask_context(celery: Celery, app):
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
