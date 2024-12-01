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
import hashlib
import logging as log
import marshmallow
import shutil
import weakref
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import hmac
from flask_login import current_user
from pathlib import Path
from pyunpack import Archive
from sqlalchemy.orm.attributes import flag_modified

from app import app
from app import db


class FileRemover(object):
    def __init__(self):
        self.weak_references = dict()  # weak_ref -> filepath to remove

    def cleanup_once_done(self, response_d, filepath):
        wr = weakref.ref(response_d, self._do_cleanup)
        self.weak_references[wr] = filepath

    def _do_cleanup(self, wr):
        filepath = self.weak_references[wr]
        shutil.rmtree(filepath, ignore_errors=True)


def decompress_7z(filename: Path, output_dir):
    """
    Decompress a 7z file in specified output directory
    :param filename: Filename to decompress
    :param output_dir: Target output dir
    :return: True if uncompress
    """
    try:
        a = Archive(filename=filename)
        a.extractall(directory=output_dir, auto_create_dir=True)

    except Exception as e:
        log.warning(e)
        return False

    return True


def add_obj_history_entry(obj, action, commit=False):
    if hasattr(obj, 'modification_history'):

        if isinstance(obj.modification_history, dict):

            obj.modification_history.update({
                datetime.datetime.now().timestamp(): {
                    'user': current_user.user,
                    'user_id': current_user.id,
                    'action': action
                }
            })

        else:

            obj.modification_history = {
                datetime.datetime.now().timestamp(): {
                    'user': current_user.user,
                    'user_id': current_user.id,
                    'action': action
                }
            }
    flag_modified(obj, "modification_history")
    if commit:
        db.session.commit()

    return obj


def file_sha256sum(file_path):

    if not Path(file_path).is_file():
        return None

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

        return sha256_hash.hexdigest().upper()


def stream_sha256sum(stream):

    return hashlib.sha256(stream).hexdigest().upper()


@app.template_filter()
def format_datetime(value, frmt):
    return datetime.datetime.fromtimestamp(float(value)).strftime(frmt)


def hmac_sign(data):
    key = bytes(app.config.get("SECRET_KEY"), "utf-8")
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)
    signature = base64.b64encode(h.finalize())

    return signature


def hmac_verify(signature_enc, data):
    signature = base64.b64decode(signature_enc)
    key = bytes(app.config.get("SECRET_KEY"), "utf-8")
    h = hmac.HMAC(key, hashes.SHA256())
    h.update(data)

    try:
        h.verify(signature)
        return True
    except InvalidSignature:
        return False


def str_to_bool(value):
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return bool(value)

    return value.lower() in ['true', '1', 'yes', 'y', 't']


def assert_type_mml(input_var: any, field_name: str,  type: type, allow_none: bool = False,
                    max_len: int = None, max_val: int = None, min_val: int = None):
    if input_var is None:
        if allow_none is False:
            raise marshmallow.ValidationError("Invalid data - non null expected",
                                            field_name=field_name if field_name else "type")
        else:
            return True
    
    if isinstance(input_var, type):
        if max_len:
            if len(input_var) > max_len:
                raise marshmallow.ValidationError("Invalid data - max length exceeded",
                                                field_name=field_name if field_name else "type")

        if max_val:
            if input_var > max_val:
                raise marshmallow.ValidationError("Invalid data - max value exceeded",
                                                field_name=field_name if field_name else "type")

        if min_val:
            if input_var < min_val:
                raise marshmallow.ValidationError("Invalid data - min value exceeded",
                                                field_name=field_name if field_name else "type")

        return True
    
    try:

        if isinstance(type(input_var), type):
            return True

    except Exception as e:
        log.error(e)
        print(e)
        
    raise marshmallow.ValidationError("Invalid data type",
                                      field_name=field_name if field_name else "type")
