#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Business layer for the war-room chat stream.

The chat is a single chronological stream per war room. Operator
messages live alongside system rows we synthesise from events
elsewhere in IRIS — case activity ingest, task assignments, SitRep
publications. Sub-tabs filter client-side on the `kind` column.

Slash commands (`/task`, `/attach`, `/sitrep`, `/pin`, `/note`) are
resolved server-side: the route layer dispatches them to the
appropriate sub-system and writes a corresponding `kind=*` row to the
stream so the audit trail stays in one place.
"""

import datetime
import re

from sqlalchemy import and_, desc

from app.db import db
from app.models.authorization import User
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomChatMessage
from app.models.war_rooms import WarRoomChatReaction


_BODY_MAX_LEN = 16_384
_PAGE_DEFAULT = 50
_PAGE_MAX = 200
_DATETIME_MIN = datetime.datetime.min


_VALID_KINDS = {
    'message', 'system',
    'task_assigned', 'task_completed',
    'case_attached', 'case_detached',
    'case_activity',
    'sitrep_published', 'note', 'pin',
    # `decision` rows are first-class so the SitRep author can lift them
    # straight out via a future timeline-of-decisions query; they
    # otherwise behave like a richer `/note`.
    'decision',
    # `priority` flags a banner-style row stamped when the operator flips
    # the war room into a hotter posture via `/priority` or `/state`.
    'priority',
}


# --- Activity classifier --------------------------------------------------
#
# Patterns derived from the verbs IRIS's business layer feeds into
# `track_activity()`. Order matters: more specific patterns first. Anything
# that doesn't match falls through to `case.other` so the row still shows
# up in the unfiltered stream view.
import re as _re

_ACTIVITY_RULES = [
    (_re.compile(r'^new case '), 'case.created'),
    (_re.compile(r'^case closed$', _re.IGNORECASE), 'case.closed'),
    (_re.compile(r'^case re-opened$', _re.IGNORECASE), 'case.reopened'),
    (_re.compile(r'^case updated', _re.IGNORECASE), 'case.updated'),
    (_re.compile(r'^case reviewer', _re.IGNORECASE), 'case.reviewer_changed'),
    (_re.compile(r'^closed case id', _re.IGNORECASE), 'case.closed'),

    (_re.compile(r'^created note', _re.IGNORECASE), 'note.created'),
    (_re.compile(r'^updated note', _re.IGNORECASE), 'note.updated'),
    (_re.compile(r'^deleted note revision', _re.IGNORECASE), 'note.updated'),
    (_re.compile(r'^deleted note', _re.IGNORECASE), 'note.deleted'),
    (_re.compile(r'^added directory', _re.IGNORECASE), 'directory.created'),
    (_re.compile(r'^modified directory', _re.IGNORECASE), 'directory.updated'),
    (_re.compile(r'^deleted directory', _re.IGNORECASE), 'directory.deleted'),

    (_re.compile(r'^added ioc', _re.IGNORECASE), 'ioc.created'),
    (_re.compile(r'^updated ioc', _re.IGNORECASE), 'ioc.updated'),
    (_re.compile(r'^deleted ioc', _re.IGNORECASE), 'ioc.deleted'),

    (_re.compile(r'^added asset', _re.IGNORECASE), 'asset.created'),
    (_re.compile(r'^updated asset', _re.IGNORECASE), 'asset.updated'),
    (_re.compile(r'^(deleted|removed) asset', _re.IGNORECASE), 'asset.deleted'),

    (_re.compile(r'^added evidence', _re.IGNORECASE), 'evidence.created'),
    (_re.compile(r'^updated evidence', _re.IGNORECASE), 'evidence.updated'),
    (_re.compile(r'^deleted evidence', _re.IGNORECASE), 'evidence.deleted'),

    (_re.compile(r'^added task', _re.IGNORECASE), 'task.created'),
    (_re.compile(r'^updated task', _re.IGNORECASE), 'task.updated'),
    (_re.compile(r'^deleted task', _re.IGNORECASE), 'task.deleted'),

    (_re.compile(r'^added event', _re.IGNORECASE), 'event.created'),
    (_re.compile(r'^updated event', _re.IGNORECASE), 'event.updated'),
    (_re.compile(r'^deleted event', _re.IGNORECASE), 'event.deleted'),

    (_re.compile(r'^(linked|unlinked) alert', _re.IGNORECASE), 'alert.linked'),
]


def classify_activity_text(text):
    """Map a tracked activity description to a fine-grained type slug.

    The IRIS tracker capitalises the first letter of every message, so
    we match case-insensitively. Returns `'case.other'` when nothing
    fits; the stream still surfaces those under the "Other" toggle.
    """
    if not isinstance(text, str) or not text:
        return 'case.other'
    for pattern, slug in _ACTIVITY_RULES:
        if pattern.search(text):
            return slug
    return 'case.other'


def _validate_kind(kind):
    if kind is None:
        return 'message'
    if not isinstance(kind, str) or kind not in _VALID_KINDS:
        raise BusinessProcessingError(f'Invalid message kind: {kind}')
    return kind


def _validate_body(body, kind):
    if body is None:
        # System messages may carry no body (the ref_id + ref_type carry
        # the meaning). Operator-authored messages must have content.
        if kind == 'message':
            raise BusinessProcessingError('Message body is required')
        return None
    if not isinstance(body, str):
        raise BusinessProcessingError('Message body must be a string')
    stripped = body.strip()
    if kind == 'message' and not stripped:
        raise BusinessProcessingError('Message body is required')
    if len(body) > _BODY_MAX_LEN:
        raise BusinessProcessingError(
            f'Message body must be at most {_BODY_MAX_LEN} characters'
        )
    return body


def _virtual_activity_row(ua_row, war_room_id):
    """Wrap a UserActivity row as a chat-list row.

    Same shape the REST serializer expects from the chat query
    (`.message_id`, `.body`, `.kind`, `.activity_type`, `.created_at`,
    …). The message id is synthesised with a high offset (-id) so it
    never collides with a real chat message_id and the SPA can still
    treat it as a stable React-style key.
    """
    from types import SimpleNamespace
    return SimpleNamespace(
        # Negative id keeps virtual rows out of the real id space
        # without polluting the integer cursor on the chat side.
        message_id=-int(ua_row.id),
        war_room_id=war_room_id,
        author_id=ua_row.user_id,
        body=ua_row.activity_desc,
        kind='case_activity',
        ref_type='user_activity',
        ref_id=int(ua_row.id),
        ref_case_id=ua_row.case_id,
        activity_type=classify_activity_text(ua_row.activity_desc),
        created_at=ua_row.activity_date,
        edited_at=None,
        deleted_at=None,
        author_login=ua_row.user_login,
        author_name=ua_row.user_name,
    )


def _fetch_live_case_activities(war_room_id, before_dt, limit,
                                case_ids=None):
    """Pull live `UserActivity` rows for cases attached to this war room.

    Avoids the chat-table backfill: every render of the stream sees
    the up-to-date case activity, so a case attached after the war
    room was created surfaces its full history immediately, and a
    case detached drops out without leaving stale rows behind.

    The query filters by the war room's current attached-case set
    (intersected with the caller's `case_ids` filter if provided), so
    case_id mismatches just no-op.
    """
    from app.models.authorization import User
    from app.models.models import UserActivity
    from app.models.war_rooms import WarRoomCase
    from sqlalchemy import and_

    attached = (
        WarRoomCase.query
        .with_entities(WarRoomCase.case_id)
        .filter(WarRoomCase.war_room_id == war_room_id)
        .all()
    )
    attached_ids = [row.case_id for row in attached]
    if not attached_ids:
        return []
    if case_ids:
        attached_ids = [c for c in attached_ids if c in set(case_ids)]
        if not attached_ids:
            return []

    q = (
        db.session.query(
            UserActivity.id,
            UserActivity.user_id,
            UserActivity.case_id,
            UserActivity.activity_date,
            UserActivity.activity_desc,
            User.user.label('user_login'),
            User.name.label('user_name'),
        )
        .outerjoin(User, User.id == UserActivity.user_id)
        .filter(and_(
            UserActivity.case_id.in_(attached_ids),
            UserActivity.display_in_ui == True,
            # Filter out the noise the case activity panel also drops —
            # same exclusion list as `get_auto_activities`.
            UserActivity.activity_desc.notlike('[Unbound]%'),
            UserActivity.activity_desc.notlike('Started a search for %'),
            UserActivity.activity_desc.notlike('Updated global task %'),
            UserActivity.activity_desc.notlike('Created new global task %'),
            UserActivity.activity_desc.notlike('Started a new case creation %'),
        ))
    )
    if before_dt is not None:
        q = q.filter(UserActivity.activity_date < before_dt)

    rows = (
        q.order_by(desc(UserActivity.activity_date))
        .limit(limit)
        .all()
    )
    return [_virtual_activity_row(r, war_room_id) for r in rows]


def list_messages(war_room_id, before=None, limit=None, kinds=None,
                  case_ids=None):
    """Return the next page of the war-room stream, newest first.

    Two sources are merged at read time:

      1. Real chat-table rows (`WarRoomChatMessage`) — operator
         messages, war-room-level system events, SitRep publishes,
         task assignments, case attach/detach.
      2. Live `UserActivity` rows for every case currently attached
         to this war room — no backfill, no duplication. A case
         attached later instantly surfaces its full activity history;
         a case detached drops out of the stream.

    The merge sorts by `created_at` descending. `before` remains a
    chat `message_id` for backwards compatibility with the SPA's
    infinite-scroll: we resolve it to the matching row's timestamp
    and use that as the activity-side cursor.

    `kinds` filtering works as before. `case_ids` constrains both
    sides (chat-row `ref_case_id` and `UserActivity.case_id`).
    """
    if limit is None:
        limit = _PAGE_DEFAULT
    limit = min(int(limit), _PAGE_MAX)

    want_case_activity = (not kinds) or ('case_activity' in kinds)

    # Resolve the cursor to a timestamp so we can apply it to both
    # sources. None on initial load means "from now backwards".
    # `before` may be a real chat message_id (positive) or a virtual
    # UserActivity id (negative; encoded as -ua.id by
    # `_virtual_activity_row`) — handle both so infinite scroll keeps
    # working after the cursor crosses a stream-of-activity span.
    before_dt = None
    if before is not None:
        cursor_int = int(before)
        if cursor_int < 0:
            from app.models.models import UserActivity
            ua_row = (
                UserActivity.query
                .with_entities(UserActivity.activity_date)
                .filter(UserActivity.id == -cursor_int)
                .first()
            )
            if ua_row and ua_row.activity_date:
                before_dt = ua_row.activity_date
        else:
            cursor_row = (
                WarRoomChatMessage.query
                .with_entities(WarRoomChatMessage.created_at)
                .filter(WarRoomChatMessage.message_id == cursor_int)
                .first()
            )
            if cursor_row and cursor_row.created_at:
                before_dt = cursor_row.created_at

    # Drop any previously-ingested case_activity rows so we don't double
    # them up against the live UserActivity pull below — installs that
    # backfilled into the chat table before this change won't surface
    # rows twice as a result.
    #
    # We intentionally do NOT select `activity_type` from the chat row:
    # activity classification lives on live UserActivity rows (synthesised
    # below). Skipping the column keeps the endpoint working on databases
    # that haven't run the `e5a1b46c7d92` migration yet — important for
    # rolling upgrades.
    q = (
        db.session.query(
            WarRoomChatMessage.message_id,
            WarRoomChatMessage.war_room_id,
            WarRoomChatMessage.author_id,
            WarRoomChatMessage.body,
            WarRoomChatMessage.kind,
            WarRoomChatMessage.ref_type,
            WarRoomChatMessage.ref_id,
            WarRoomChatMessage.ref_case_id,
            WarRoomChatMessage.created_at,
            WarRoomChatMessage.edited_at,
            WarRoomChatMessage.deleted_at,
            User.user.label('author_login'),
            User.name.label('author_name'),
        )
        .outerjoin(User, User.id == WarRoomChatMessage.author_id)
        .filter(WarRoomChatMessage.war_room_id == war_room_id)
        .filter(WarRoomChatMessage.kind != 'case_activity')
    )
    if before is not None:
        # Real chat ids only — virtual UA ids are negative and the
        # `before_dt` clamp above already covers their case in the
        # date-based merge below.
        if int(before) > 0:
            q = q.filter(WarRoomChatMessage.message_id < int(before))
        elif before_dt is not None:
            q = q.filter(WarRoomChatMessage.created_at < before_dt)
    if kinds:
        q = q.filter(WarRoomChatMessage.kind.in_(list(kinds)))
    if case_ids:
        q = q.filter(WarRoomChatMessage.ref_case_id.in_(list(case_ids)))

    chat_rows = q.order_by(desc(WarRoomChatMessage.message_id)).limit(limit).all()

    if not want_case_activity:
        return chat_rows

    # Overfetch live activities to fill the page after merge — we'll
    # trim down to `limit` after sorting.
    activity_rows = _fetch_live_case_activities(
        war_room_id, before_dt=before_dt, limit=limit, case_ids=case_ids
    )

    # Merge by created_at desc. When timestamps tie, real chat rows
    # come first so a /command + its emitted system row stay adjacent.
    merged = list(chat_rows) + list(activity_rows)
    merged.sort(
        key=lambda r: (r.created_at or _DATETIME_MIN, r.message_id),
        reverse=True
    )
    return merged[:limit]


def create_message(war_room_id, author_id, body, kind=None,
                   ref_type=None, ref_id=None, ref_case_id=None):
    kind = _validate_kind(kind)
    body = _validate_body(body, kind)

    msg = WarRoomChatMessage()
    msg.war_room_id = war_room_id
    msg.author_id = author_id
    msg.body = body
    msg.kind = kind
    msg.ref_type = ref_type
    msg.ref_id = ref_id
    msg.ref_case_id = ref_case_id
    db.session.add(msg)
    db.session.commit()
    return msg


def get_message(war_room_id, message_id):
    msg = WarRoomChatMessage.query.filter_by(
        war_room_id=war_room_id, message_id=message_id
    ).first()
    if msg is None:
        raise ObjectNotFoundError()
    return msg


def update_message(war_room_id, message_id, author_id, body):
    msg = get_message(war_room_id, message_id)
    if msg.deleted_at is not None:
        raise BusinessProcessingError('Cannot edit a deleted message')
    if msg.kind != 'message':
        raise BusinessProcessingError('System messages cannot be edited')
    if msg.author_id != author_id:
        raise BusinessProcessingError('Only the author can edit a message')
    msg.body = _validate_body(body, 'message')
    msg.edited_at = datetime.datetime.utcnow()
    db.session.commit()
    return msg


def delete_message(war_room_id, message_id, author_id, is_admin=False):
    msg = get_message(war_room_id, message_id)
    if msg.author_id != author_id and not is_admin:
        raise BusinessProcessingError('Only the author or an admin can delete a message')
    # Soft-delete so the audit trail stays intact and any thread
    # references remain valid.
    msg.deleted_at = datetime.datetime.utcnow()
    msg.body = None
    db.session.commit()


# ----- Reactions -----------------------------------------------------------

def toggle_reaction(war_room_id, message_id, user_id, emoji):
    """Add the reaction if absent, remove it if present.

    Returns the resulting state — True if added, False if removed.
    """
    if not isinstance(emoji, str) or not 1 <= len(emoji) <= 32:
        raise BusinessProcessingError('Invalid emoji')

    # The message must belong to the war room — prevents a forged
    # reaction call that hops between rooms.
    msg = get_message(war_room_id, message_id)

    existing = (
        WarRoomChatReaction.query
        .filter_by(message_id=msg.message_id, user_id=user_id, emoji=emoji)
        .first()
    )
    if existing is not None:
        db.session.delete(existing)
        db.session.commit()
        return False

    row = WarRoomChatReaction()
    row.message_id = msg.message_id
    row.user_id = user_id
    row.emoji = emoji
    db.session.add(row)
    db.session.commit()
    return True


def list_reactions(message_ids):
    """Return `{message_id: [{emoji, count, user_ids: [...]}, ...]}`.

    Called by the message-list endpoint so the SPA gets reactions
    pre-aggregated and doesn't fire a round-trip per row.
    """
    if not message_ids:
        return {}
    rows = (
        WarRoomChatReaction.query
        .with_entities(
            WarRoomChatReaction.message_id,
            WarRoomChatReaction.user_id,
            WarRoomChatReaction.emoji,
        )
        .filter(WarRoomChatReaction.message_id.in_(message_ids))
        .all()
    )
    by_msg = {}
    for r in rows:
        bucket = by_msg.setdefault(r.message_id, {})
        cell = bucket.setdefault(r.emoji, {'emoji': r.emoji, 'user_ids': []})
        cell['user_ids'].append(r.user_id)
    out = {}
    for mid, by_emoji in by_msg.items():
        out[mid] = [
            {'emoji': cell['emoji'], 'count': len(cell['user_ids']),
             'user_ids': cell['user_ids']}
            for cell in by_emoji.values()
        ]
    return out


# ----- Slash commands ------------------------------------------------------

_SLASH_RE = re.compile(r'^/(?P<cmd>[a-z]+)(?:\s+(?P<rest>.*))?$', re.DOTALL)


def parse_slash(body):
    """Detect a leading slash command.

    Returns (cmd, rest) on hit, None on miss. Commands not recognised by
    the route layer are passed through as plain messages so the operator
    sees their typo instead of a silent drop.
    """
    if not isinstance(body, str):
        return None
    match = _SLASH_RE.match(body.strip())
    if not match:
        return None
    return match.group('cmd'), (match.group('rest') or '').strip()


# ----- System message helper for REST mutations ---------------------------

def emit_system_event(war_room_id, kind, body, *, author_id=None,
                      ref_type=None, ref_id=None, ref_case_id=None,
                      activity_type=None):
    """Write a system-kind chat row.

    `activity_type` is accepted for API compatibility with callers that
    used to stamp it, but is intentionally ignored on write — the
    column is read-side-only and is now never queried, so we skip it
    to keep the helper safe on databases that haven't applied the
    `e5a1b46c7d92` migration.
    """
    """Best-effort write of a system-kind chat row.

    Used by REST routes (case attach/detach, member add/remove, task
    create/close, …) so the activity panel reflects what happened in
    the war room even when the actor used the regular UI instead of a
    slash command. Failures are swallowed: the parent REST mutation
    already succeeded; we don't want a chat-stream hiccup to roll back
    a legitimate workspace change.
    """
    try:
        msg = WarRoomChatMessage()
        msg.war_room_id = war_room_id
        msg.author_id = author_id
        msg.body = body[:_BODY_MAX_LEN] if body else None
        msg.kind = kind
        msg.ref_type = ref_type
        msg.ref_id = ref_id
        msg.ref_case_id = ref_case_id
        # Don't touch msg.activity_type — see helper docstring.
        db.session.add(msg)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


# ----- Activity ingest -----------------------------------------------------

def ingest_case_activity(case_id, activity_text, ref_activity_id=None):
    """DEPRECATED — no-op kept for backwards compatibility.

    Earlier versions mirrored case-activity rows into the chat table.
    `list_messages` now pulls `UserActivity` rows live at render time
    so a case attached after-the-fact instantly surfaces its full
    history with zero duplication. This shim stays so external test
    callers don't break; new code should not call it.
    """
    return None
