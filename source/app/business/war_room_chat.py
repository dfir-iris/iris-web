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
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.models.authorization import User
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomChatMessage
from app.models.war_rooms import WarRoomChatPoll
from app.models.war_rooms import WarRoomChatPollOption
from app.models.war_rooms import WarRoomChatPollVote
from app.models.war_rooms import WarRoomChatReaction
from app.models.war_rooms import WarRoomThreadFollower


_BODY_MAX_LEN = 16_384
_PAGE_DEFAULT = 50
_PAGE_MAX = 200
_DATETIME_MIN = datetime.datetime.min

# Cache for the once-per-process check of whether the threading
# columns (`parent_message_id`, `thread_title`) and the follower table
# actually exist on the live database. We probe the information_schema
# the first time we need to know and then short-circuit so we don't
# pay for the lookup on every request.
#
# Same rationale as the `activity_type` skip: a war room installed
# against a database where the threading migration hasn't run yet
# should still be able to read the stream. Threading features just
# go dark until the migration lands.
_THREADS_SUPPORTED = None


def _threads_supported():
    """Probe whether the threading schema exists on this DB.

    Runs the actual query against the column on a fresh connection. If
    Postgres raises `UndefinedColumn`, threads are off — anything else
    means they're available. Cached only on a positive result so a
    freshly-applied migration is picked up on the next request without
    a Flask restart.

    Earlier implementations used `information_schema.columns` and the
    SQLAlchemy inspector — both gave wrong negatives in practice
    (search_path issues, stale inspector caches). Going straight to the
    column is the most direct test.
    """
    global _THREADS_SUPPORTED
    if _THREADS_SUPPORTED is True:
        return True
    try:
        from sqlalchemy import text as _text
        # Fresh connection so a poisoned session can't taint the probe.
        # We `SELECT parent_message_id LIMIT 0` so it works on an empty
        # table — and Postgres still validates the column reference at
        # plan time, so the missing-column case raises immediately.
        with db.engine.connect() as conn:
            conn.execute(
                _text(
                    'SELECT parent_message_id '
                    'FROM war_room_chat_message LIMIT 0'
                )
            )
        supported = True
    except Exception as e:
        # Distinguish "column doesn't exist" from any other DB error so
        # operators have a fighting chance of debugging the probe when
        # it goes wrong. The `pgcode` for UndefinedColumn is '42703'.
        from app.logger import logger
        pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
        if pgcode == '42703':
            logger.info('Threads disabled: parent_message_id column missing')
        else:
            logger.exception(
                'Threads support probe failed unexpectedly '
                '(pgcode=%s)', pgcode
            )
        return False
    if supported:
        _THREADS_SUPPORTED = True
    return supported


_PIN_SUPPORTED = None


def _pin_supported():
    """Probe whether the `is_pinned` column exists on this DB.

    Same rolling-upgrade rationale as `_threads_supported` — an install
    that hasn't run the pin migration still gets a working chat stream;
    pin features just go dark until the migration lands.
    """
    global _PIN_SUPPORTED
    if _PIN_SUPPORTED is True:
        return True
    try:
        from sqlalchemy import text as _text
        with db.engine.connect() as conn:
            conn.execute(
                _text('SELECT is_pinned FROM war_room_chat_message LIMIT 0')
            )
        supported = True
    except Exception as e:
        from app.logger import logger
        pgcode = getattr(getattr(e, 'orig', None), 'pgcode', None)
        if pgcode == '42703':
            logger.info('Pin support disabled: is_pinned column missing')
        else:
            logger.exception(
                'Pin support probe failed unexpectedly (pgcode=%s)', pgcode
            )
        return False
    if supported:
        _PIN_SUPPORTED = True
    return supported


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
    # `poll` hosts an inline poll (question + options + votes). The
    # poll body lives in `WarRoomChatPoll`; the chat row acts as the
    # anchor in the stream so the row's `created_at` and thread
    # placement stay consistent with every other kind.
    'poll',
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
        # UA-derived rows never participate in threads; the fields are
        # set explicitly so the row's shape matches the chat-row tuple
        # and downstream serializers don't have to special-case it.
        parent_message_id=None,
        thread_title=None,
        created_at=ua_row.activity_date,
        edited_at=None,
        deleted_at=None,
        author_login=ua_row.user_login,
        author_name=ua_row.user_name,
    )


def _fetch_live_case_activities(war_room_id, before_dt, limit,
                                case_ids=None, search=None):
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
    needle = search.strip() if isinstance(search, str) else None
    if needle:
        q = q.filter(UserActivity.activity_desc.ilike(f'%{needle}%'))

    rows = (
        q.order_by(desc(UserActivity.activity_date))
        .limit(limit)
        .all()
    )
    return [_virtual_activity_row(r, war_room_id) for r in rows]


