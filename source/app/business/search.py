#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
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
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from app.iris_engine.utils.tracker import track_activity
from app.datamgmt.comments import search_comments
from app.datamgmt.case.case_notes_db import search_notes
from app.datamgmt.case.case_iocs_db import search_iocs
from app.datamgmt.case.case_assets_db import search_assets
from app.datamgmt.case.case_events_db import search_events
from app.datamgmt.case.case_tasks_db import search_tasks
from app.datamgmt.case.case_evidences_search_db import search_evidences
from app.datamgmt.manage.manage_cases_db import user_list_cases_view


# Map every supported search type to (per-type helper, discriminator label).
# Helpers all take `(search_value, accessible_case_ids)` and return a list
# of `_asdict()` row dicts.
_SEARCHERS = {
    'ioc': search_iocs,
    'notes': search_notes,
    'comments': search_comments,
    'assets': search_assets,
    'events': search_events,
    'tasks': search_tasks,
    'evidences': search_evidences,
}

SUPPORTED_SEARCH_TYPES = tuple(_SEARCHERS.keys())


def _annotate(rows, search_type):
    # Tag every row with its discriminator + a stable id field the frontend
    # can use as a list key. Each helper projects its own primary key into
    # the row already; here we just normalise the name to `result_id`.
    id_field_per_type = {
        'ioc': 'ioc_id',
        'notes': 'note_id',
        'comments': 'comment_id',
        'assets': 'asset_id',
        'events': 'event_id',
        'tasks': 'task_id',
        'evidences': 'evidence_id',
    }
    id_field = id_field_per_type[search_type]
    for row in rows:
        row['type'] = search_type
        row['result_id'] = row.get(id_field)
    return rows


def search(search_type, search_value):
    """Backwards-compatible single-type search used by the legacy
    /search route. Returns a list of raw row dicts (no annotation, no
    access scoping).
    """
    track_activity(f'started a global search for {search_value} on {search_type}')

    if search_type in _SEARCHERS:
        return _SEARCHERS[search_type](search_value)
    return []


def search_across(search_value, search_types, user_id, page=1, per_page=25, case_id=None, case_ids=None):
    """Unified multi-type, access-scoped, paginated search.

    Args:
        search_value: pattern with optional `%` wildcards. Pattern semantics
            match the legacy per-type helpers (some use exact LIKE, others
            wrap the value in `%...%`).
        search_types: iterable of supported type strings; unknown types are
            silently dropped.
        user_id: scope the result set to cases this user has access to.
        page: 1-indexed page number.
        per_page: page size cap (we clamp to 1..100 to keep responses bounded).
        case_id: optional — restrict to a single case. Kept for back-compat
            with the single-case scope param; `case_ids` is the preferred
            shape going forward.
        case_ids: optional iterable of case ids to scope to. Each id is
            intersected with the caller's accessible-case list, so a
            request that mentions a forbidden case just drops it
            (the caller never learns whether the case exists).

    Returns:
        dict with `data` (list of annotated rows) and `pagination` (total,
        page, per_page, total_pages).
    """
    track_activity(f'started a global search for {search_value} on {list(search_types)}')

    accessible_case_ids = user_list_cases_view(user_id)

    # Normalise: collapse `case_id` (singular, legacy) into the same
    # `requested_case_ids` set as the new `case_ids` param.
    requested_case_ids = set()
    if case_id is not None:
        requested_case_ids.add(int(case_id))
    if case_ids:
        for cid in case_ids:
            try:
                requested_case_ids.add(int(cid))
            except (TypeError, ValueError):
                continue

    # Intersect with the user's access list so the caller can never
    # broaden their scope by guessing case ids they shouldn't see.
    if requested_case_ids:
        accessible_case_ids = [cid for cid in accessible_case_ids if cid in requested_case_ids]

    per_page = max(1, min(int(per_page or 25), 100))
    page = max(1, int(page or 1))

    # Each per-type helper streams its full result set. The combined list
    # is sliced for pagination — fine for typical SOC-sized datasets where
    # a single search rarely returns more than a few thousand rows. If
    # this ever needs to scale further, push pagination into the per-type
    # queries with UNION ALL.
    combined = []
    for st in search_types:
        if st not in _SEARCHERS:
            continue
        rows = _SEARCHERS[st](search_value, accessible_case_ids=accessible_case_ids)
        combined.extend(_annotate(rows, st))

    total = len(combined)
    total_pages = (total + per_page - 1) // per_page if total else 0
    start = (page - 1) * per_page
    end = start + per_page

    return {
        'data': combined[start:end],
        'pagination': {
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
        }
    }
