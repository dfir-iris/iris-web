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
from typing import Iterable
from typing import List
from typing import Optional

from sqlalchemy import func

from app.db import db
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.models.assets import CaseAssets
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.iocs import Ioc
from app.models.war_rooms import WarRoomTimeline
from app.models.war_rooms import WarRoomTimelineEvent
from app.models.war_rooms import WarRoomTimelineEventAsset
from app.models.war_rooms import WarRoomTimelineEventIoc


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
    track_activity(f'created war room timeline "{t.name}"', war_room_id=war_room_id)
    t = call_modules_hook('on_postload_war_room_timeline_create', t)
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
    track_activity(f'updated war room timeline "{t.name}"', war_room_id=war_room_id)
    t = call_modules_hook('on_postload_war_room_timeline_update', t)
    return t


def delete_timeline(war_room_id, timeline_id):
    t = get_timeline(war_room_id, timeline_id)
    if t.is_default:
        raise BusinessProcessingError('The default timeline cannot be deleted')
    name = t.name
    db.session.delete(t)
    db.session.commit()
    track_activity(f'deleted war room timeline "{name}"', war_room_id=war_room_id)
    call_modules_hook('on_postload_war_room_timeline_delete',
                      {'war_room_id': war_room_id, 'timeline_id': timeline_id})


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


def _validate_category(category):
    if category is None or category == '':
        return None
    if not isinstance(category, str):
        raise BusinessProcessingError('Category must be a string')
    stripped = category.strip()
    if len(stripped) > _CATEGORY_MAX_LEN:
        raise BusinessProcessingError(
            f'Category must be at most {_CATEGORY_MAX_LEN} characters'
        )
    return stripped or None


