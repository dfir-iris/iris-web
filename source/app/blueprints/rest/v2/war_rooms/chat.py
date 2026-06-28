#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Chat-stream REST routes for war rooms.

Mounted under `/api/v2/war-rooms/<id>/chat`. Cursor-paginated via
`?before=<msg_id>` so the SPA can scroll back without offsets that
shift when a new message lands.

Slash commands are resolved here: the body is parsed, the matching
sub-system is invoked (task / case attach / sitrep), and a system
message is recorded in the same transaction so the chat is also the
audit log.
"""

from flask import Blueprint, request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_permission
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.war_room_chat import create_message
from app.business.war_room_chat import create_reply
from app.business.war_room_chat import delete_message
from app.business.war_room_chat import follow_thread
from app.business.war_room_chat import list_followed_thread_ids
from app.business.war_room_chat import list_messages
from app.business.war_room_chat import list_reactions
from app.business.war_room_chat import list_replies
from app.business.war_room_chat import list_thread_roots
from app.business.war_room_chat import parse_slash
from app.business.war_room_chat import set_thread_title
from app.business.war_room_chat import toggle_reaction
from app.business.war_room_chat import unfollow_thread
from app.business.war_room_chat import update_message
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_chat_blueprint = Blueprint(
    'war_rooms_chat_rest_v2', __name__, url_prefix='/<int:war_room_id>/chat'
)


def _serialize(row, reactions=None):
    return {
        'message_id': row.message_id,
        'war_room_id': row.war_room_id,
        'author_id': row.author_id,
        'author_login': row.author_login,
        'author_name': row.author_name,
        'body': row.body,
        'kind': row.kind,
        'ref_type': row.ref_type,
        'ref_id': row.ref_id,
        'ref_case_id': row.ref_case_id,
        # `activity_type` is populated on virtual UserActivity rows
        # only — chat rows never carry it directly (the column is
        # ignored at query time for cross-version compat). Defaults
        # to None for plain messages / system rows.
        'activity_type': getattr(row, 'activity_type', None),
        # Threading metadata. `parent_message_id` is None on roots and
        # on virtual UA rows (which never participate in threads).
        # `thread_title` is set only when an operator named the topic.
        'parent_message_id': getattr(row, 'parent_message_id', None),
        'thread_title': getattr(row, 'thread_title', None),
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'edited_at': row.edited_at.isoformat() if row.edited_at else None,
        'deleted_at': row.deleted_at.isoformat() if row.deleted_at else None,
        'reactions': reactions or [],
    }


def _emit_socket(war_room_id, event_name, payload):
    """Best-effort fan-out to the war-room socket channel.

    Failures are swallowed: the REST write already succeeded; if no
    socketio worker is running (CLI / test mode) we don't want to
    surface a 500.
    """
    try:
        from app import socket_io
    except Exception:
        return
    try:
        socket_io.emit(event_name, payload, room=f'war_room_{war_room_id}')
    except Exception:
        pass


@war_rooms_chat_blueprint.get('')
@ac_api_requires()
def list_chat(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err

    before = request.args.get('before', type=int)
    limit = request.args.get('limit', type=int)
    kinds_raw = request.args.get('kinds', type=str)
    case_ids_raw = request.args.get('case_ids', type=str)

    kinds = [k.strip() for k in kinds_raw.split(',') if k.strip()] if kinds_raw else None
    case_ids = None
    if case_ids_raw:
        try:
            case_ids = [int(x) for x in case_ids_raw.split(',') if x.strip()]
        except ValueError:
            return response_api_error('Invalid case_ids')

    rows = list_messages(war_room_id, before=before, limit=limit,
                         kinds=kinds, case_ids=case_ids)
    reactions = list_reactions([r.message_id for r in rows])
    return response_api_success(
        data=[_serialize(r, reactions.get(r.message_id)) for r in rows]
    )


_VALID_STATES = {'open', 'active', 'standby', 'closed'}
_PRIORITY_LEVELS = {'low', 'medium', 'high', 'critical'}
_PRIORITY_ALIASES = {'med': 'medium', 'mid': 'medium', 'crit': 'critical'}


def _resolve_slash(war_room_id, cmd, rest):
    """Translate a recognised slash command into a structured message.

    Returns (kind, body, ref_type, ref_id, ref_case_id) for the system
    row, or None if the command is unrecognised (the route layer then
    falls through to a normal message).
    """
    if cmd == 'note':
        return ('note', rest, 'war_room_chat', None, None)
    if cmd == 'pin':
        return ('pin', rest, 'war_room_chat', None, None)

    if cmd == 'decision':
        if not rest:
            raise BusinessProcessingError(
                'Usage: /decision <what we decided>'
            )
        return ('decision', rest, 'war_room_chat', None, None)

    if cmd == 'attach':
        # `/attach <case_id> [reason]`
        parts = rest.split(None, 1)
        if not parts or not parts[0].isdigit():
            raise BusinessProcessingError('Usage: /attach <case_id> [reason]')
        case_id = int(parts[0])
        note = parts[1] if len(parts) > 1 else None
        from app.business.war_rooms import war_room_attach_case
        from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
        from app.models.authorization import CaseAccessLevel
        if ac_fast_check_current_user_has_case_access(
            case_id, [CaseAccessLevel.full_access]
        ) is None:
            raise BusinessProcessingError(
                f'You need full access on case #{case_id} to attach it'
            )
        war_room_attach_case(war_room_id, case_id,
                             attached_by_id=iris_current_user.id, note=note)
        body = f'Attached case #{case_id}' + (f' — {note}' if note else '')
        return ('case_attached', body, 'case', case_id, case_id)

    if cmd == 'detach':
        # `/detach <case_id>` — symmetrical with /attach. Useful in the
        # rare crisis where a case was attached in error or is moved out.
        parts = rest.split(None, 1)
        if not parts or not parts[0].isdigit():
            raise BusinessProcessingError('Usage: /detach <case_id>')
        case_id = int(parts[0])
        from app.business.war_rooms import war_room_detach_case
        from app.models.errors import ObjectNotFoundError
        try:
            war_room_detach_case(war_room_id, case_id)
        except ObjectNotFoundError:
            raise BusinessProcessingError(
                f'Case #{case_id} is not attached to this war room'
            )
        return (
            'case_detached', f'Detached case #{case_id}',
            'case', case_id, case_id,
        )

    if cmd == 'task':
        # `/task <title>` — single-arg form.
        # `/task @user <title>` — assign on creation (resolves the
        # mention to a User row via login or display name).
        if not rest:
            raise BusinessProcessingError('Usage: /task [@user] <title>')
        from app.business.war_room_tasks import war_room_task_create
        assignee_id = None
        assignee_label = None
        title = rest
        if rest.startswith('@'):
            head, _, tail = rest.partition(' ')
            if not tail.strip():
                raise BusinessProcessingError(
                    'Usage: /task @user <title>'
                )
            assignee_id, assignee_label = _resolve_user_handle(head[1:])
            title = tail.strip()
        task = war_room_task_create(
            war_room_id, title=title,
            created_by_id=iris_current_user.id,
            assignee_id=assignee_id,
        )
        body = (
            f'Created task for {assignee_label}: {title}'
            if assignee_label else f'Created task: {title}'
        )
        return ('task_assigned', body, 'war_room_task', task.task_id, None)

    if cmd == 'assign':
        # `/assign @user <title>` — shorthand for `/task @user <title>`.
        if not rest or not rest.startswith('@'):
            raise BusinessProcessingError('Usage: /assign @user <title>')
        head, _, tail = rest.partition(' ')
        if not tail.strip():
            raise BusinessProcessingError('Usage: /assign @user <title>')
        from app.business.war_room_tasks import war_room_task_create
        assignee_id, assignee_label = _resolve_user_handle(head[1:])
        title = tail.strip()
        task = war_room_task_create(
            war_room_id, title=title,
            created_by_id=iris_current_user.id,
            assignee_id=assignee_id,
        )
        body = f'Assigned to {assignee_label}: {title}'
        return ('task_assigned', body, 'war_room_task', task.task_id, None)

    if cmd == 'sitrep':
        if not rest:
            raise BusinessProcessingError('Usage: /sitrep <title>')
        from app.business.war_room_sitreps import sitrep_draft
        sit = sitrep_draft(war_room_id, title=rest,
                           authored_by_id=iris_current_user.id)
        return ('sitrep_published', f'Drafted SitRep: {rest}',
                'sitrep', sit.sitrep_id, None)

    if cmd == 'state':
        # `/state <open|active|standby|closed>` — flip the war-room
        # lifecycle without leaving the stream. Useful during a crisis
        # when the IC wants to wave the room into Active or wind it down.
        target = rest.strip().lower()
        if target not in _VALID_STATES:
            raise BusinessProcessingError(
                'Usage: /state <open|active|standby|closed>'
            )
        from app.business.war_rooms import war_room_update
        war_room_update(
            war_room_id, state=target,
            closed_by_id=iris_current_user.id if target == 'closed' else None,
        )
        return (
            'priority' if target in ('active', 'closed') else 'system',
            f'War room state set to {target}',
            'war_room', war_room_id, None,
        )

    if cmd == 'priority':
        # `/priority <low|medium|high|critical>` — purely a banner row.
        # State-side effects on the war room could be added later but
        # for now this just stamps a visible row in the stream the team
        # can rally around.
        level = rest.strip().lower()
        level = _PRIORITY_ALIASES.get(level, level)
        if level not in _PRIORITY_LEVELS:
            raise BusinessProcessingError(
                'Usage: /priority <low|medium|high|critical>'
            )
        if level in ('high', 'critical'):
            # Hot-up the war room when the operator declares a hot
            # priority — saves them an extra /state command.
            from app.business.war_rooms import war_room_update
            war_room_update(war_room_id, state='active')
        return (
            'priority',
            f'Priority set to {level.upper()}',
            'war_room', war_room_id, None,
        )

    if cmd == 'summary':
        # Auto-generate a SitRep draft seeded with the current war-room
        # snapshot. Operator just polishes the prose before publishing.
        from app.business.war_room_sitreps import sitrep_draft, _snapshot
        snap = _snapshot(war_room_id)
        body_md_lines = [
            '## Snapshot',
            f'- Attached cases: ' + (
                ', '.join(f'#{c}' for c in (snap.get('attached_case_ids') or [])) or '—'
            ),
            f'- Open tasks: {snap.get("tasks_open", 0)}',
            f'- Closed tasks: {snap.get("tasks_closed", 0)}',
            '',
            '## Situation',
            rest.strip() or '_Describe the current situation._',
            '',
            '## Next steps',
            '_What we plan to do next._',
        ]
        title = rest.strip()[:120] or f'Auto SitRep — {snap.get("captured_at", "now")[:10]}'
        sit = sitrep_draft(
            war_room_id,
            title=title,
            body_md='\n'.join(body_md_lines),
            authored_by_id=iris_current_user.id,
        )
        return (
            'sitrep_published',
            f'Drafted SitRep: {title}',
            'sitrep', sit.sitrep_id, None,
        )

    if cmd == 'thread':
        # `/thread <title>` — open a named topic the team can rally
        # replies under. The resolved row becomes a normal `message` with
        # a `thread_title` set, so it shows up in the threads sidebar
        # immediately even before anyone has replied.
        from app.business.war_room_chat import _threads_supported
        if not _threads_supported():
            raise BusinessProcessingError(
                'Threads are not enabled on this server yet — '
                'apply the latest migrations.'
            )
        title = rest.strip()
        if not title:
            raise BusinessProcessingError('Usage: /thread <title>')
        if len(title) > 160:
            raise BusinessProcessingError(
                'Thread title must be at most 160 characters'
            )
        # Tag the resolved tuple with a sentinel so the post handler
        # knows to call set_thread_title after creating the root. We
        # encode it via ref_type — the create path treats it as a
        # marker, not a foreign-key ref.
        return ('message', title, '__set_thread_title__', None, None)

    if cmd in ('help', '?'):
        body = (
            'Commands: /note /pin /decision /attach /detach /task /assign '
            '/sitrep /summary /state /priority /thread'
        )
        return ('system', body, None, None, None)

    return None


def _resolve_user_handle(handle):
    """Look up a `@handle` to a (user_id, display_label) pair.

    Matches against `user.user` (login) first, then `user.name`
    (display name). Case-insensitive. Raises a `BusinessProcessingError`
    when no match is found so the operator sees a useful hint instead
    of a silent no-assignee task.
    """
    from app.models.authorization import User
    from app.db import db
    from sqlalchemy import or_, func
    if not handle:
        raise BusinessProcessingError('Empty user mention')
    h = handle.strip()
    row = (
        db.session.query(User.id, User.user, User.name)
        .filter(
            or_(
                func.lower(User.user) == h.lower(),
                func.lower(User.name) == h.lower(),
            )
        )
        .first()
    )
    if row is None:
        raise BusinessProcessingError(
            f'No user matched @{handle}. Use a login or full name.'
        )
    return row.id, (row.name or row.user)


@war_rooms_chat_blueprint.post('')
@ac_api_requires()
def post_chat(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err

    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    body = raw.get('body')
    if not isinstance(body, str):
        return response_api_error('body is required')

    slash = parse_slash(body)
    if slash is not None:
        try:
            resolved = _resolve_slash(war_room_id, slash[0], slash[1])
        except BusinessProcessingError as e:
            return response_api_error(e.get_message())
        except ImportError:
            # A required sub-system isn't importable (test envs, a
            # feature module not yet packaged). Surface a generic
            # "unavailable" message — exception text would leak
            # internal module paths to the operator's browser.
            from app.logger import logger
            logger.exception('Slash command module missing')
            return response_api_error(
                'Command unavailable in this build.'
            )
        except Exception:  # noqa: BLE001 — generic catch with correlation id
            # Any unexpected error inside a slash handler used to bubble
            # up as a 500 with no body, which made `/summary` and the
            # like look like silent failures. Log full traceback
            # server-side with a correlation id and return a generic
            # message — don't echo `repr(e)` to the SPA, since that
            # surfaces table names, file paths, etc.
            import uuid
            from app.logger import logger
            err_id = uuid.uuid4().hex[:8]
            logger.exception(
                'Slash command failed', extra={'err_id': err_id}
            )
            return response_api_error(
                f'Command failed (ref {err_id}). See server logs.'
            )

        if resolved is not None:
            kind, body, ref_type, ref_id, ref_case_id = resolved
            # `/thread <title>` shoves the title through the `body` slot
            # of the resolved tuple and uses a sentinel `ref_type` so we
            # know to seed `thread_title` on the new root.
            wants_thread = ref_type == '__set_thread_title__'
            if wants_thread:
                ref_type = None
            try:
                msg = create_message(
                    war_room_id, iris_current_user.id, body,
                    kind=kind, ref_type=ref_type, ref_id=ref_id,
                    ref_case_id=ref_case_id,
                )
                if wants_thread:
                    set_thread_title(war_room_id, msg.message_id, body)
            except BusinessProcessingError as e:
                return response_api_error(e.get_message())
            _emit_socket(war_room_id, 'message:new', {'message_id': msg.message_id})
            return response_api_created({'message_id': msg.message_id, 'kind': msg.kind})

        # Unknown command. Returning an explicit 400 — instead of
        # falling through to `create_message(body)` and storing the
        # literal `/foo` text as a normal message — keeps the
        # operator's intent obvious. They get a "command not found"
        # toast and can correct themselves; nothing pollutes the
        # stream as a confused chat bubble.
        return response_api_error(
            f'Unknown command "/{slash[0]}". Try /help.'
        )

    try:
        msg = create_message(war_room_id, iris_current_user.id, body)
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())

    _emit_socket(war_room_id, 'message:new', {'message_id': msg.message_id})
    return response_api_created({'message_id': msg.message_id, 'kind': msg.kind})


@war_rooms_chat_blueprint.patch('/<int:message_id>')
@ac_api_requires()
def edit_chat(war_room_id, message_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        update_message(war_room_id, message_id, iris_current_user.id,
                       raw.get('body'))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    _emit_socket(war_room_id, 'message:edit', {'message_id': message_id})
    return response_api_success({'message_id': message_id})


@war_rooms_chat_blueprint.delete('/<int:message_id>')
@ac_api_requires()
def remove_chat(war_room_id, message_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    is_admin = ac_current_user_has_permission(Permissions.server_administrator)
    try:
        delete_message(war_room_id, message_id, iris_current_user.id, is_admin)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    _emit_socket(war_room_id, 'message:delete', {'message_id': message_id})
    return response_api_deleted()


# ----- Threads -------------------------------------------------------------


def _serialize_thread_root(row, followed_ids):
    """Compact serializer for the threads sidebar.

    Returns just enough to render a list row — the full body and the
    replies come from the dedicated /replies endpoint when the operator
    opens the thread.
    """
    return {
        'message_id': row.message_id,
        'thread_title': row.thread_title,
        'preview': (row.body or '')[:200] if row.body else None,
        'kind': row.kind,
        'author_id': row.author_id,
        'author_login': row.author_login,
        'author_name': row.author_name,
        'reply_count': int(row.reply_count) if row.reply_count else 0,
        'last_activity_at': (
            row.last_reply_at.isoformat() if row.last_reply_at
            else (row.created_at.isoformat() if row.created_at else None)
        ),
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'deleted_at': row.deleted_at.isoformat() if row.deleted_at else None,
        'is_followed': row.message_id in followed_ids,
    }


@war_rooms_chat_blueprint.get('/threads')
@ac_api_requires()
def list_threads(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    limit = request.args.get('limit', type=int)
    rows = list_thread_roots(war_room_id, limit=limit)
    followed = set(list_followed_thread_ids(war_room_id, iris_current_user.id))
    return response_api_success(
        data=[_serialize_thread_root(r, followed) for r in rows]
    )


@war_rooms_chat_blueprint.get('/<int:message_id>/replies')
@ac_api_requires()
def list_message_replies(war_room_id, message_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    limit = request.args.get('limit', type=int)
    try:
        rows = list_replies(war_room_id, message_id, limit=limit)
    except ObjectNotFoundError:
        return response_api_not_found()
    reactions = list_reactions([r.message_id for r in rows])
    return response_api_success(
        data=[_serialize(r, reactions.get(r.message_id)) for r in rows]
    )


@war_rooms_chat_blueprint.post('/<int:message_id>/replies')
@ac_api_requires()
def post_reply(war_room_id, message_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    body = raw.get('body')
    try:
        msg = create_reply(
            war_room_id, message_id, iris_current_user.id, body
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    _emit_socket(war_room_id, 'thread:reply', {
        'root_id': msg.parent_message_id, 'message_id': msg.message_id,
    })
    return response_api_created({
        'message_id': msg.message_id,
        'parent_message_id': msg.parent_message_id,
    })


@war_rooms_chat_blueprint.patch('/<int:message_id>/thread-title')
@ac_api_requires()
def patch_thread_title(war_room_id, message_id):
    """Name, rename, or clear a thread's title.

    Body: `{"title": "..."}`. An empty string or null removes the
    title. Works whether the caller passes the root or any reply id —
    the business layer folds to the root.
    """
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        root = set_thread_title(war_room_id, message_id, raw.get('title'))
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    _emit_socket(war_room_id, 'thread:retitle', {
        'message_id': root.message_id, 'title': root.thread_title,
    })
    return response_api_success({
        'message_id': root.message_id,
        'thread_title': root.thread_title,
    })


@war_rooms_chat_blueprint.post('/<int:message_id>/follow')
@ac_api_requires()
def post_follow(war_room_id, message_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        added = follow_thread(
            war_room_id, message_id, iris_current_user.id
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success({'message_id': message_id, 'added': added})


@war_rooms_chat_blueprint.delete('/<int:message_id>/follow')
@ac_api_requires()
def delete_follow(war_room_id, message_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        removed = unfollow_thread(
            war_room_id, message_id, iris_current_user.id
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success({'message_id': message_id, 'removed': removed})


@war_rooms_chat_blueprint.post('/<int:message_id>/reactions')
@ac_api_requires()
def post_reaction(war_room_id, message_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    emoji = raw.get('emoji')
    try:
        added = toggle_reaction(war_room_id, message_id,
                                 iris_current_user.id, emoji)
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    _emit_socket(war_room_id, 'message:reaction', {
        'message_id': message_id, 'user_id': iris_current_user.id,
        'emoji': emoji, 'added': added,
    })
    return response_api_success({'message_id': message_id, 'added': added})