def list_messages(war_room_id, before=None, limit=None, kinds=None,
                  case_ids=None, search=None):
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
    `search` case-insensitively matches the chat body / activity
    description with a `%needle%` LIKE — the SPA uses this to drive
    the top-of-stream quick-filter without pulling the full firehose
    to the client.
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
    # Threading columns are conditionally selected: on databases that
    # haven't applied the threads migration yet, requesting
    # `parent_message_id` / `thread_title` would raise UndefinedColumn
    # before any row could be returned. We probe the schema once and
    # cache the result.
    threads_on = _threads_supported()
    pin_on = _pin_supported()
    columns = [
        WarRoomChatMessage.message_id,
        WarRoomChatMessage.war_room_id,
        WarRoomChatMessage.author_id,
        WarRoomChatMessage.body,
        WarRoomChatMessage.kind,
        WarRoomChatMessage.ref_type,
        WarRoomChatMessage.ref_id,
        WarRoomChatMessage.ref_case_id,
    ]
    if threads_on:
        columns += [
            WarRoomChatMessage.parent_message_id,
            WarRoomChatMessage.thread_title,
        ]
    if pin_on:
        columns.append(WarRoomChatMessage.is_pinned)
    columns += [
        WarRoomChatMessage.created_at,
        WarRoomChatMessage.edited_at,
        WarRoomChatMessage.deleted_at,
        User.user.label('author_login'),
        User.name.label('author_name'),
    ]
    q = (
        db.session.query(*columns)
        .outerjoin(User, User.id == WarRoomChatMessage.author_id)
        .filter(WarRoomChatMessage.war_room_id == war_room_id)
        .filter(WarRoomChatMessage.kind != 'case_activity')
    )
    if threads_on:
        # Replies stay inside their thread panel — the top-level stream
        # only shows roots so a chatty thread doesn't drown out other
        # activity. Skipped when threading isn't supported on this DB
        # yet (all messages are roots in that case).
        q = q.filter(WarRoomChatMessage.parent_message_id.is_(None))
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
    # Free-text filter: ILIKE against the message body. Soft-deleted
    # rows drop out here too, because their body is nulled at delete
    # time and NULL doesn't match `LIKE`. Overfetch is fine — the merge
    # step below trims to `limit`.
    needle = search.strip() if isinstance(search, str) else None
    if needle:
        q = q.filter(WarRoomChatMessage.body.ilike(f'%{needle}%'))

    chat_rows = q.order_by(desc(WarRoomChatMessage.message_id)).limit(limit).all()

    if not want_case_activity:
        return chat_rows

    # Overfetch live activities to fill the page after merge — we'll
    # trim down to `limit` after sorting.
    activity_rows = _fetch_live_case_activities(
        war_room_id, before_dt=before_dt, limit=limit, case_ids=case_ids,
        search=needle,
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

    # Fire notifications on plain user messages only — system-authored
    # kinds (task_assigned, sitrep_published, case_attached, …) get
    # their notification via the origin action's own hook, not the
    # chat mirror. `_fire_message_notifications` is a no-op if the
    # notifications subsystem is not installed (safe on partial
    # rollouts).
    if kind == 'message':
        _fire_message_notifications(msg)
    msg = call_modules_hook('on_postload_war_room_message_create', msg)
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
    msg = call_modules_hook('on_postload_war_room_message_update', msg)
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
    call_modules_hook('on_postload_war_room_message_delete',
                      {'war_room_id': war_room_id, 'message_id': message_id})


def set_message_pin(war_room_id, message_id, is_pinned, actor_id, is_admin=False):
    """Toggle the sticky-pin flag on a chat message.

    Anyone with war-room write access can pin/unpin — pinning isn't a
    destructive act (delete/edit are author-only) so we don't gate to
    the author. If we later grow a per-war-room role model that
    distinguishes 'member' from 'moderator' this is the place to
    tighten the check. `actor_id`/`is_admin` are threaded through for
    future permission work and for the `track_activity` bookkeeping.
    """
    msg = get_message(war_room_id, message_id)
    if msg.deleted_at is not None:
        raise BusinessProcessingError('Cannot pin a deleted message')
    if msg.kind not in ('message', 'pin', 'decision', 'note'):
        # System rows (task_assigned, case_attached, sitrep_published,
        # poll, …) aren't pinnable — they're already elevated via
        # `kind` and cluttering the pin list with them would defeat
        # the point.
        raise BusinessProcessingError(
            f'Messages of kind {msg.kind!r} cannot be pinned'
        )
    msg.is_pinned = bool(is_pinned)
    db.session.commit()
    call_modules_hook('on_postload_war_room_message_pin',
                      {'war_room_id': war_room_id,
                       'message_id': message_id,
                       'is_pinned': msg.is_pinned,
                       'actor_id': actor_id})
    return msg


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
        call_modules_hook('on_postload_war_room_reaction_toggle',
                          {'war_room_id': war_room_id,
                           'message_id': msg.message_id,
                           'user_id': user_id, 'emoji': emoji,
                           'added': False})
        return False

    row = WarRoomChatReaction()
    row.message_id = msg.message_id
    row.user_id = user_id
    row.emoji = emoji
    db.session.add(row)
    db.session.commit()
    call_modules_hook('on_postload_war_room_reaction_toggle',
                      {'war_room_id': war_room_id,
                       'message_id': msg.message_id,
                       'user_id': user_id, 'emoji': emoji,
                       'added': True})
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


# ----- Threads -------------------------------------------------------------

_THREAD_TITLE_MAX_LEN = 160


def _validate_thread_title(title):
    if title is None or title == '':
        return None
    if not isinstance(title, str):
        raise BusinessProcessingError('Thread title must be a string')
    stripped = title.strip()
    if not stripped:
        return None
    if len(stripped) > _THREAD_TITLE_MAX_LEN:
        raise BusinessProcessingError(
            f'Thread title must be at most {_THREAD_TITLE_MAX_LEN} characters'
        )
    return stripped


def _get_root_message(war_room_id, message_id):
    """Resolve a message id to its thread root.

    A reply (`parent_message_id IS NOT NULL`) folds upward to its
    parent so callers can pass either the root or any reply id and get
    consistent behaviour for follow/title/list.
    """
    msg = get_message(war_room_id, message_id)
    if _threads_supported() and msg.parent_message_id is not None:
        return get_message(war_room_id, msg.parent_message_id)
    return msg


def _require_threads():
    """Surface a clean error when a thread route is called on a DB
    that hasn't applied the threading migration yet. Callers turn
    this into a 400 instead of a 500 with a stack trace."""
    if not _threads_supported():
        raise BusinessProcessingError(
            'Threads are not enabled on this server yet — '
            'apply the latest migrations.'
        )


def create_reply(war_room_id, parent_message_id, author_id, body, kind='message'):
    """Post a reply hanging off a thread root.

    Threads are two-level: replying to a reply folds the new row up to
    the same root, mirroring how operators expect "reply to this
    thread" to behave. `kind` accepts the trace-friendly subset
    (`message`, `decision`, `pin`, `note`) so slash commands like
    `/decision` and `/pin` used inside a thread persist as structured
    rows — the operator gets the same visual chrome (icon, colour) as
    on the main stream, and the "who decided what and when" index can
    surface these entries whether they were posted top-level or in a
    thread.
    """
    _require_threads()
    root = _get_root_message(war_room_id, parent_message_id)
    if root.deleted_at is not None:
        raise BusinessProcessingError('Cannot reply on a deleted message')
    # Only the plain-message + trace kinds are allowed as replies. Other
    # kinds (task_assigned, case_attached, sitrep_published, …) represent
    # room-wide state changes that belong in the main stream, not
    # buried inside a thread.
    if kind not in ('message', 'decision', 'pin', 'note'):
        raise BusinessProcessingError(
            f'Kind "{kind}" is not allowed as a thread reply'
        )
    body = _validate_body(body, kind)

    msg = WarRoomChatMessage()
    msg.war_room_id = war_room_id
    msg.author_id = author_id
    msg.body = body
    msg.kind = kind
    msg.parent_message_id = root.message_id
    db.session.add(msg)
    db.session.commit()

    _fire_reply_notifications(msg, root.message_id)
    msg = call_modules_hook('on_postload_war_room_reply_create', msg)
    return msg


def list_replies(war_room_id, root_message_id, limit=None):
    """Return all replies for a thread root, oldest first.

    Oldest-first matches how thread side-pane UIs typically render
    (read top-to-bottom). Pagination is by `limit` only since threads
    are expected to be small relative to the main stream.
    """
    if not _threads_supported():
        return []
    if limit is None:
        limit = _PAGE_DEFAULT
    limit = min(int(limit), _PAGE_MAX)
    root = _get_root_message(war_room_id, root_message_id)
    pin_on = _pin_supported()
    columns = [
        WarRoomChatMessage.message_id,
        WarRoomChatMessage.war_room_id,
        WarRoomChatMessage.author_id,
        WarRoomChatMessage.body,
        WarRoomChatMessage.kind,
        WarRoomChatMessage.ref_type,
        WarRoomChatMessage.ref_id,
        WarRoomChatMessage.ref_case_id,
        WarRoomChatMessage.parent_message_id,
        WarRoomChatMessage.thread_title,
        WarRoomChatMessage.created_at,
        WarRoomChatMessage.edited_at,
        WarRoomChatMessage.deleted_at,
        User.user.label('author_login'),
        User.name.label('author_name'),
    ]
    if pin_on:
        columns.append(WarRoomChatMessage.is_pinned)
    q = (
        db.session.query(*columns)
        .outerjoin(User, User.id == WarRoomChatMessage.author_id)
        .filter(WarRoomChatMessage.war_room_id == war_room_id)
        .filter(WarRoomChatMessage.parent_message_id == root.message_id)
        .order_by(WarRoomChatMessage.message_id.asc())
        .limit(limit)
    )
    return q.all()


_TRACE_KINDS = ('decision', 'pin', 'note')


def list_trace_log(war_room_id, limit=None):
    """Return every trace-worthy message (decisions, pins, notes) in the
    war room — including replies inside threads.

    Unlike `list_messages`, this doesn't skip replies (the main-stream
    listing hides them so a chatty thread doesn't drown out other
    activity, but the trace log needs the full picture: a decision
    posted inside a thread is still a decision). Ordered newest-first
    so the sidebar renders "most recent first" without a client-side
    reverse.
    """
    if limit is None:
        limit = _PAGE_MAX
    limit = min(int(limit), _PAGE_MAX)

    threads_on = _threads_supported()
    pin_on = _pin_supported()
    columns = [
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
    ]
    # `parent_message_id` doesn't exist on installs that haven't run
    # the threads migration yet — probe the schema so this endpoint
    # keeps working through a rolling upgrade. When it's absent, every
    # trace-worthy message is by definition a top-level one anyway.
    if threads_on:
        columns.append(WarRoomChatMessage.parent_message_id)
    if pin_on:
        columns.append(WarRoomChatMessage.is_pinned)

    from sqlalchemy import or_
    filters = [
        WarRoomChatMessage.war_room_id == war_room_id,
        WarRoomChatMessage.deleted_at.is_(None),
    ]
    if pin_on:
        # Trace-worthy = system rows we already flagged as "keep me"
        # (decisions/pins/notes) OR any regular message an analyst
        # explicitly pinned. Union rather than two queries to keep
        # the ORDER BY LIMIT correct across both sources.
        filters.append(or_(
            WarRoomChatMessage.kind.in_(_TRACE_KINDS),
            WarRoomChatMessage.is_pinned.is_(True),
        ))
    else:
        # Pre-migration DBs: only the system-row kinds count as trace-worthy.
        filters.append(WarRoomChatMessage.kind.in_(_TRACE_KINDS))

    q = (
        db.session.query(*columns)
        .outerjoin(User, User.id == WarRoomChatMessage.author_id)
        .filter(*filters)
        .order_by(desc(WarRoomChatMessage.created_at), desc(WarRoomChatMessage.message_id))
        .limit(limit)
    )
    return q.all()


def set_thread_title(war_room_id, message_id, title):
    """Promote a message to a named topic, or rename / clear the name.

    Always operates on the root: if the caller passed a reply id, we
    fold up to the root so the title lives on the right row.
    """
    _require_threads()
    root = _get_root_message(war_room_id, message_id)
    root.thread_title = _validate_thread_title(title)
    db.session.commit()
    return root


def list_thread_roots(war_room_id, limit=None):
    """Return thread roots with reply counts and follower flags.

    A "thread" here is any root that has either at least one reply OR
    a named `thread_title`. A naked message with neither isn't listed
    — operators don't need to see every message in the threads
    sidebar, just the ones with content branching off them.

    Results are sorted by latest activity (max of root.created_at and
    the newest reply's created_at) descending so an active thread
    bubbles to the top.
    """
    if not _threads_supported():
        return []
    if limit is None:
        limit = _PAGE_DEFAULT
    limit = min(int(limit), _PAGE_MAX)

    from sqlalchemy import func
    # Aggregate replies per root.
    reply_stats = (
        db.session.query(
            WarRoomChatMessage.parent_message_id.label('root_id'),
            func.count(WarRoomChatMessage.message_id).label('reply_count'),
            func.max(WarRoomChatMessage.created_at).label('last_reply_at'),
        )
        .filter(WarRoomChatMessage.war_room_id == war_room_id)
        .filter(WarRoomChatMessage.parent_message_id.isnot(None))
        .group_by(WarRoomChatMessage.parent_message_id)
        .subquery()
    )

    q = (
        db.session.query(
            WarRoomChatMessage.message_id,
            WarRoomChatMessage.war_room_id,
            WarRoomChatMessage.author_id,
            WarRoomChatMessage.body,
            WarRoomChatMessage.kind,
            WarRoomChatMessage.thread_title,
            WarRoomChatMessage.created_at,
            WarRoomChatMessage.deleted_at,
            User.user.label('author_login'),
            User.name.label('author_name'),
            reply_stats.c.reply_count,
            reply_stats.c.last_reply_at,
        )
        .outerjoin(User, User.id == WarRoomChatMessage.author_id)
        .outerjoin(reply_stats,
                   reply_stats.c.root_id == WarRoomChatMessage.message_id)
        .filter(WarRoomChatMessage.war_room_id == war_room_id)
        .filter(WarRoomChatMessage.parent_message_id.is_(None))
        # Either has replies OR a name — naked unnamed roots aren't
        # treated as threads.
        .filter(and_(
            (reply_stats.c.reply_count.isnot(None)) |
            (WarRoomChatMessage.thread_title.isnot(None))
        ))
        .order_by(
            func.coalesce(reply_stats.c.last_reply_at,
                          WarRoomChatMessage.created_at).desc()
        )
        .limit(limit)
    )
    return q.all()


def follow_thread(war_room_id, message_id, user_id):
    """Add a follow row for (user, root). Idempotent.

    Returns True on insert, False if the row already existed.
    """
    _require_threads()
    root = _get_root_message(war_room_id, message_id)
    existing = (
        WarRoomThreadFollower.query
        .filter_by(message_id=root.message_id, user_id=user_id)
        .first()
    )
    if existing is not None:
        return False
    row = WarRoomThreadFollower()
    row.message_id = root.message_id
    row.user_id = user_id
    db.session.add(row)
    db.session.commit()
    return True


def unfollow_thread(war_room_id, message_id, user_id):
    """Remove the follow row if present. Idempotent — returns True on
    delete, False if there was nothing to remove."""
    if not _threads_supported():
        return False
    root = _get_root_message(war_room_id, message_id)
    row = (
        WarRoomThreadFollower.query
        .filter_by(message_id=root.message_id, user_id=user_id)
        .first()
    )
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def list_followed_thread_ids(war_room_id, user_id):
    """IDs of roots that `user_id` follows in this war room.

    Used by the UI to flag followed threads in the sidebar list. Scoped
    to the war room via a join so we don't leak follows across rooms.
    """
    if not _threads_supported():
        return []
    rows = (
        db.session.query(WarRoomThreadFollower.message_id)
        .join(WarRoomChatMessage,
              WarRoomChatMessage.message_id == WarRoomThreadFollower.message_id)
        .filter(WarRoomChatMessage.war_room_id == war_room_id)
        .filter(WarRoomThreadFollower.user_id == user_id)
        .all()
    )
    return [r.message_id for r in rows]


# ----- Notification fan-out ------------------------------------------------
#
# Chat messages and thread replies both need to notify a set of
# recipients. Kept as helpers so `create_message` / `create_reply` stay
# focussed on persistence and the notification path can be exercised
# and updated in one place. Failure here MUST NOT bubble — a broken
# notification pipeline shouldn't prevent a chat message from being
# posted.

def _fire_message_notifications(msg):
    """Notify members mentioned in a new plain chat message.

    Room members (WarRoomMember roster) are NOT blanket-notified — a
    busy war room would drown its participants. Only mentions raise
    the bell. The war-room event type is reserved for followed-thread
    replies (see `_fire_reply_notifications`).
    """
    try:
        from app.iris_engine.notifications.mentions import extract_mentioned_user_ids
        from app.iris_engine.notifications.service import notify_many
        from app.models.war_rooms import WarRoomMember

        mentioned = extract_mentioned_user_ids(msg.body)
        if not mentioned:
            return

        # Only notify members of this war room — a mention chip on a
        # user without room access would be a leak (bell would surface
        # the room title/body).
        member_ids = {
            row.user_id for row in
            WarRoomMember.query
            .filter(WarRoomMember.war_room_id == msg.war_room_id)
            .filter(WarRoomMember.user_id.in_(mentioned))
            .all()
        }
        if not member_ids:
            return

        notify_many(
            user_ids=list(member_ids),
            event_type='mention',
            title='You were mentioned in a war room',
            body=(msg.body or '')[:255],
            link=f'/war-rooms/{msg.war_room_id}/chat',
            source_type='war_room_message',
            source_id=msg.message_id,
            exclude_user_ids=[msg.author_id] if msg.author_id else [],
        )
    except Exception:
        # Broad catch — see note above. A missing notifications module
        # or a DB blip must not fail the chat write.
        import logging
        logging.getLogger(__name__).exception(
            'war-room mention notification failed')


def _fire_reply_notifications(msg, root_message_id):
    """Notify thread followers + mentions on a new reply."""
    try:
        from app.iris_engine.notifications.mentions import extract_mentioned_user_ids
        from app.iris_engine.notifications.service import notify_many

        # 1. Thread followers (excluding the author)
        follower_ids = {
            row.user_id for row in
            WarRoomThreadFollower.query
            .filter(WarRoomThreadFollower.message_id == root_message_id)
            .all()
        }

        if follower_ids:
            notify_many(
                user_ids=list(follower_ids),
                event_type='war_room_thread_reply',
                title='New reply in a thread you follow',
                body=(msg.body or '')[:255],
                link=f'/war-rooms/{msg.war_room_id}/chat?thread={root_message_id}',
                source_type='war_room_thread_reply',
                source_id=msg.message_id,
                exclude_user_ids=[msg.author_id] if msg.author_id else [],
            )

        # 2. Mentions inside the reply (independent from follow —
        # mentioning a non-follower still pings them).
        mentioned = extract_mentioned_user_ids(msg.body)
        if mentioned:
            from app.models.war_rooms import WarRoomMember
            member_ids = {
                row.user_id for row in
                WarRoomMember.query
                .filter(WarRoomMember.war_room_id == msg.war_room_id)
                .filter(WarRoomMember.user_id.in_(mentioned))
                .all()
            }
            # Avoid double-notifying someone who both follows AND was
            # mentioned — the mention notification is more informative
            # so we keep it and drop the follow one for that user.
            member_ids = member_ids - follower_ids
            if member_ids:
                notify_many(
                    user_ids=list(member_ids),
                    event_type='mention',
                    title='You were mentioned in a war-room thread',
                    body=(msg.body or '')[:255],
                    link=f'/war-rooms/{msg.war_room_id}/chat?thread={root_message_id}',
                    source_type='war_room_thread_reply',
                    source_id=msg.message_id,
                    exclude_user_ids=[msg.author_id] if msg.author_id else [],
                )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            'war-room reply notification failed')