def create_timeline_event(war_room_id, timeline_id, title=None, content=None,
                          event_date=None, event_tz=None, color=None,
                          category=None, case_id=None, event_id=None,
                          source=None, raw=None, tags=None, is_flagged=False,
                          parent_id=None, asset_ids=None, ioc_ids=None,
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
    category = _validate_category(category)

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
    row.source = source
    row.raw = raw
    row.tags = tags
    row.is_flagged = bool(is_flagged)
    if parent_id is not None:
        # Parent must belong to the same war room — enforce here so a
        # cross-tenant parent id can't sneak in via the create payload.
        _get_event(war_room_id, parent_id)
        row.parent_id = parent_id
    row.created_by_id = created_by_id
    db.session.add(row)
    db.session.flush()  # obtain row.id before hooking up joins

    if asset_ids:
        _set_asset_links(row.id, asset_ids)
    if ioc_ids:
        _set_ioc_links(row.id, ioc_ids)

    db.session.commit()
    label = row.title or (f'case event #{event_id}' if event_id else 'event')
    track_activity(f'added timeline event "{label}"', war_room_id=war_room_id)
    row = call_modules_hook('on_postload_war_room_timeline_event_create', row)
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
                          category=_UNSET, timeline_id=_UNSET,
                          source=_UNSET, raw=_UNSET, tags=_UNSET,
                          is_flagged=_UNSET, parent_id=_UNSET,
                          asset_ids=_UNSET, ioc_ids=_UNSET):
    """Partial update for a war-room timeline event.

    Sentinel-based: a field passed as `_UNSET` is left untouched, while
    explicit `None` clears it. `timeline_id` is the drag-between-timelines
    knob — validates the target belongs to the same war room. The
    `asset_ids` / `ioc_ids` lists (when passed) fully replace the row's
    current asset / IOC associations — pass `[]` to detach everything,
    omit to keep the existing set.
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
        row.category = _validate_category(category)
    if source is not _UNSET:
        row.source = source
    if raw is not _UNSET:
        row.raw = raw
    if tags is not _UNSET:
        row.tags = tags
    if is_flagged is not _UNSET:
        row.is_flagged = bool(is_flagged)
    if parent_id is not _UNSET:
        if parent_id is None:
            row.parent_id = None
        else:
            if parent_id == row.id:
                raise BusinessProcessingError('An event cannot be its own parent')
            _get_event(war_room_id, parent_id)  # cross-tenant guard
            row.parent_id = parent_id
    if asset_ids is not _UNSET:
        _set_asset_links(row.id, asset_ids or [])
    if ioc_ids is not _UNSET:
        _set_ioc_links(row.id, ioc_ids or [])
    db.session.commit()
    label = row.title or (f'case event #{row.event_id}' if row.event_id else f'event #{row.id}')
    track_activity(f'updated timeline event "{label}"', war_room_id=war_room_id)
    row = call_modules_hook('on_postload_war_room_timeline_event_update', row)
    return row


def toggle_event_flag(war_room_id, event_id):
    """Flip `is_flagged` on the event and return the new value. Kept as
    its own endpoint so the frontend flag button doesn't need to know
    the current state — one click, server toggles."""
    row = _get_event(war_room_id, event_id)
    row.is_flagged = not row.is_flagged
    db.session.commit()
    label = row.title or f'event #{row.id}'
    track_activity(
        f'{"flagged" if row.is_flagged else "unflagged"} timeline event "{label}"',
        war_room_id=war_room_id,
    )
    return row


def duplicate_event(war_room_id, event_id, created_by_id=None):
    """Shallow-copy an event onto the same timeline. Asset and IOC
    associations are copied; comments intentionally aren't — a new
    event starts its own conversation."""
    src = _get_event(war_room_id, event_id)
    dup = WarRoomTimelineEvent()
    dup.timeline_id = src.timeline_id
    dup.case_id = src.case_id
    dup.event_id = src.event_id
    dup.title = f'{src.title} (copy)' if src.title else 'Untitled (copy)'
    dup.content = src.content
    dup.raw = src.raw
    dup.source = src.source
    dup.tags = src.tags
    dup.is_flagged = src.is_flagged
    dup.event_date = src.event_date
    dup.event_tz = src.event_tz
    dup.color = src.color
    dup.category = src.category
    dup.parent_id = src.parent_id
    dup.created_by_id = created_by_id
    db.session.add(dup)
    db.session.flush()

    # Copy asset/IOC links so the duplicate feels like a "start-from-here"
    # rather than a stripped skeleton. Comments intentionally left off.
    src_asset_ids = [
        r.asset_id for r in
        WarRoomTimelineEventAsset.query.filter_by(event_id=src.id).all()
    ]
    if src_asset_ids:
        _set_asset_links(dup.id, src_asset_ids)
    src_ioc_ids = [
        r.ioc_id for r in
        WarRoomTimelineEventIoc.query.filter_by(event_id=src.id).all()
    ]
    if src_ioc_ids:
        _set_ioc_links(dup.id, src_ioc_ids)

    db.session.commit()
    track_activity(
        f'duplicated timeline event "{src.title or f"#{src.id}"}"',
        war_room_id=war_room_id,
    )
    return dup


def _set_asset_links(event_id: int, asset_ids: Iterable[int]) -> None:
    """Replace the event's asset associations. Idempotent — dedupes ids
    on the way in and doesn't crash if the client passed a non-existent
    asset id (silently skipped after the FK-integrity check)."""
    wanted = {int(a) for a in asset_ids if a is not None}
    WarRoomTimelineEventAsset.query.filter_by(event_id=event_id).delete()
    if not wanted:
        return
    existing = {
        row.asset_id for row in
        CaseAssets.query.filter(CaseAssets.asset_id.in_(wanted))
        .with_entities(CaseAssets.asset_id).all()
    }
    for aid in wanted & existing:
        db.session.add(WarRoomTimelineEventAsset(
            event_id=event_id, asset_id=aid,
        ))


def _set_ioc_links(event_id: int, ioc_ids: Iterable[int]) -> None:
    """Replace the event's IOC associations. Same idempotent semantics
    as `_set_asset_links`."""
    wanted = {int(i) for i in ioc_ids if i is not None}
    WarRoomTimelineEventIoc.query.filter_by(event_id=event_id).delete()
    if not wanted:
        return
    existing = {
        row.ioc_id for row in
        Ioc.query.filter(Ioc.ioc_id.in_(wanted))
        .with_entities(Ioc.ioc_id).all()
    }
    for iid in wanted & existing:
        db.session.add(WarRoomTimelineEventIoc(
            event_id=event_id, ioc_id=iid,
        ))


def set_event_assets(war_room_id, event_id, asset_ids):
    """Public wrapper — cross-war-room-check + replace-and-commit."""
    _get_event(war_room_id, event_id)
    _set_asset_links(event_id, asset_ids or [])
    db.session.commit()


def set_event_iocs(war_room_id, event_id, ioc_ids):
    _get_event(war_room_id, event_id)
    _set_ioc_links(event_id, ioc_ids or [])
    db.session.commit()


# Read-side hydration ------------------------------------------------------

def event_asset_ids(event_id: int) -> List[int]:
    return [
        r.asset_id for r in
        WarRoomTimelineEventAsset.query
        .filter_by(event_id=event_id)
        .with_entities(WarRoomTimelineEventAsset.asset_id)
        .all()
    ]


def event_ioc_ids(event_id: int) -> List[int]:
    return [
        r.ioc_id for r in
        WarRoomTimelineEventIoc.query
        .filter_by(event_id=event_id)
        .with_entities(WarRoomTimelineEventIoc.ioc_id)
        .all()
    ]


def event_children_count(event_id: int) -> int:
    return (
        db.session.query(func.count(WarRoomTimelineEvent.id))
        .filter(WarRoomTimelineEvent.parent_id == event_id)
        .scalar()
        or 0
    )


def delete_timeline_event(war_room_id, event_id):
    row = _get_event(war_room_id, event_id)
    label = row.title or (f'case event #{row.event_id}' if row.event_id else f'event #{row.id}')
    db.session.delete(row)
    db.session.commit()
    track_activity(f'deleted timeline event "{label}"', war_room_id=war_room_id)
    call_modules_hook('on_postload_war_room_timeline_event_delete',
                      {'war_room_id': war_room_id, 'event_id': event_id})
