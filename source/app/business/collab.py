#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Business layer for the real-time collaborative editor (Option A).

Server-authoritative Yjs. The server keeps the canonical Y.Doc for each
open document in `collab_doc.y_state` and:

  1. Resolves a `doc_name` (like `note:42`, `case-summary:17`,
     `war-room-note:8`, `sitrep:5`) to (a) the object, (b) the caller's
     access level, (c) whether writes are currently allowed.
  2. Guarantees a Y.Doc exists for the document, migrating from the
     source column exactly once via the markdown→Y.Doc renderer.
  3. Applies every client update to the authoritative Y.Doc (via
     `pycrdt`) before rebroadcasting, so we KNOW the canonical state
     rather than trusting a client's dump of it.
  4. Renders the Y.Doc back to markdown on flush and writes it to the
     source column so REST readers / search / exports stay coherent.

Design rules — kept short so they're easy to enforce during review:
  * `content_md` NEVER travels on the collab wire. Removed from every
    inbound and outbound message.
  * The client never seeds the editor from the source column. Only
    from `y_state`.
  * The server never trusts a client's markdown. It only trusts
    Yjs updates, which are CRDT-safe by construction.
"""

import base64
import datetime

from app.business.access_controls import ac_fast_check_user_has_case_access
from app.db import db
from app.iris_engine.collab.render import markdown_to_ydoc_update
from app.iris_engine.collab.render import ydoc_update_to_markdown
from app.iris_engine.utils.tracker import track_activity
from app.models.authorization import CaseAccessLevel
from app.models.authorization import WarRoomAccessLevel
from app.models.cases import Cases
from app.models.collab import CollabDoc
from app.models.models import Notes
from app.models.war_rooms import WarRoom
from app.models.war_rooms import WarRoomNote
from app.models.war_rooms import WarRoomSitRep


def _war_room_access_check(user_id, war_room_id, levels):
    """Late-import wrapper around `ac_fast_check_user_has_war_room_access`.

    `app.business.war_rooms_access` pulls in several models that
    transitively re-import this module, so a top-level import here would
    trip a circular-import error at app-load time. Every existing caller
    of this helper in the codebase does the same lazy import (see
    `access_controls.ac_fast_check_current_user_has_war_room_access` for
    the canonical example) — we're just following the convention.
    """
    from app.business.war_rooms_access import ac_fast_check_user_has_war_room_access
    return ac_fast_check_user_has_war_room_access(user_id, war_room_id, levels)


class DocResolutionError(Exception):
    """Raised when a doc_name can't be parsed or its target doesn't exist."""


# Doc kinds we recognise. Any doc_name whose prefix isn't in this map is
# rejected up-front — keeps the socket handler from spawning arbitrary
# rooms based on client input.
_DOC_KINDS = {'note', 'case-summary', 'war-room-note', 'war-room-summary', 'sitrep'}


def _parse_doc_name(doc_name):
    """Split `<kind>:<id>` into (kind, int_id). Validates the shape and
    the kind whitelist; caller-facing errors are `DocResolutionError`."""
    if not isinstance(doc_name, str) or ':' not in doc_name:
        raise DocResolutionError('doc_name must be "<kind>:<id>"')
    kind, _, raw_id = doc_name.partition(':')
    if kind not in _DOC_KINDS:
        raise DocResolutionError(f'Unknown doc kind: {kind!r}')
    try:
        obj_id = int(raw_id)
    except (TypeError, ValueError):
        raise DocResolutionError('doc_name id must be an integer')
    return kind, obj_id


def resolve_doc(doc_name, user_id):
    """Look up the object referenced by `doc_name` and the caller's
    permissions.

    Returns a dict:
        {
          'kind': str,
          'id': int,
          'exists': bool,
          'can_read': bool,
          'can_write': bool,
          'current_content': str | None,   # source-column markdown
        }

    `current_content` is used exclusively to seed the Y.Doc on first
    open of a doc (see `ensure_snapshot` below). It does NOT travel to
    the client — the client only ever sees Yjs update bytes.

    Raises `DocResolutionError` for bad shapes; permission failures are
    reported as `can_read=False` / `can_write=False`, NOT raised, so
    the socket layer can respond with a rejection event rather than a
    Python exception.
    """
    kind, obj_id = _parse_doc_name(doc_name)

    if kind == 'note':
        note = Notes.query.filter_by(note_id=obj_id).first()
        if note is None:
            return {'kind': kind, 'id': obj_id, 'exists': False,
                    'can_read': False, 'can_write': False,
                    'current_content': None}
        # Note ACL rides on the parent case's ACL. Two separate calls
        # (write, then read) because `CaseAccessLevel` is a plain
        # `enum.Enum`, so we can't just compare the returned int to
        # the enum member. See the war-room branches for the same
        # pattern.
        write_level = ac_fast_check_user_has_case_access(
            user_id, note.note_case_id, [CaseAccessLevel.full_access],
        )
        read_level = write_level or ac_fast_check_user_has_case_access(
            user_id, note.note_case_id, [CaseAccessLevel.read_only],
        )
        return {'kind': kind, 'id': obj_id, 'exists': True,
                'can_read': read_level is not None,
                'can_write': write_level is not None,
                'current_content': note.note_content}

    if kind == 'case-summary':
        case = Cases.query.filter_by(case_id=obj_id).first()
        if case is None:
            return {'kind': kind, 'id': obj_id, 'exists': False,
                    'can_read': False, 'can_write': False,
                    'current_content': None}
        write_level = ac_fast_check_user_has_case_access(
            user_id, case.case_id, [CaseAccessLevel.full_access],
        )
        read_level = write_level or ac_fast_check_user_has_case_access(
            user_id, case.case_id, [CaseAccessLevel.read_only],
        )
        return {'kind': kind, 'id': obj_id, 'exists': True,
                'can_read': read_level is not None,
                'can_write': write_level is not None,
                'current_content': case.description}

    if kind == 'war-room-note':
        wrn = WarRoomNote.query.filter_by(note_id=obj_id).first()
        if wrn is None:
            return {'kind': kind, 'id': obj_id, 'exists': False,
                    'can_read': False, 'can_write': False,
                    'current_content': None}
        write_level = _war_room_access_check(
            user_id, wrn.war_room_id, [WarRoomAccessLevel.full_access],
        )
        read_level = write_level or _war_room_access_check(
            user_id, wrn.war_room_id, [WarRoomAccessLevel.read_only],
        )
        return {'kind': kind, 'id': obj_id, 'exists': True,
                'can_read': read_level is not None,
                'can_write': write_level is not None,
                'current_content': wrn.content}

    if kind == 'war-room-summary':
        room = WarRoom.query.filter_by(war_room_id=obj_id).first()
        if room is None:
            return {'kind': kind, 'id': obj_id, 'exists': False,
                    'can_read': False, 'can_write': False,
                    'current_content': None}
        write_level = _war_room_access_check(
            user_id, room.war_room_id, [WarRoomAccessLevel.full_access],
        )
        read_level = write_level or _war_room_access_check(
            user_id, room.war_room_id, [WarRoomAccessLevel.read_only],
        )
        return {'kind': kind, 'id': obj_id, 'exists': True,
                'can_read': read_level is not None,
                'can_write': write_level is not None,
                'current_content': room.description}

    if kind == 'sitrep':
        sit = WarRoomSitRep.query.filter_by(sitrep_id=obj_id).first()
        if sit is None:
            return {'kind': kind, 'id': obj_id, 'exists': False,
                    'can_read': False, 'can_write': False,
                    'current_content': None}
        write_level = _war_room_access_check(
            user_id, sit.war_room_id, [WarRoomAccessLevel.full_access],
        )
        read_level = write_level or _war_room_access_check(
            user_id, sit.war_room_id, [WarRoomAccessLevel.read_only],
        )
        # Published sitreps are read-only regardless of ACL level.
        can_write = write_level is not None and not sit.published
        return {'kind': kind, 'id': obj_id, 'exists': True,
                'can_read': read_level is not None,
                'can_write': can_write,
                'current_content': sit.body_md}

    raise DocResolutionError(f'Unhandled doc kind: {kind!r}')


# ---------------------------------------------------------------------------
# Snapshot storage — server-authoritative Y.Doc bytes.
# ---------------------------------------------------------------------------

# Bump this whenever `iris_engine.collab.render` grows a new block
# type (tables, task lists, footnotes…). `ensure_snapshot` re-seeds
# rows whose stored `seeder_version` is below the current value from
# the up-to-date source column, so users don't stay stuck on the
# previous parser's lossy output. Historical bumps:
#   1 — GFM pipe tables (Jul 2026). The CommonMark parser silently
#       dropped tables, so any legacy note with a table lost its
#       tabular structure after the first open.
_CURRENT_SEEDER_VERSION = 1


def ensure_snapshot(doc_name, current_content):
    """Return the authoritative `y_state` bytes for `doc_name`, creating
    it from the source column if this is a first open.

    Guarantees:
      * A `CollabDoc` row exists after this call.
      * The row's `y_state` is a non-empty Yjs update representing the
        current authoritative Y.Doc.
      * The one-time migration from markdown to Y.Doc happens exactly
        once per document, atomically — UNLESS the row's `seeder_version`
        is below `_CURRENT_SEEDER_VERSION`, in which case we re-seed
        from `current_content` so the doc picks up whatever the newer
        parser can now express.

    The returned bytes are what we ship in `sync-init`. Every client
    hydrates from these bytes and only these bytes — there's no
    fallback path.
    """
    row = CollabDoc.query.filter_by(doc_name=doc_name).first()
    stored_version = getattr(row, 'seeder_version', None) if row is not None else None
    is_current_version = stored_version == _CURRENT_SEEDER_VERSION
    if row is not None and row.y_state and is_current_version:
        return bytes(row.y_state)

    # Re-seed. Reaches this branch on:
    #   * first open of a doc (`row is None`),
    #   * DB tampering that emptied `y_state` (`not row.y_state`),
    #   * or a seeder-version bump landing on an existing row
    #     (`stored_version < _CURRENT_SEEDER_VERSION`).
    # In the last case we DISCARD the stored y_state and re-parse
    # the source column, because the old y_state was produced by a
    # parser that couldn't represent the new block types — keeping
    # it would leave users unable to see content they know is in
    # `note.note_content` / `case.description` / etc.
    seed_md = current_content or ''
    seed_bytes = markdown_to_ydoc_update(seed_md)

    if row is None:
        row = CollabDoc(
            doc_name=doc_name,
            y_state=seed_bytes,
            content_md=seed_md,
            seeder_version=_CURRENT_SEEDER_VERSION,
            last_flushed_at=datetime.datetime.utcnow(),
        )
        db.session.add(row)
    else:
        row.y_state = seed_bytes
        row.content_md = seed_md
        row.seeder_version = _CURRENT_SEEDER_VERSION
        row.last_flushed_at = datetime.datetime.utcnow()
    db.session.commit()
    return seed_bytes


def apply_wire_update(doc_name, update_b64, user_id):
    """Apply an incoming Yjs update from a client to the authoritative
    Y.Doc for `doc_name`, then persist the merged state.

    Returns the ORIGINAL client update bytes (base64-decoded) so the
    socket layer can rebroadcast them to peers. CRDTs are commutative —
    peers applying the same update independently converge to the same
    state as the server's Y.Doc.

    Returns None if the update is malformed or the doc has never been
    initialised (caller should have called `ensure_snapshot` first).
    """
    row = CollabDoc.query.filter_by(doc_name=doc_name).first()
    if row is None or not row.y_state:
        # Should be unreachable — the socket handler calls
        # `ensure_snapshot` on join, so every write path sees an
        # initialised row. If we get here it's a bug in the caller.
        return None

    try:
        update_bytes = base64.b64decode(update_b64) if update_b64 else b''
    except (TypeError, ValueError):
        return None
    if not update_bytes:
        return None

    from pycrdt import merge_updates
    try:
        # Merge the incoming update INTO the stored state at the
        # byte-blob level. `merge_updates` is the pycrdt/Yrs helper for
        # combining update blobs without needing to materialise a full
        # Doc — much cheaper than apply+get_update on hot paths. It's
        # a variadic (not a list), hence the star-splat.
        new_state = merge_updates(bytes(row.y_state), update_bytes)
    except Exception:
        # Malformed update — drop it. Peers won't see the broadcast
        # either (caller checks the return value).
        return None

    row.y_state = new_state
    row.updated_by_id = user_id
    row.last_flushed_at = datetime.datetime.utcnow()
    db.session.commit()

    return update_bytes


def flush_to_source(doc_name):
    """Render the Y.Doc to markdown and write it to the source column
    if it changed.

    Called on last-client-disconnect (and, in a future revision, on a
    periodic tick). Fires the existing `track_activity()` hook so the
    audit log records who last touched the doc.

    Uses `ydoc_update_to_markdown` to render — the only place in the
    server that reads editor content out of Yjs. No-op if the doc row
    doesn't exist or the render matches what's already in the column.
    """
    row = CollabDoc.query.filter_by(doc_name=doc_name).first()
    if row is None or not row.y_state:
        return

    try:
        kind, obj_id = _parse_doc_name(doc_name)
    except DocResolutionError:
        return

    try:
        new_content = ydoc_update_to_markdown(bytes(row.y_state))
    except Exception:
        # Never let a bad snapshot break the audit path — keep the
        # source column as-is until a subsequent flush succeeds.
        return

    # Keep the cached markdown in the row so a REST reader can consume
    # it without booting a Y.Doc. Also lets us skip the source-column
    # UPDATE when there's no meaningful change.
    if row.content_md != new_content:
        row.content_md = new_content
        db.session.commit()

    if kind == 'note':
        note = Notes.query.filter_by(note_id=obj_id).first()
        if note is None or note.note_content == new_content:
            return
        note.note_content = new_content
        db.session.commit()
        track_activity(f'updated note "{note.note_title}"',
                       caseid=note.note_case_id)
        return

    if kind == 'case-summary':
        case = Cases.query.filter_by(case_id=obj_id).first()
        if case is None or case.description == new_content:
            return
        case.description = new_content
        db.session.commit()
        track_activity(f'updated case summary', caseid=case.case_id)
        return

    if kind == 'war-room-note':
        wrn = WarRoomNote.query.filter_by(note_id=obj_id).first()
        if wrn is None or wrn.content == new_content:
            return
        wrn.content = new_content
        db.session.commit()
        track_activity(f'updated war room note "{wrn.title}"',
                       war_room_id=wrn.war_room_id)
        return

    if kind == 'war-room-summary':
        room = WarRoom.query.filter_by(war_room_id=obj_id).first()
        if room is None or room.description == new_content:
            return
        room.description = new_content
        db.session.commit()
        track_activity(f'updated war room summary',
                       war_room_id=room.war_room_id)
        return

    if kind == 'sitrep':
        sit = WarRoomSitRep.query.filter_by(sitrep_id=obj_id).first()
        # Never flush into a published sitrep — the ACL layer already
        # blocks writes, but this belt-and-braces guard prevents a
        # rogue queued flush from mutating a locked report.
        if sit is None or sit.published or sit.body_md == new_content:
            return
        sit.body_md = new_content
        db.session.commit()
        track_activity(
            f'updated sitrep "{sit.title}" (v{sit.version})',
            war_room_id=sit.war_room_id,
        )
        return