# ----- Polls ---------------------------------------------------------------

_POLL_QUESTION_MAX = 512
_POLL_OPTION_MAX_LEN = 256
_POLL_OPTIONS_MIN = 2
_POLL_OPTIONS_MAX = 20


def _validate_poll_options(options):
    """Normalise + validate the option-label list from the client.

    Raises `BusinessProcessingError` on shape violations; returns the
    trimmed list otherwise. Ordering is preserved — the caller
    persists options with `sort_order` matching their index in the
    returned list."""
    if not isinstance(options, list):
        raise BusinessProcessingError('options must be a list of strings')
    if not (_POLL_OPTIONS_MIN <= len(options) <= _POLL_OPTIONS_MAX):
        raise BusinessProcessingError(
            f'A poll must have between {_POLL_OPTIONS_MIN} '
            f'and {_POLL_OPTIONS_MAX} options'
        )
    cleaned = []
    for opt in options:
        if not isinstance(opt, str):
            raise BusinessProcessingError('Each option must be a string')
        s = opt.strip()
        if not s:
            raise BusinessProcessingError('Option labels cannot be empty')
        if len(s) > _POLL_OPTION_MAX_LEN:
            raise BusinessProcessingError(
                f'Option labels must be at most {_POLL_OPTION_MAX_LEN} characters'
            )
        cleaned.append(s)
    return cleaned


