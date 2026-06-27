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


_VALID_KINDS = {
    'message', 'system',
    'task_assigned', 'task_completed',
    'case_attached', 'case_detached',
    'case_activity',
    'sitrep_published', 'note', 'pin',
}


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


def list_messages(war_room_id, before=None, limit=None, kinds=None,
                  case_ids=None):
    """Cursor-paginate the chat stream.

    `before` is a message_id — return messages with smaller ids
    (older). `kinds` and `case_ids` filter further.
    """
    if limit is None:
        limit = _PAGE_DEFAULT
    limit = min(int(limit), _PAGE_MAX)

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
    )

    if before is not None:
        q = q.filter(WarRoomChatMessage.message_id < int(before))
    if kinds:
        q = q.filter(WarRoomChatMessage.kind.in_(list(kinds)))
    if case_ids:
        q = q.filter(WarRoomChatMessage.ref_case_id.in_(list(case_ids)))

    rows = q.order_by(desc(WarRoomChatMessage.message_id)).limit(limit).all()
    # Caller gets newest-first; the SPA reverses for display.
    return rows


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
                      ref_type=None, ref_id=None, ref_case_id=None):
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
        db.session.add(msg)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


# ----- Activity ingest -----------------------------------------------------

def ingest_case_activity(case_id, activity_text, ref_activity_id=None):
    """Mirror a case-activity row into every war room the case is in.

    Called from the activity tracker so the war-room chat always
    reflects what's happening on its attached cases without the SPA
    having to subscribe per-case.
    """
    from app.models.war_rooms import WarRoomCase

    rooms = (
        WarRoomCase.query
        .with_entities(WarRoomCase.war_room_id)
        .filter(WarRoomCase.case_id == case_id)
        .all()
    )
    if not rooms:
        return

    for r in rooms:
        msg = WarRoomChatMessage()
        msg.war_room_id = r.war_room_id
        msg.author_id = None
        msg.body = activity_text[:_BODY_MAX_LEN] if activity_text else None
        msg.kind = 'case_activity'
        msg.ref_type = 'user_activity'
        msg.ref_id = ref_activity_id
        msg.ref_case_id = case_id
        db.session.add(msg)
    db.session.commit()
