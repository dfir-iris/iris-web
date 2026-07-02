#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Core notification listeners.

Wired into the module-hook system as *built-in* handlers (not via the
`IrisModule` table). We hook the same events modules can register for,
but we bypass the module dispatcher — one direct call registered via
`register_notification_listeners()` from `post_init`.

The design keeps each listener defensive:

* Any exception is swallowed and logged. A save flow (create note,
  update task, close case) MUST NOT fail because a notification
  couldn't be fired.
* Actor exclusion is done centrally — `_actor_id()` reads
  `iris_current_user` when available, else None (background/celery
  contexts).
"""

from __future__ import annotations

import logging
from typing import Any
from typing import Callable
from typing import Optional

from app.iris_engine.module_handler import module_handler as _mh
from app.iris_engine.notifications.mentions import extract_mentioned_user_ids
from app.iris_engine.notifications.service import notify
from app.iris_engine.notifications.service import notify_many


logger = logging.getLogger(__name__)


def _actor_id() -> Optional[int]:
    """Return the current authenticated user's id, or None outside a
    request. `iris_current_user` is a LocalProxy so we can't just do
    `getattr(..., 'id', None)` — accessing `id` when there is no user
    triggers the proxy which may raise."""
    try:
        from app.blueprints.iris_user import iris_current_user
        # `iris_current_user.id` throws when there is no auth context
        # (Celery worker, CLI); guard with a getattr on the proxied
        # object.
        user = iris_current_user._get_current_object()  # type: ignore[attr-defined]
        if user is None:
            return None
        return int(getattr(user, 'id', 0)) or None
    except Exception:
        return None


def _safe(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a listener so exceptions never bubble into the caller."""
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            logger.exception('Notification listener %s failed', fn.__name__)
            return None
    wrapped.__name__ = fn.__name__
    return wrapped


# --- Note listeners ---------------------------------------------------------

@_safe
def _on_note(note) -> None:
    """Fire mention notifications for a note create/update.

    Uses the extractor which handles both TipTap mention spans and
    legacy `@handle` text. We can't diff against a previous revision
    here (note_revisions are persisted separately and would double the
    query cost per save); duplicate mentions across edits are dealt
    with client-side by the bell aggregating on `source_type+source_id`.
    """
    if note is None:
        return
    content = getattr(note, 'note_content', None)
    user_ids = extract_mentioned_user_ids(content)
    if not user_ids:
        return

    title = 'You were mentioned in a note'
    body = getattr(note, 'note_title', None) or ''
    case_id = getattr(note, 'note_case_id', None)
    note_id = getattr(note, 'note_id', None)
    link = f'/case/{case_id}/notes/{note_id}' if case_id and note_id else None

    notify_many(
        user_ids=user_ids,
        event_type='mention',
        title=title,
        body=body,
        link=link,
        source_type='note',
        source_id=note_id,
        exclude_user_ids=[_actor_id()] if _actor_id() else [],
    )


# --- Comment listeners ------------------------------------------------------

_COMMENT_HOOK_LINKS = {
    # Maps hook name to a builder returning (link, parent_type, parent_id)
    # given the hook payload dict. Each comment kind has its own payload
    # shape so this is table-driven rather than a big if/else.
    'note': lambda p: (
        f'/case/{p["note"].note_case_id}/notes/{p["note"].note_id}',
        'note', p['note'].note_id, p['note'].note_case_id,
    ),
    'task': lambda p: (
        f'/case/{p["task"].task_case_id}/tasks/{p["task"].id}',
        'task', p['task'].id, p['task'].task_case_id,
    ),
    'asset': lambda p: (
        f'/case/{p["asset"].case_id}/assets/{p["asset"].asset_id}',
        'asset', p['asset'].asset_id, p['asset'].case_id,
    ),
    'evidence': lambda p: (
        f'/case/{p["evidence"].case_id}/evidence/{p["evidence"].id}',
        'evidence', p['evidence'].id, p['evidence'].case_id,
    ),
    'ioc': lambda p: (
        f'/case/{p["ioc"].case_id}/iocs/{p["ioc"].ioc_id}',
        'ioc', p['ioc'].ioc_id, p['ioc'].case_id,
    ),
    'event': lambda p: (
        f'/case/{p["event"].case_id}/timeline/{p["event"].event_id}',
        'event', p['event'].event_id, p['event'].case_id,
    ),
    'alert': lambda p: (
        f'/alerts/{p["alert"].alert_id}',
        'alert', p['alert'].alert_id, None,
    ),
}