def _parse_closes_at(raw):
    """Parse a client-supplied `closes_at` deadline string.

    None / empty string → no deadline. Otherwise expects ISO-8601.
    Naive datetimes are treated as UTC (matches the rest of the
    codebase's `datetime.utcnow` usage)."""
    if raw is None or raw == '':
        return None
    if isinstance(raw, datetime.datetime):
        return raw
    if not isinstance(raw, str):
        raise BusinessProcessingError('closes_at must be an ISO date string')
    try:
        return datetime.datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        raise BusinessProcessingError('closes_at must be an ISO date string')


def poll_is_closed(poll: WarRoomChatPoll) -> bool:
    """A poll is closed if it was manually closed OR its deadline has
    passed. Called from every vote path so the truth is centralised."""
    if poll.closed_at is not None:
        return True
    if poll.closes_at is not None and poll.closes_at <= datetime.datetime.utcnow():
        return True
    return False


def _get_poll(war_room_id: int, poll_id: int) -> WarRoomChatPoll:
    poll = (
        WarRoomChatPoll.query
        .filter_by(poll_id=poll_id, war_room_id=war_room_id)
        .first()
    )
    if poll is None:
        raise ObjectNotFoundError()
    return poll


def create_poll(war_room_id, author_id, question, options,
                is_multi_select=False, is_anonymous=False, closes_at=None):
    """Create a poll + its companion chat message in one commit.

    The chat message is `kind='poll'` with `ref_type='chat_poll'` and
    `ref_id=<poll_id>`. The route layer emits `message:new` after this
    returns so the stream broadcast fires through the existing path —
    no separate `poll:created` event is strictly required, but we
    also emit `poll:created` for clients that want to react to poll
    creation specifically (e.g. jump to it, seed a local cache)."""
    if not isinstance(question, str) or not question.strip():
        raise BusinessProcessingError('Poll question is required')
    question = question.strip()
    if len(question) > _POLL_QUESTION_MAX:
        raise BusinessProcessingError(
            f'Poll question must be at most {_POLL_QUESTION_MAX} characters'
        )
    labels = _validate_poll_options(options)
    parsed_closes_at = _parse_closes_at(closes_at)
    if parsed_closes_at is not None and parsed_closes_at <= datetime.datetime.utcnow():
        raise BusinessProcessingError('closes_at must be in the future')

    poll = WarRoomChatPoll()
    poll.war_room_id = war_room_id
    poll.author_id = author_id
    poll.question = question
    poll.is_multi_select = bool(is_multi_select)
    poll.is_anonymous = bool(is_anonymous)
    poll.closes_at = parsed_closes_at
    db.session.add(poll)
    db.session.flush()  # get poll.poll_id before inserting options + message

    for idx, label in enumerate(labels):
        opt = WarRoomChatPollOption()
        opt.poll_id = poll.poll_id
        opt.label = label
        opt.sort_order = idx
        db.session.add(opt)

    # Companion chat message. `body` intentionally left empty — the
    # frontend renders the poll card from the poll payload, not from
    # the message body. Keeping `body` NULL means the stream fallback
    # renderer produces nothing awkward if the poll card doesn't load.
    msg = WarRoomChatMessage()
    msg.war_room_id = war_room_id
    msg.author_id = author_id
    msg.kind = 'poll'
    msg.body = None
    msg.ref_type = 'chat_poll'
    db.session.add(msg)
    db.session.flush()
    msg.ref_id = poll.poll_id
    poll.chat_message_id = msg.message_id
    db.session.commit()

    call_modules_hook('on_postload_war_room_poll_create',
                      {'war_room_id': war_room_id,
                       'poll_id': poll.poll_id,
                       'message_id': msg.message_id})
    return msg, poll


