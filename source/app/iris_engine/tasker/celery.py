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

from celery import Celery
from celery.security import setup_security
from kombu.serialization import register
from app.configuration import CeleryConfig

def _patch_celery_cert_datetime():
    import datetime
    from celery.security.certificate import Certificate

    _original_has_expired = Certificate.has_expired

    def _patched_has_expired(self):
        try:
            return _original_has_expired(self)
        except TypeError:
            not_valid_after = self._cert.not_valid_after_utc
            return datetime.datetime.now(datetime.timezone.utc) >= not_valid_after

    Certificate.has_expired = _patched_has_expired


def _register_auth_serializer():
    import json

    def _encode_auth(data):
        return json.dumps(data).encode('utf-8'), 'application/auth'

    def _decode_auth(data):
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return json.loads(data)

    register('auth', _encode_auth, _decode_auth, content_type='application/auth')


def make_celery(name):
    _register_auth_serializer()

    celery_app = Celery(
        name,
        config_source=CeleryConfig
    )

    if CeleryConfig.security_key and CeleryConfig.security_certificate:
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
