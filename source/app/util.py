#  IRIS Source Code
#  Copyright (C) 2022 - DFIR IRIS Team
#  contact@dfir-iris.org
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

# TODO should probably dispatch the methods provided in this file in the different namespaces
import base64
import datetime
import shutil
import weakref
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import hmac
from sqlalchemy.orm.attributes import flag_modified
from flask import current_app

from app.db import db
from app.blueprints.iris_user import iris_current_user


class FileRemover(object):
    def __init__(self):
        self.weak_references = dict()  # weak_ref -> filepath to remove

    def cleanup_once_done(self, response_d, filepath):
        wr = weakref.ref(response_d, self._do_cleanup)
        self.weak_references[wr] = filepath

    def _do_cleanup(self, wr):
        filepath = self.weak_references[wr]
        shutil.rmtree(filepath, ignore_errors=True)


def add_obj_history_entry(obj, action, commit=False):
    date_update = datetime.datetime.now(datetime.timezone.utc)
    timestamp = date_update.timestamp()
    utc = date_update

    if hasattr(obj, 'modification_history'):
        if isinstance(obj.modification_history, dict):
            obj.modification_history.update({
                timestamp: {
                    'user': iris_current_user.user,
                    'user_id': iris_current_user.id,
                    'action': action
                }
            })
        else:
            obj.modification_history = {
                timestamp: {
                    'user': iris_current_user.user,
                    'user_id': iris_current_user.id,
                    'action': action
                }
            }

    if hasattr(obj, 'date_update'):
        obj.date_update = utc

    flag_modified(obj, "modification_history")
    if commit:
        db.session.commit()

    return obj


def hmac_sign(data):
    key = bytes(current_app.config.get("SECRET_KEY"), "utf-8")
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    signature = base64.b64encode(h.finalize())

    return signature


def hmac_verify(signature_enc, data):
    signature = base64.b64decode(signature_enc)
    key = bytes(current_app.config.get("SECRET_KEY"), "utf-8")
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)

    try:
        h.verify(signature)
        return True
    except InvalidSignature:
        return False