def vote_on_poll(war_room_id, poll_id, user_id, option_ids):
    """Cast/replace a user's votes on a poll.

    For single-select polls, `option_ids` must be exactly one — the
    existing vote (if any) is atomically replaced by the new one.
    For multi-select polls, `option_ids` is the FULL desired set —
    votes not in the list are removed, votes in the list are added
    (idempotent). Passing `[]` clears the user's votes entirely.

    Rejects if the poll is closed or if any id doesn't belong to it.
    """
    if not isinstance(option_ids, list):
        raise BusinessProcessingError('option_ids must be a list of integers')

    poll = _get_poll(war_room_id, poll_id)
    if poll_is_closed(poll):
        raise BusinessProcessingError('Poll is closed for voting')

    # Coerce + dedupe. Ints only; non-numeric silently dropped so a
    # client bug doesn't 400 the whole request.
    wanted: set[int] = set()
    for raw in option_ids:
        try:
            wanted.add(int(raw))
        except (TypeError, ValueError):
            continue

    if not poll.is_multi_select and len(wanted) > 1:
        raise BusinessProcessingError(
            'This is a single-select poll; only one option may be chosen'
        )

    # Validate every requested option belongs to this poll — cheap
    # single-query check, keeps us from ballot-stuffing across polls.
    valid_option_ids = {
        row.option_id for row in
        WarRoomChatPollOption.query
        .filter(WarRoomChatPollOption.poll_id == poll.poll_id,
                WarRoomChatPollOption.option_id.in_(wanted))
        .with_entities(WarRoomChatPollOption.option_id)
        .all()
    } if wanted else set()
    if wanted != valid_option_ids:
        raise BusinessProcessingError('One or more option ids are invalid for this poll')

    # Snapshot the user's current votes across ANY option in this
    # poll. Anything not in `wanted` gets removed; anything in
    # `wanted` and not already present gets added.
    existing_option_ids = {
        row.option_id for row in
        db.session.query(WarRoomChatPollVote.option_id)
        .join(WarRoomChatPollOption,
              WarRoomChatPollOption.option_id == WarRoomChatPollVote.option_id)
        .filter(WarRoomChatPollOption.poll_id == poll.poll_id,
                WarRoomChatPollVote.user_id == user_id)
        .all()
    }

    to_remove = existing_option_ids - wanted
    to_add = wanted - existing_option_ids

    if to_remove:
        WarRoomChatPollVote.query.filter(
            WarRoomChatPollVote.option_id.in_(to_remove),
            WarRoomChatPollVote.user_id == user_id,
        ).delete(synchronize_session=False)

    for opt_id in to_add:
        vote = WarRoomChatPollVote()
        vote.option_id = opt_id
        vote.user_id = user_id
        db.session.add(vote)

    db.session.commit()
    call_modules_hook('on_postload_war_room_poll_vote',
                      {'war_room_id': war_room_id,
                       'poll_id': poll.poll_id,
                       'user_id': user_id,
                       'added': list(to_add), 'removed': list(to_remove)})
    return poll


