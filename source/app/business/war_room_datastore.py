#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""War-room datastore business layer.

Each war room gets its own subdirectory under the configured
`DATASTORE_PATH/war_rooms/<id>/`. The `WarRoomDatastoreFile` row holds
metadata (filename, size, sha256, mime, uploaded_by); the bytes live
on disk under a hashed name so two uploads with the same filename
don't clobber each other.
"""

import hashlib
import os
import uuid

from flask import current_app

from app.db import db
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomCase
from app.models.war_rooms import WarRoomDatastoreFile


_MAX_BYTES = 200 * 1024 * 1024  # 200 MiB per file — same ceiling as cases
_FILENAME_MAX = 512


def _datastore_root():
    return current_app.config.get(
        'DATASTORE_PATH', '/home/iris/server_data/datastore'
    )


def _war_room_dir(war_room_id):
    root = _datastore_root()
    return os.path.join(root, 'war_rooms', str(war_room_id))


def _sanitize_filename(name):
    if not isinstance(name, str) or not name.strip():
        raise BusinessProcessingError('filename is required')
    base = os.path.basename(name).strip()
    if not base or base in ('.', '..'):
        raise BusinessProcessingError('Invalid filename')
    return base[:_FILENAME_MAX]


def war_room_datastore_list(war_room_id, include_attached_cases=True):
    """Return the war-room's own files.

    `include_attached_cases` is currently informational — the SPA
    fetches per-case datastore listings via the existing case
    endpoints. We don't aggregate server-side here because that would
    require teaching this layer about case-level access nuances; the
    SPA already has the per-case ACL coverage.
    """
    rows = (
        WarRoomDatastoreFile.query
        .filter(WarRoomDatastoreFile.war_room_id == war_room_id)
        .order_by(WarRoomDatastoreFile.uploaded_at.desc())
        .all()
    )
    return rows


def war_room_datastore_get(war_room_id, file_id):
    row = WarRoomDatastoreFile.query.filter_by(
        war_room_id=war_room_id, file_id=file_id
    ).first()
    if row is None:
        raise ObjectNotFoundError()
    return row


def war_room_datastore_save(war_room_id, file_stream, filename,
                             mime_type=None, description=None, tags=None,
                             uploaded_by_id=None):
    """Persist an uploaded file.

    Streams to disk in 64 KiB chunks while updating a sha256 hash, so
    we never load the entire upload into memory. Caller is expected to
    have already validated war-room write access.
    """
    filename = _sanitize_filename(filename)
    dirpath = _war_room_dir(war_room_id)
    os.makedirs(dirpath, exist_ok=True)

    # Random suffix prevents collision while keeping the original
    # filename in the DB row for the UI.
    storage_name = f'{uuid.uuid4().hex}_{filename}'
    storage_path = os.path.join(dirpath, storage_name)

    hasher = hashlib.sha256()
    total = 0
    with open(storage_path, 'wb') as out:
        while True:
            chunk = file_stream.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_BYTES:
                out.close()
                try:
                    os.remove(storage_path)
                except OSError:
                    pass
                raise BusinessProcessingError(
                    f'File exceeds {_MAX_BYTES // (1024 * 1024)} MiB cap'
                )
            hasher.update(chunk)
            out.write(chunk)

    if total == 0:
        try:
            os.remove(storage_path)
        except OSError:
            pass
        raise BusinessProcessingError('Empty file')

    row = WarRoomDatastoreFile()
    row.war_room_id = war_room_id
    row.filename = filename
    row.description = description
    row.storage_path = storage_path
    row.size_bytes = total
    row.mime_type = mime_type
    row.sha256 = hasher.hexdigest()
    row.uploaded_by_id = uploaded_by_id
    row.tags = tags
    db.session.add(row)
    db.session.commit()
    return row


def war_room_datastore_open(row):
    """Return a binary file handle to the stored bytes."""
    if not row.storage_path or not os.path.exists(row.storage_path):
        raise ObjectNotFoundError()
    return open(row.storage_path, 'rb')


def war_room_datastore_delete(war_room_id, file_id):
    row = war_room_datastore_get(war_room_id, file_id)
    path = row.storage_path
    db.session.delete(row)
    db.session.commit()
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            # Don't roll back the DB delete — leaving an orphan blob is
            # less bad than leaving the row pointing at it.
            pass


def war_room_attached_cases(war_room_id):
    """Convenience used by the SPA to fan out per-case datastore reads."""
    rows = (
        WarRoomCase.query
        .with_entities(WarRoomCase.case_id)
        .filter(WarRoomCase.war_room_id == war_room_id)
        .all()
    )
    return [r.case_id for r in rows]
