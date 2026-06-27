#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Versioned situational reports."""

import datetime
import json

from sqlalchemy import desc, func

from app.db import db
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError
from app.models.war_rooms import WarRoomCase
from app.models.war_rooms import WarRoomSitRep
from app.models.war_rooms import WarRoomTask


def _next_version(war_room_id):
    latest = (
        db.session.query(func.max(WarRoomSitRep.version))
        .filter(WarRoomSitRep.war_room_id == war_room_id)
        .scalar()
    )
    return (latest or 0) + 1


def _snapshot(war_room_id):
    """Capture the war-room state we want frozen in this SitRep.

    Keeps the report coherent later even if the underlying data drifts
    or the case is detached.
    """
    attached = (
        WarRoomCase.query
        .with_entities(WarRoomCase.case_id)
        .filter(WarRoomCase.war_room_id == war_room_id)
        .all()
    )
    open_tasks = (
        db.session.query(func.count(WarRoomTask.task_id))
        .filter(WarRoomTask.war_room_id == war_room_id,
                WarRoomTask.closed_at == None)
        .scalar() or 0
    )
    closed_tasks = (
        db.session.query(func.count(WarRoomTask.task_id))
        .filter(WarRoomTask.war_room_id == war_room_id,
                WarRoomTask.closed_at != None)
        .scalar() or 0
    )
    return {
        'attached_case_ids': [a.case_id for a in attached],
        'tasks_open': open_tasks,
        'tasks_closed': closed_tasks,
        'captured_at': datetime.datetime.utcnow().isoformat(),
    }


def sitrep_list(war_room_id):
    return (
        WarRoomSitRep.query
        .filter(WarRoomSitRep.war_room_id == war_room_id)
        .order_by(desc(WarRoomSitRep.version))
        .all()
    )


def sitrep_get(war_room_id, sitrep_id):
    row = WarRoomSitRep.query.filter_by(
        war_room_id=war_room_id, sitrep_id=sitrep_id
    ).first()
    if row is None:
        raise ObjectNotFoundError()
    return row


def sitrep_draft(war_room_id, title, body_md='', authored_by_id=None):
    if not isinstance(title, str) or not title.strip():
        raise BusinessProcessingError('SitRep title is required')
    sit = WarRoomSitRep()
    sit.war_room_id = war_room_id
    sit.version = _next_version(war_room_id)
    sit.title = title.strip()[:512]
    sit.body_md = body_md or ''
    sit.authored_by_id = authored_by_id
    sit.snapshot_json = None
    sit.published = False
    db.session.add(sit)
    db.session.commit()
    return sit


def sitrep_update(war_room_id, sitrep_id, title=None, body_md=None):
    sit = sitrep_get(war_room_id, sitrep_id)
    if sit.published:
        raise BusinessProcessingError('Published SitReps are immutable')
    if title is not None:
        if not isinstance(title, str) or not title.strip():
            raise BusinessProcessingError('SitRep title is required')
        sit.title = title.strip()[:512]
    if body_md is not None:
        sit.body_md = body_md
    db.session.commit()
    return sit


def sitrep_publish(war_room_id, sitrep_id):
    """Freeze the SitRep at the current war-room state.

    Publishing snapshots the attached cases + task counts so the
    report stays coherent later, and forbids further edits.
    """
    sit = sitrep_get(war_room_id, sitrep_id)
    if sit.published:
        raise BusinessProcessingError('SitRep is already published')
    sit.snapshot_json = _snapshot(war_room_id)
    sit.published = True
    sit.authored_at = datetime.datetime.utcnow()
    db.session.commit()
    return sit


def sitrep_delete(war_room_id, sitrep_id):
    sit = sitrep_get(war_room_id, sitrep_id)
    if sit.published:
        raise BusinessProcessingError('Published SitReps cannot be deleted')
    db.session.delete(sit)
    db.session.commit()


def sitrep_as_markdown(sit):
    """Render the SitRep as standalone markdown for download."""
    snap = sit.snapshot_json or {}
    lines = [
        f'# {sit.title}',
        '',
        f'_War room #{sit.war_room_id} — version {sit.version}_',
        '',
    ]
    if sit.authored_at:
        lines.append(f'**Authored at:** {sit.authored_at.isoformat()}')
    if sit.published:
        lines.append('**Status:** Published')
    else:
        lines.append('**Status:** Draft')
    lines.append('')
    if snap:
        lines.append('## Snapshot at publish')
        if 'attached_case_ids' in snap:
            ids = snap['attached_case_ids'] or []
            lines.append(f'- Attached cases: {", ".join(str(i) for i in ids) or "—"}')
        if 'tasks_open' in snap:
            lines.append(f'- Open tasks: {snap.get("tasks_open", 0)}')
        if 'tasks_closed' in snap:
            lines.append(f'- Closed tasks: {snap.get("tasks_closed", 0)}')
        lines.append('')
    lines.append('## Report')
    lines.append('')
    lines.append(sit.body_md or '_(no content)_')
    return '\n'.join(lines)


def sitrep_as_html(sit):
    """Render the SitRep as a stand-alone HTML page.

    Uses the same markdown→HTML pipeline IRIS already relies on for
    case notes so the output matches the rest of the product. Used by
    the export-to-PDF endpoint which feeds this into wkhtmltopdf when
    it's available, or returns the HTML directly for print-to-PDF.
    """
    try:
        import markdown
        body = markdown.markdown(
            sitrep_as_markdown(sit),
            extensions=['tables', 'fenced_code']
        )
    except Exception:
        body = '<pre>' + (sitrep_as_markdown(sit)
                          .replace('&', '&amp;')
                          .replace('<', '&lt;')
                          .replace('>', '&gt;')) + '</pre>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{sit.title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            max-width: 800px; margin: 2em auto; padding: 0 1em; color: #1f2937; }}
    h1, h2, h3 {{ color: #111827; }}
    code, pre {{ background: #f3f4f6; padding: 2px 4px; border-radius: 3px; }}
    pre {{ padding: 12px; overflow-x: auto; }}
    table {{ border-collapse: collapse; }}
    th, td {{ border: 1px solid #d1d5db; padding: 4px 8px; }}
    blockquote {{ border-left: 4px solid #94a3b8; margin: 1em 0; padding: 0 1em; color: #475569; }}
  </style>
</head>
<body>{body}</body>
</html>
"""