def close_poll(war_room_id, poll_id, user_id, is_admin=False):
    """Manually close a poll. Author or admin only. Idempotent."""
    poll = _get_poll(war_room_id, poll_id)
    if poll.author_id != user_id and not is_admin:
        raise BusinessProcessingError(
            'Only the poll author or an admin can close a poll'
        )
    if poll.closed_at is None:
        poll.closed_at = datetime.datetime.utcnow()
        db.session.commit()
        call_modules_hook('on_postload_war_room_poll_close',
                          {'war_room_id': war_room_id,
                           'poll_id': poll.poll_id,
                           'closed_by': user_id})
    return poll


def get_poll_state(war_room_id, poll_id, viewer_id):
    """Return the poll + option tallies for a viewer.

    Voter identity is stripped when `poll.is_anonymous=true`; only
    the aggregate `vote_count` is returned per option. Non-anonymous
    polls return per-option `voters: [{user_id, name}]` so the UI
    can render "voted by …" chips.

    `my_votes` is always the viewer's own option ids — even on
    anonymous polls the viewer sees their own selections."""
    poll = _get_poll(war_room_id, poll_id)

    # One join per option to fetch its votes + voter identity in a
    # single query. Cheap because polls have at most 20 options each.
    from sqlalchemy import func
    counts = dict(
        db.session.query(
            WarRoomChatPollOption.option_id,
            func.count(WarRoomChatPollVote.option_id),
        )
        .outerjoin(WarRoomChatPollVote,
                   WarRoomChatPollVote.option_id == WarRoomChatPollOption.option_id)
        .filter(WarRoomChatPollOption.poll_id == poll.poll_id)
        .group_by(WarRoomChatPollOption.option_id)
        .all()
    )

    # Viewer's own selections — anonymous polls still show these
    # (a user always knows what they clicked).
    my_votes = [
        row.option_id for row in
        db.session.query(WarRoomChatPollVote.option_id)
        .join(WarRoomChatPollOption,
              WarRoomChatPollOption.option_id == WarRoomChatPollVote.option_id)
        .filter(WarRoomChatPollOption.poll_id == poll.poll_id,
                WarRoomChatPollVote.user_id == viewer_id)
        .all()
    ]

    voters_by_option: dict[int, list] = {}
    if not poll.is_anonymous:
        rows = (
            db.session.query(
                WarRoomChatPollVote.option_id,
                User.id, User.user, User.name,
            )
            .join(WarRoomChatPollOption,
                  WarRoomChatPollOption.option_id == WarRoomChatPollVote.option_id)
            .join(User, User.id == WarRoomChatPollVote.user_id)
            .filter(WarRoomChatPollOption.poll_id == poll.poll_id)
            .all()
        )
        for opt_id, uid, login, name in rows:
            voters_by_option.setdefault(opt_id, []).append({
                'user_id': uid,
                'user_login': login,
                'user_name': name,
            })

    options_out = []
    for opt in poll.options:
        entry = {
            'option_id': opt.option_id,
            'label': opt.label,
            'sort_order': opt.sort_order,
            'vote_count': int(counts.get(opt.option_id, 0)),
        }
        if not poll.is_anonymous:
            entry['voters'] = voters_by_option.get(opt.option_id, [])
        options_out.append(entry)

    return {
        'poll_id': poll.poll_id,
        'war_room_id': poll.war_room_id,
        'author_id': poll.author_id,
        'question': poll.question,
        'is_multi_select': poll.is_multi_select,
        'is_anonymous': poll.is_anonymous,
        'closes_at': poll.closes_at.isoformat() if poll.closes_at else None,
        'closed_at': poll.closed_at.isoformat() if poll.closed_at else None,
        'is_closed': poll_is_closed(poll),
        'chat_message_id': poll.chat_message_id,
        'created_at': poll.created_at.isoformat() if poll.created_at else None,
        'my_votes': my_votes,
        'options': options_out,
    }


def get_poll_by_message_id(war_room_id, message_id):
    """Look up the poll hosted by a `kind='poll'` chat message. Used
    by the list-messages serializer to inline the poll payload so the
    SPA doesn't need a second RPC per poll on stream load."""
    return (
        WarRoomChatPoll.query
        .filter_by(war_room_id=war_room_id, chat_message_id=message_id)
        .first()
    )


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