def _make_comment_listener(kind: str):
    @_safe
    def _listener(payload) -> None:
        if not isinstance(payload, dict) or 'comment' not in payload:
            return
        comment = payload['comment']
        content = getattr(comment, 'comment_text', None)
        user_ids = extract_mentioned_user_ids(content)
        if not user_ids:
            return
        builder = _COMMENT_HOOK_LINKS.get(kind)
        if builder is None:
            return
        link, source_type, source_id, _case_id = builder(payload)

        notify_many(
            user_ids=user_ids,
            event_type='mention',
            title=f'You were mentioned in a {kind} comment',
            body=(content or '')[:255],
            link=link,
            source_type=f'{source_type}_comment',
            source_id=getattr(comment, 'comment_id', None),
            exclude_user_ids=[_actor_id()] if _actor_id() else [],
        )
    _listener.__name__ = f'_on_{kind}_comment'
    return _listener


# --- Task listeners ---------------------------------------------------------

@_safe
def _on_task(task) -> None:
    """Notify assignees on case-task create/update.

    Case tasks use the `task_assignee` join table for their assignees
    (see models.TaskAssignee); we read the current set at fire time.
    We don't diff pre/post so an edit re-notifies — acceptable v1
    trade-off. See plan for follow-up work to add a per-task
    idempotency window.
    """
    if task is None:
        return
    task_id = getattr(task, 'id', None)
    if not task_id:
        return
    # Import here to keep this module import-cheap (models pull in the
    # whole SQLAlchemy tree).
    from app.models.models import TaskAssignee
    assignee_ids = [
        row.user_id for row in
        TaskAssignee.query.filter(TaskAssignee.task_id == task_id).all()
    ]
    if not assignee_ids:
        return
    title = getattr(task, 'task_title', 'A task')
    case_id = getattr(task, 'task_case_id', None)
    link = f'/case/{case_id}/tasks/{task_id}' if case_id else None
    notify_many(
        user_ids=assignee_ids,
        event_type='task_assigned',
        title='You were assigned a task',
        body=title,
        link=link,
        source_type='task',
        source_id=task_id,
        exclude_user_ids=[_actor_id()] if _actor_id() else [],
    )


@_safe
def _on_global_task(task) -> None:
    """Notify the assignee on global-task create/update. Uses the
    scalar `task_assignee_id` on GlobalTasks (no join table)."""
    if task is None:
        return
    assignee = getattr(task, 'task_assignee_id', None)
    if not assignee:
        return
    task_id = getattr(task, 'id', None)
    title = getattr(task, 'task_title', 'A task')
    notify(
        user_id=int(assignee),
        event_type='task_assigned',
        title='You were assigned a global task',
        body=title,
        link=f'/dim-tasks/{task_id}' if task_id else None,
        source_type='global_task',
        source_id=task_id,
    ) if _actor_id() != int(assignee) else None


# --- Case listeners ---------------------------------------------------------

@_safe
def _on_case_create(case) -> None:
    """New case with an owner other than the actor → notify."""
    if case is None:
        return
    owner_id = getattr(case, 'owner_id', None)
    if not owner_id:
        return
    if _actor_id() == int(owner_id):
        return
    case_id = getattr(case, 'case_id', None)
    notify(
        user_id=int(owner_id),
        event_type='case_assigned',
        title='You own a new case',
        body=getattr(case, 'name', None) or '',
        link=f'/case/{case_id}' if case_id else None,
        source_type='case',
        source_id=case_id,
    )


@_safe
def _on_case_update(case) -> None:
    """Case update fires two notifications: state change (if the case
    is set) and reviewer/owner assignment (mirrors create).

    We can't observe deltas without a "before" — a follow-up can add
    a light per-case state stash. For v1 we fire on every update; the
    bell UX de-noise falls back to the read-status filter."""
    if case is None:
        return
    case_id = getattr(case, 'case_id', None)
    if not case_id:
        return
    link = f'/case/{case_id}'
    body = getattr(case, 'name', None) or ''

    # Reviewer assignment
    reviewer_id = getattr(case, 'reviewer_id', None)
    if reviewer_id and _actor_id() != int(reviewer_id):
        notify(
            user_id=int(reviewer_id),
            event_type='case_assigned',
            title='You were assigned as a case reviewer',
            body=body,
            link=link,
            source_type='case',
            source_id=case_id,
        )

    # State change — we fire against the owner unless the actor IS
    # the owner. Fires on every update; see comment above.
    owner_id = getattr(case, 'owner_id', None)
    if owner_id and _actor_id() != int(owner_id):
        notify(
            user_id=int(owner_id),
            event_type='case_state_change',
            title='A case you own was updated',
            body=body,
            link=link,
            source_type='case',
            source_id=case_id,
        )


