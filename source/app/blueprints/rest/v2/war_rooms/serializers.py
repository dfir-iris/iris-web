#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Plain dict serializers for war-room objects.

These are intentionally not marshmallow schemas — the war-room object
graph is shallow and the v2 API ships flat dicts already (see
`case_timelines.py` for the same pattern). Centralising the shape here
means the REST sub-modules don't need to repeat field lists.
"""


def serialize_war_room(war_room):
    return {
        'war_room_id': war_room.war_room_id,
        'war_room_uuid': str(war_room.war_room_uuid) if war_room.war_room_uuid else None,
        'name': war_room.name,
        'description': war_room.description,
        'state': war_room.state,
        'severity_id': war_room.severity_id,
        'color': war_room.color,
        'created_at': war_room.created_at.isoformat() if war_room.created_at else None,
        'created_by_id': war_room.created_by_id,
        'closed_at': war_room.closed_at.isoformat() if war_room.closed_at else None,
        'closed_by_id': war_room.closed_by_id,
        'custom_attributes': war_room.custom_attributes,
    }


def serialize_member(row):
    return {
        'war_room_id': row.war_room_id,
        'user_id': row.user_id,
        'user_login': row.login,
        'user_name': row.name,
        'role': row.role,
        'added_at': row.added_at.isoformat() if row.added_at else None,
    }


def serialize_case_attachment(row):
    return {
        'war_room_id': row.war_room_id,
        'case_id': row.case_id,
        'case_name': row.case_name,
        # Customer / owner / lifecycle joined server-side so the SPA can
        # render a rich row + filter on these fields without a per-row
        # fetch.
        'customer_id': getattr(row, 'customer_id', None),
        'customer_name': getattr(row, 'customer_name', None),
        'owner_id': getattr(row, 'owner_id', None),
        'owner_login': getattr(row, 'owner_login', None),
        'owner_name': getattr(row, 'owner_name', None),
        'open_date': row.open_date.isoformat() if getattr(row, 'open_date', None) else None,
        'close_date': row.close_date.isoformat() if getattr(row, 'close_date', None) else None,
        'state_id': getattr(row, 'state_id', None),
        'state_name': getattr(row, 'state_name', None),
        'task_count': int(getattr(row, 'task_count', 0) or 0),
        'task_open_count': int(getattr(row, 'task_open_count', 0) or 0),
        'attached_at': row.attached_at.isoformat() if row.attached_at else None,
        'note': row.note,
    }


def serialize_case_war_room_summary(row):
    """Shape used by `/cases/<id>/war-rooms` (case detail badge)."""
    return {
        'war_room_id': row.war_room_id,
        'name': row.name,
        'state': row.state,
        'color': row.color,
    }
