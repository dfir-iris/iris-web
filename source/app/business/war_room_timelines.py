#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Per-war-room named timelines.

Operationally identical to the per-case named timelines, but scoped to
a war room and using its own polymorphic event table
(`WarRoomTimelineEvent`) so an entry can be either a free-form row the
operator wrote inline OR a reference to an existing case event.
"""

import re

from app.db import db
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomTimeline
from app.models.war_rooms import WarRoomTimelineEvent


_NAME_MAX_LEN = 128
_CATEGORY_MAX_LEN = 64
_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')
_UNSET = object()


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


def list_timelines(war_room_id):
    return (
        WarRoomTimeline.query
        .filter(WarRoomTimeline.war_room_id == war_room_id)
        .order_by(WarRoomTimeline.is_default.desc(),
                  WarRoomTimeline.created_at.asc(),
                  WarRoomTimeline.timeline_id.asc())
        .all()
    )


def get_timeline(war_room_id, timeline_id):
    row = WarRoomTimeline.query.filter_by(
        war_room_id=war_room_id, timeline_id=timeline_id
    ).first()
    if row is None:
        raise ObjectNotFoundError()
    return row


def create_timeline(war_room_id, name, description=None, color=None,
                    created_by_id=None, is_default=False):
    name = _validate_name(name)
    color = _validate_color(color)

    existing = WarRoomTimeline.query.filter_by(
        war_room_id=war_room_id, name=name
    ).first()
    if existing is not None:
        raise BusinessProcessingError(
            f'A timeline named "{name}" already exists on this war room'
        )

    t = WarRoomTimeline()
    t.war_room_id = war_room_id
    t.name = name
    t.description = description
    t.color = color
    t.is_default = bool(is_default)
    t.created_by_id = created_by_id
    db.session.add(t)
    db.session.commit()
    return t


def update_timeline(war_room_id, timeline_id, name=None, description=None,
                    color=None):
    t = get_timeline(war_room_id, timeline_id)
    if name is not None:
        new_name = _validate_name(name)
        if new_name != t.name:
            clash = WarRoomTimeline.query.filter_by(
                war_room_id=war_room_id, name=new_name
            ).first()
            if clash is not None and clash.timeline_id != t.timeline_id:
                raise BusinessProcessingError(
                    f'A timeline named "{new_name}" already exists on this war room'
                )
            t.name = new_name
    if description is not None:
        t.description = description
    if color is not None:
        t.color = _validate_color(color)
    db.session.commit()
    return t


def delete_timeline(war_room_id, timeline_id):
    t = get_timeline(war_room_id, timeline_id)
    if t.is_default:
        raise BusinessProcessingError('The default timeline cannot be deleted')
    db.session.delete(t)
    db.session.commit()


# Events -------------------------------------------------------------------

def list_timeline_events(war_room_id, timeline_ids=None):
    """List events on the war room.

    If `timeline_ids` is given, restrict to those timelines (which must
    belong to this war room).
    """
    q = (
        WarRoomTimelineEvent.query
        .join(WarRoomTimeline,
              WarRoomTimeline.timeline_id == WarRoomTimelineEvent.timeline_id)
        .filter(WarRoomTimeline.war_room_id == war_room_id)
    )
    if timeline_ids:
        q = q.filter(WarRoomTimelineEvent.timeline_id.in_(list(timeline_ids)))
    return q.order_by(WarRoomTimelineEvent.event_date.asc().nullslast(),
                      WarRoomTimelineEvent.id.asc()).all()


def create_timeline_event(war_room_id, timeline_id, title=None, content=None,
                          event_date=None, event_tz=None, color=None,
                          category=None, case_id=None, event_id=None,
                          created_by_id=None):
    timeline = get_timeline(war_room_id, timeline_id)
    if (case_id is None) != (event_id is None):
        raise BusinessProcessingError(
            'case_id and event_id must be provided together'
        )
    if case_id is None and event_id is None and not title and not content:
        raise BusinessProcessingError(
            'Provide either a case event reference or a title/content'
        )
    color = _validate_color(color)
    if category is not None:
        if not isinstance(category, str):
            raise BusinessProcessingError('Category must be a string')
        stripped = category.strip()
        if len(stripped) > _CATEGORY_MAX_LEN:
            raise BusinessProcessingError(
                f'Category must be at most {_CATEGORY_MAX_LEN} characters'
            )
        category = stripped or None
    row = WarRoomTimelineEvent()
    row.timeline_id = timeline.timeline_id
    row.case_id = case_id
    row.event_id = event_id
    row.title = title
    row.content = content
    row.event_date = event_date
    row.event_tz = event_tz
    row.color = color
    row.category = category
    row.created_by_id = created_by_id
    db.session.add(row)
    db.session.commit()
    return row


def _get_event(war_room_id, event_id):
    row = (
        WarRoomTimelineEvent.query
        .join(WarRoomTimeline,
              WarRoomTimeline.timeline_id == WarRoomTimelineEvent.timeline_id)
        .filter(WarRoomTimeline.war_room_id == war_room_id,
                WarRoomTimelineEvent.id == event_id)
        .first()
    )
    if row is None:
        raise ObjectNotFoundError()
    return row


def update_timeline_event(war_room_id, event_id, *, title=_UNSET, content=_UNSET,
                          event_date=_UNSET, event_tz=_UNSET, color=_UNSET,
                          category=_UNSET, timeline_id=_UNSET):
    """Partial update for a war-room timeline event.

    Sentinel-based: a field passed as `_UNSET` is left untouched, while
    explicit `None` clears it. `timeline_id` is the drag-between-timelines
    knob — validates the target belongs to the same war room.
    """
    row = _get_event(war_room_id, event_id)
    if timeline_id is not _UNSET and timeline_id != row.timeline_id:
        target = get_timeline(war_room_id, timeline_id)
        row.timeline_id = target.timeline_id
    if title is not _UNSET:
        row.title = title
    if content is not _UNSET:
        row.content = content
    if event_date is not _UNSET:
        row.event_date = event_date
    if event_tz is not _UNSET:
        row.event_tz = event_tz
    if color is not _UNSET:
        row.color = _validate_color(color)
    if category is not _UNSET:
        if category is None or category == '':
            row.category = None
        else:
            if not isinstance(category, str):
                raise BusinessProcessingError('Category must be a string')
            stripped = category.strip()
            if len(stripped) > _CATEGORY_MAX_LEN:
                raise BusinessProcessingError(
                    f'Category must be at most {_CATEGORY_MAX_LEN} characters'
                )
            row.category = stripped or None
    db.session.commit()
    return row


def delete_timeline_event(war_room_id, event_id):
    row = _get_event(war_room_id, event_id)
    db.session.delete(row)
    db.session.commit()
