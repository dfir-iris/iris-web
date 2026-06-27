#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
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

"""Business layer for the per-case named-timeline feature.

The model and migration live alongside the rest of the case models in
`app.models.cases`. This module centralises the CRUD, the default
"Main" timeline guarantee, and the helpers that wire events into
timelines so the REST blueprints can stay thin.
"""

import re

from app.db import db
from app.models.cases import CaseEventTimeline
from app.models.cases import CaseTimeline
from app.models.cases import CasesEvent
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


_NAME_MAX_LEN = 128
_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _validate_name(name):
    if not isinstance(name, str):
        raise BusinessProcessingError('Timeline name must be a string')
    stripped = name.strip()
    if not stripped:
        raise BusinessProcessingError('Timeline name is required')
    if len(stripped) > _NAME_MAX_LEN:
        raise BusinessProcessingError(
            f'Timeline name must be at most {_NAME_MAX_LEN} characters'
        )
    return stripped


def _validate_color(color):
    if color is None or color == '':
        return None
    if not isinstance(color, str) or not _HEX_COLOR_RE.match(color):
        raise BusinessProcessingError('Color must be a hex string like #RRGGBB')
    return color


def case_timeline_list(case_id):
    """Return every timeline registered against a case, defaults first."""
    return (
        CaseTimeline.query
        .filter(CaseTimeline.case_id == case_id)
        .order_by(CaseTimeline.is_default.desc(),
                  CaseTimeline.created_at.asc(),
                  CaseTimeline.timeline_id.asc())
        .all()
    )


def case_timeline_get(case_id, timeline_id):
    row = (
        CaseTimeline.query
        .filter_by(case_id=case_id, timeline_id=timeline_id)
        .first()
    )
    if row is None:
        raise ObjectNotFoundError()
    return row


def case_timeline_create(case_id, name, description=None, color=None,
                         created_by_id=None, is_default=False):
    """Create a new timeline on a case.

    Trips on the (case_id, name) unique constraint when the name is
    already in use — surfaced as a 400 by the REST layer.
    """
    name = _validate_name(name)
    color = _validate_color(color)

    existing = (
        CaseTimeline.query
        .filter_by(case_id=case_id, name=name)
        .first()
    )
    if existing is not None:
        raise BusinessProcessingError(
            f'A timeline named "{name}" already exists on this case'
        )

    timeline = CaseTimeline(
        case_id=case_id,
        name=name,
        description=description,
        color=color,
        is_default=bool(is_default),
        created_by_id=created_by_id,
    )
    db.session.add(timeline)
    db.session.commit()
    return timeline


def case_timeline_update(case_id, timeline_id, name=None, description=None,
                         color=None):
    timeline = case_timeline_get(case_id, timeline_id)

    if name is not None:
        new_name = _validate_name(name)
        if new_name != timeline.name:
            clash = (
                CaseTimeline.query
                .filter_by(case_id=case_id, name=new_name)
                .first()
            )
            if clash is not None and clash.timeline_id != timeline.timeline_id:
                raise BusinessProcessingError(
                    f'A timeline named "{new_name}" already exists on this case'
                )
            timeline.name = new_name
    if description is not None:
        timeline.description = description
    if color is not None:
        timeline.color = _validate_color(color)

    db.session.commit()
    return timeline


def case_timeline_delete(case_id, timeline_id):
    """Delete a timeline. The default timeline cannot be removed —
    deleting it would leave events with no fallback timeline and
    break the "Main" affordance every case relies on."""
    timeline = case_timeline_get(case_id, timeline_id)
    if timeline.is_default:
        raise BusinessProcessingError('The default timeline cannot be deleted')
    db.session.delete(timeline)
    db.session.commit()


def case_ensure_default_timeline(case_id, created_by_id=None):
    """Create the case's "Main" timeline if it doesn't have one yet.

    Idempotent — safe to call from case-create hooks even if the
    migration backfill already seeded a row.
    """
    existing = (
        CaseTimeline.query
        .filter_by(case_id=case_id, is_default=True)
        .first()
    )
    if existing is not None:
        return existing
    return case_timeline_create(
        case_id, 'Main',
        description='Default timeline',
        created_by_id=created_by_id,
        is_default=True,
    )


def _default_timeline_id(case_id):
    row = (
        CaseTimeline.query
        .filter_by(case_id=case_id, is_default=True)
        .with_entities(CaseTimeline.timeline_id)
        .first()
    )
    return row.timeline_id if row else None


def set_event_timelines(event_id, case_id, timeline_ids):
    """Replace the timeline-set attached to an event.

    Passing `None` is a no-op (caller didn't specify timelines — keep
    whatever's already on the row). Passing an empty list intentionally
    clears the event off every named timeline.

    Every id in `timeline_ids` must belong to `case_id` — cross-case
    membership is rejected to keep filter queries safe.
    """
    if timeline_ids is None:
        return

    if not isinstance(timeline_ids, (list, tuple)):
        raise BusinessProcessingError('timeline_ids must be a list of integers')

    cleaned = []
    for tid in timeline_ids:
        if not isinstance(tid, int):
            raise BusinessProcessingError('timeline_ids must be a list of integers')
        cleaned.append(tid)

    if cleaned:
        owned = (
            CaseTimeline.query
            .filter(CaseTimeline.case_id == case_id,
                    CaseTimeline.timeline_id.in_(cleaned))
            .with_entities(CaseTimeline.timeline_id)
            .all()
        )
        owned_ids = {r.timeline_id for r in owned}
        if owned_ids != set(cleaned):
            raise BusinessProcessingError(
                'One or more timeline_ids do not belong to this case'
            )

    CaseEventTimeline.query.filter_by(event_id=event_id).delete(
        synchronize_session=False
    )
    for tid in cleaned:
        db.session.add(CaseEventTimeline(event_id=event_id, timeline_id=tid))
    db.session.commit()


def attach_event_to_default_timeline_if_unset(event_id, case_id):
    """Ensure a newly-created event is on at least the default timeline
    when the caller did not specify a timeline set.

    Without this hook the event would be invisible when the user
    filters the timeline view down to any specific timeline — including
    the default — until they edit the event.
    """
    already = (
        CaseEventTimeline.query
        .filter_by(event_id=event_id)
        .first()
    )
    if already is not None:
        return
    default_id = _default_timeline_id(case_id)
    if default_id is None:
        # Edge case: an event was created before the default timeline
        # was provisioned (case predates this feature and the backfill
        # hasn't yet run). Caller is expected to ensure the default
        # exists first; bail quietly.
        return
    db.session.add(CaseEventTimeline(event_id=event_id, timeline_id=default_id))
    db.session.commit()


def get_event_timeline_ids(event_id):
    rows = (
        CaseEventTimeline.query
        .filter_by(event_id=event_id)
        .with_entities(CaseEventTimeline.timeline_id)
        .all()
    )
    return [r.timeline_id for r in rows]


def filter_events_by_timelines(case_id, timeline_ids):
    """Return event ids on the case that are attached to any of the
    given timelines. `timeline_ids=None` or empty means "no filter"
    (caller gets all event ids for the case).
    """
    if not timeline_ids:
        return None
    rows = (
        db.session.query(CaseEventTimeline.event_id)
        .join(CasesEvent, CasesEvent.event_id == CaseEventTimeline.event_id)
        .filter(CasesEvent.case_id == case_id)
        .filter(CaseEventTimeline.timeline_id.in_(timeline_ids))
        .distinct()
        .all()
    )
    return [r.event_id for r in rows]