# --- Alert listeners --------------------------------------------------------

@_safe
def _on_alert(alert) -> None:
    if alert is None:
        return
    owner_id = getattr(alert, 'alert_owner_id', None)
    if not owner_id or _actor_id() == int(owner_id):
        return
    alert_id = getattr(alert, 'alert_id', None)
    notify(
        user_id=int(owner_id),
        event_type='alert_assigned',
        title='An alert was assigned to you',
        body=getattr(alert, 'alert_title', None) or '',
        link=f'/alerts/{alert_id}' if alert_id else None,
        source_type='alert',
        source_id=alert_id,
    )


@_safe
def _on_alert_escalate(alert) -> None:
    if alert is None:
        return
    owner_id = getattr(alert, 'alert_owner_id', None)
    if not owner_id or _actor_id() == int(owner_id):
        return
    alert_id = getattr(alert, 'alert_id', None)
    notify(
        user_id=int(owner_id),
        event_type='alert_escalated',
        title='An alert you own was escalated',
        body=getattr(alert, 'alert_title', None) or '',
        link=f'/alerts/{alert_id}' if alert_id else None,
        source_type='alert',
        source_id=alert_id,
    )


# --- Registration -----------------------------------------------------------

# Map hook name -> listener. Populated at import time so a single
# `register_notification_listeners()` call wires everything.
_HOOK_MAP = {
    # Notes
    'on_postload_note_create': _on_note,
    'on_postload_note_update': _on_note,
    # Comments (one listener per parent kind because payload shape
    # differs slightly per kind — see _make_comment_listener).
    'on_postload_note_commented': _make_comment_listener('note'),
    'on_postload_note_comment_update': _make_comment_listener('note'),
    'on_postload_task_commented': _make_comment_listener('task'),
    'on_postload_task_comment_update': _make_comment_listener('task'),
    'on_postload_asset_commented': _make_comment_listener('asset'),
    'on_postload_asset_comment_update': _make_comment_listener('asset'),
    'on_postload_evidence_commented': _make_comment_listener('evidence'),
    'on_postload_evidence_comment_update': _make_comment_listener('evidence'),
    'on_postload_ioc_commented': _make_comment_listener('ioc'),
    'on_postload_ioc_comment_update': _make_comment_listener('ioc'),
    'on_postload_event_commented': _make_comment_listener('event'),
    'on_postload_event_comment_update': _make_comment_listener('event'),
    'on_postload_alert_commented': _make_comment_listener('alert'),
    'on_postload_alert_comment_update': _make_comment_listener('alert'),
    # Tasks
    'on_postload_task_create': _on_task,
    'on_postload_task_update': _on_task,
    'on_postload_global_task_create': _on_global_task,
    'on_postload_global_task_update': _on_global_task,
    # Cases
    'on_postload_case_create': _on_case_create,
    'on_postload_case_update': _on_case_update,
    # Alerts
    'on_postload_alert_create': _on_alert,
    'on_postload_alert_update': _on_alert,
    'on_postload_alert_escalate': _on_alert_escalate,
}


def register_notification_listeners() -> None:
    """Monkey-patch `call_modules_hook` to fan out to our built-in
    listeners in addition to the module-registered handlers.

    The existing dispatcher (module_handler.call_modules_hook) is the
    single choke point for every hook fire in the app. We wrap it once
    at app-start so we don't need to touch every business/*.py caller.
    Wrapping is idempotent — a second call is a no-op (checked via a
    sentinel attribute).
    """
    if getattr(_mh, '_notifications_wrapped', False):
        return

    original = _mh.call_modules_hook

    def wrapped(hook_name: str, data: any, caseid: int = None,
                hook_ui_name: str = None, module_name: str = None):
        # Run modules first, then our listeners. Modules can rewrite
        # `data` and we want to notify based on the final state.
        result = original(hook_name, data, caseid=caseid,
                          hook_ui_name=hook_ui_name, module_name=module_name)
        listener = _HOOK_MAP.get(hook_name)
        if listener is not None:
            listener(result if result is not None else data)
        return result

    _mh.call_modules_hook = wrapped
    _mh._notifications_wrapped = True
