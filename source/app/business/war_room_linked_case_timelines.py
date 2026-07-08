#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Projection layer that surfaces case-side timelines inside a war room.

A war room aggregates multiple cases (`WarRoomCase`), and every case has
its own timelines (`CaseTimeline` + `CaseEventTimeline`). Historically
the war-room timeline view only rendered its own native
`WarRoomTimelineEvent` rows — analysts had to copy case events over one
by one if they wanted them here. This module turns that around: instead
of copying, we compute the projection on the fly so the war-room
timeline can UNION its native events with a live view of any case
timelines the user has opted in to.

The projection is deliberately read-only. Writes (create/edit/delete)
still go through the case-side timeline endpoints — the case remains
the source of truth for its own events. This keeps the data model
clean (no drift between projected copies and the originals) and lets
edits/deletes on the case propagate immediately to every war room the
case is attached to.

ACL is layered on top of the war-room ACL: even if you can read the
war room, you only see the case timelines / events for cases you also
have case-level read access to. Cases you can't reach are silently
elided so the sidebar doesn't advertise their existence.
"""

from typing import Iterable
from typing import List
from typing import Optional
from typing import Set

from sqlalchemy import func

from app.business.case_timelines import case_timeline_list
from app.db import db
from app.models.authorization import CaseAccessLevel
from app.models.cases import CaseEventTimeline
from app.models.cases import CaseTimeline
from app.models.cases import Cases
from app.models.cases import CasesEvent
from app.models.war_rooms import WarRoomCase


def _accessible_linked_case_ids(war_room_id: int, user_id: int) -> Set[int]:
    """Every case linked to `war_room_id` that the caller can read.

    Kept private and used by both entry points below so a caller who
    can't reach Case #12 sees the same "as if it isn't linked" view on
    the timelines sidebar AND on the events endpoint (i.e., can't
    smuggle case events by guessing timeline ids).

    Late import of the case-ACL helper matches the pattern in
    `app.business.collab._war_room_access_check` — importing at module
    top would trip a circular import through `app.blueprints`."""
    from app.blueprints.access_controls import ac_fast_check_user_has_case_access

    linked_case_ids = [
        row.case_id
        for row in WarRoomCase.query
        .filter(WarRoomCase.war_room_id == war_room_id)
        .with_entities(WarRoomCase.case_id)
        .all()
    ]
    if not linked_case_ids:
        return set()

    reachable: Set[int] = set()
    for case_id in linked_case_ids:
        level = ac_fast_check_user_has_case_access(
            user_id, case_id,
            [CaseAccessLevel.read_only, CaseAccessLevel.full_access],
        )
        if level is not None:
            reachable.add(case_id)
    return reachable


def list_linked_case_timelines(war_room_id: int, user_id: int) -> list:
    """Return a nested tree of case timelines available to the caller.

    Shape:
        [
          {
            'case_id': int,
            'case_name': str,
            'timelines': [
              {'timeline_id': int, 'name': str,
               'color': str | None, 'is_default': bool},
              ...
            ],
          },
          ...
        ]

    Cases without any timelines are still included (as an empty list)
    — the sidebar can show "no timelines yet" affordance without a
    separate probe. Ordering: cases by attach time (via `WarRoomCase`),
    timelines using `case_timeline_list`'s existing "defaults first,
    then chronological" order.
    """
    accessible = _accessible_linked_case_ids(war_room_id, user_id)
    if not accessible:
        return []

    # Preserve WarRoomCase.attached_at ordering — this is what the
    # linked-cases page uses, so the timelines sidebar reads in the
    # same order.
    attach_rows = (
        WarRoomCase.query
        .filter(WarRoomCase.war_room_id == war_room_id,
                WarRoomCase.case_id.in_(accessible))
        .order_by(WarRoomCase.attached_at.asc())
        .with_entities(WarRoomCase.case_id, WarRoomCase.attached_at)
        .all()
    )
    ordered_case_ids = [row.case_id for row in attach_rows]

    case_names = dict(
        Cases.query
        .filter(Cases.case_id.in_(accessible))
        .with_entities(Cases.case_id, Cases.name)
        .all()
    )

    result = []
    for case_id in ordered_case_ids:
        timelines = case_timeline_list(case_id)
        result.append({
            'case_id': case_id,
            'case_name': case_names.get(case_id) or f'Case #{case_id}',
            'timelines': [
                {
                    'timeline_id': t.timeline_id,
                    'name': t.name,
                    'color': t.color,
                    'is_default': bool(t.is_default),
                }
                for t in timelines
            ],
        })
    return result


def list_linked_case_events(war_room_id: int, user_id: int,
                            case_timeline_ids: Iterable[int]) -> list:
    """Return case events shaped like `WarRoomTimelineEvent` rows.

    The frontend merges these with the native war-room events and sorts
    both by `event_date` client-side. Field names are aligned with
    `WarRoomTimelineEvent`'s serializer so the timeline card component
    doesn't need per-source branching:

        {
          'id': 'case:<case_id>:<event_id>',   # synthetic; won't collide with native ids
          'war_room_source': 'case',            # discriminator for the client
          'timeline_id': <case timeline id>,
          'case_id': int,
          'event_id': int,
          'title': str,
          'content': str | None,
          'event_date': ISO8601 | None,
          'event_tz': str | None,
          'color': str | None,
          'category': None,                     # case events don't carry a category today
          'created_at': ISO8601 | None,         # maps from `event_added`
          'created_by_id': int | None,          # maps from `user_id`
        }

    Empty / unknown / inaccessible timeline ids are silently dropped —
    the goal is that a stale preference blob (e.g., the analyst
    unlinked a case) degrades gracefully to "no events from that
    source" rather than a 500.
    """
    if not case_timeline_ids:
        return []

    # Normalise + dedupe. The route already CSV-parses, but callers
    # from other code paths might pass strings mixed with ints.
    wanted_ids: Set[int] = set()
    for raw in case_timeline_ids:
        try:
            wanted_ids.add(int(raw))
        except (TypeError, ValueError):
            continue
    if not wanted_ids:
        return []

    accessible_case_ids = _accessible_linked_case_ids(war_room_id, user_id)
    if not accessible_case_ids:
        return []

    # Filter to timelines that (a) exist, (b) belong to a linked +
    # accessible case. A single JOIN keeps the trip to the DB cheap
    # and enforces the tenancy check server-side even if the client
    # supplied ids from a case they can't see.
    valid_pairs = (
        CaseTimeline.query
        .filter(CaseTimeline.timeline_id.in_(wanted_ids),
                CaseTimeline.case_id.in_(accessible_case_ids))
        .with_entities(CaseTimeline.timeline_id, CaseTimeline.case_id)
        .all()
    )
    if not valid_pairs:
        return []
    valid_timeline_ids = {row.timeline_id for row in valid_pairs}

    rows = (
        CasesEvent.query
        .join(CaseEventTimeline,
              CaseEventTimeline.event_id == CasesEvent.event_id)
        .filter(CaseEventTimeline.timeline_id.in_(valid_timeline_ids))
        .add_columns(CaseEventTimeline.timeline_id)
        .order_by(CasesEvent.event_date.asc().nullslast(),
                  CasesEvent.event_id.asc())
        .all()
    )

    return [_serialize_case_event(event, timeline_id)
            for event, timeline_id in rows]


def _serialize_case_event(event: CasesEvent, source_timeline_id: int) -> dict:
    """Case event → war-room-event-shaped dict. Kept out of the query so
    it stays trivial to reuse from tests and any future socket-driven
    push path that needs the same shape.

    Every field the war-room event card renders is populated here from
    its case-side equivalent — `event_source` / `event_raw` /
    `event_tags` / `event_is_flagged` map straight across. Assets /
    IOCs / children_count are hydrated too so the frontend doesn't
    have to branch on `war_room_source` when reading. Projected events
    remain read-only regardless of what these fields contain — the
    frontend gates edit affordances on `war_room_source === 'case'`.
    Per-event comments aren't part of the war-room event surface.
    """
    from app.models.models import CaseEventsAssets
    from app.models.models import CaseEventsIoc

    # Cheap targeted lookups. Bulk-batching these into a single N-way
    # join would be micro-optimisation; the projection is called with
    # a bounded set of events (per selected case timeline) and each
    # scalar count is a single index lookup.
    asset_ids = [
        r.asset_id for r in
        CaseEventsAssets.query
        .filter_by(event_id=event.event_id)
        .with_entities(CaseEventsAssets.asset_id).all()
    ]
    ioc_ids = [
        r.ioc_id for r in
        CaseEventsIoc.query
        .filter_by(event_id=event.event_id)
        .with_entities(CaseEventsIoc.ioc_id).all()
    ]
    children_count = (
        db.session.query(func.count(CasesEvent.event_id))
        .filter(CasesEvent.parent_event_id == event.event_id)
        .scalar() or 0
    )

    return {
        # Synthetic id — never a bare integer so it won't collide with
        # native `WarRoomTimelineEvent.id`. The frontend uses this as
        # its `key` and drag-drop identity.
        'id': f'case:{event.case_id}:{event.event_id}',
        'war_room_source': 'case',
        # Reuse the case event's UUID so the "copy share link" affordance
        # produces a URL that also works when opened from the source case.
        'uuid': str(event.event_uuid) if event.event_uuid else '',
        'timeline_id': source_timeline_id,
        # Parent traversal not projected across the boundary — a case's
        # parent event might not be on the timelines the user selected,
        # so leaving `parent_id=None` here means the war-room tree view
        # shows projected events as roots. Reasonable default.
        'parent_id': None,
        'case_id': event.case_id,
        'event_id': event.event_id,
        'title': event.event_title,
        'content': event.event_content,
        'raw': event.event_raw,
        'source': event.event_source,
        'tags': event.event_tags,
        'is_flagged': bool(event.event_is_flagged),
        'event_date': event.event_date.isoformat() if event.event_date else None,
        'event_tz': event.event_tz,
        'color': event.event_color,
        # Case events use a M2M `case_events_category` join rather than a
        # column — surface as `None` here so the card component's
        # existing `category` handling still works. If we ever want the
        # category badge on projected events we can enrich this later
        # without changing the shape.
        'category': None,
        'modification_history': event.modification_history,
        'assets': asset_ids,
        'iocs': ioc_ids,
        'children_count': children_count,
        'created_at': event.event_added.isoformat() if event.event_added else None,
        'created_by_id': event.user_id,
    }
