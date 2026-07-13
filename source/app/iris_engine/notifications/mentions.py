#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Extract user mentions from stored content.

The TipTap editor in iris-frontend renders user mentions as structured
HTML spans:

    <span data-mention data-kind="user" data-id="42" data-label="John Doe">@John Doe</span>

That form is unambiguous — we pull `data-id` directly, no handle
resolution needed. For legacy content authored before the mention node
existed (or pasted from external sources), we also match plain
`@handle` tokens and resolve them via `resolve_user_handle` below.

Both parsers are defensive: no HTML parser is loaded — a regex over the
persisted content is fast, sufficient for the strictly-shaped span the
editor emits, and immune to XSS-shaped inputs (we only pull numeric IDs
which we then look up in the DB).
"""

from __future__ import annotations

import re
from typing import Iterable
from typing import Optional
from typing import Set

from sqlalchemy import func
from sqlalchemy import or_

from app.db import db
from app.models.authorization import User


# Match `<span … data-mention … data-kind="user" … data-id="123" …>`.
# The order of attributes on the span is fixed by the TipTap render
# function, but we don't rely on it — the regex allows arbitrary
# attribute ordering and whitespace, and only extracts the numeric id
# when kind is explicitly `user`. `re.IGNORECASE` covers HTML
# normalisation quirks (some sanitisers lower-case tag/attr names).
_MENTION_SPAN_RE = re.compile(
    r"<span\b(?=[^>]*\bdata-mention\b)"
    r"(?=[^>]*\bdata-kind=[\"']user[\"'])"
    r"[^>]*?\bdata-id=[\"'](?P<id>\d+)[\"']",
    re.IGNORECASE,
)

# Team-kind mention span. Same shape as the user variant but keyed on
# `data-kind="team"`. Team IDs are war-room-scoped, so callers MUST
# resolve them via `war_room_team_member_user_ids(war_room_id, ...)` to
# avoid leaking notifications across rooms.
_TEAM_MENTION_SPAN_RE = re.compile(
    r"<span\b(?=[^>]*\bdata-mention\b)"
    r"(?=[^>]*\bdata-kind=[\"']team[\"'])"
    r"[^>]*?\bdata-id=[\"'](?P<id>\d+)[\"']",
    re.IGNORECASE,
)

# Legacy `@handle` matcher. Only used when the content contains NO
# mention spans (i.e. pre-mention-node notes) — otherwise a chip like
# `@John Doe` would double-count via both parsers. The character class
# is deliberately narrow: `\w` plus dot and dash, up to 64 chars, so
# emails like `@example.com` are captured but random punctuation isn't.
# Leading char is not a word char to avoid matching email addresses
# mid-text (`foo@bar` should NOT be a mention).
_LEGACY_MENTION_RE = re.compile(
    r"(?:^|[^\w.-])@(?P<handle>[A-Za-z][\w.-]{0,63})"
)


def extract_mentioned_user_ids(content: Optional[str]) -> Set[int]:
    """Return the set of user IDs mentioned in `content`.

    Combines both parsers:
    * TipTap-style `<span data-mention data-kind="user" data-id="N">`
      pulls IDs directly.
    * If (and only if) no mention span is present, fall back to
      plaintext `@handle` resolution against `User.user` / `User.name`.
      That lets old notes still trigger notifications while preventing
      double-count on new content.

    Missing / empty content yields an empty set.
    """
    if not content:
        return set()

    span_ids: Set[int] = set()
    for m in _MENTION_SPAN_RE.finditer(content):
        try:
            span_ids.add(int(m.group('id')))
        except (TypeError, ValueError):
            # A non-integer data-id shouldn't happen given the frontend
            # never emits one, but defensively skip rather than raise:
            # a save that mentions someone should not blow up because
            # some earlier tool wrote garbage into the span.
            continue

    if span_ids:
        return span_ids

    # Legacy path: only run the handle regex if the content has no
    # structured spans at all — otherwise a live chip like `@Alice`
    # would resolve twice (once via data-id, once via handle).
    handles = {m.group('handle') for m in _LEGACY_MENTION_RE.finditer(content)}
    if not handles:
        return set()
    return resolve_user_handles(handles)


def resolve_user_handles(handles: Iterable[str]) -> Set[int]:
    """Resolve a batch of `@handle` strings to a set of `User.id`.

    Match is case-insensitive against `user.user` (login) OR
    `user.name` (display name). Unknown handles are silently dropped —
    a mistyped mention should not raise, it just doesn't notify
    anyone. For UX where you WANT the error (slash commands), keep
    using `resolve_user_handle` in war-room chat which raises.
    """
    normalised = {h.strip().lower() for h in handles if h and h.strip()}
    if not normalised:
        return set()

    # Single query for the batch — cheap because both columns are
    # indexed via their uniqueness constraints (see User model).
    rows = (
        db.session.query(User.id)
        .filter(
            or_(
                func.lower(User.user).in_(normalised),
                func.lower(User.name).in_(normalised),
            )
        )
        .filter(User.active == True)  # noqa: E712 — SQLAlchemy needs `==`
        .all()
    )
    return {r.id for r in rows}


def extract_mentioned_team_ids(content: Optional[str]) -> Set[int]:
    """Return the set of team IDs mentioned in `content`.

    Team IDs are scoped to their war room; the caller is responsible
    for scoping the resolved team IDs to a specific war room when
    expanding them to user IDs.
    """
    if not content:
        return set()
    ids: Set[int] = set()
    for m in _TEAM_MENTION_SPAN_RE.finditer(content):
        try:
            ids.add(int(m.group('id')))
        except (TypeError, ValueError):
            continue
    return ids


def _resolve_team_names_to_ids(names: Iterable[str], war_room_id: int) -> Set[int]:
    """Resolve `@team-name` plaintext tokens against `WarRoomTeam.name`.

    Case-insensitive, war-room-scoped. Unknown names silently drop out.
    Used only from the plaintext fallback path in `resolve_mentions_to_user_ids`
    where the chat composer emits `@name` rather than a structured span.
    """
    normalised = {n.strip().lower() for n in names if n and n.strip()}
    if not normalised:
        return set()
    from app.models.war_rooms import WarRoomTeam
    rows = (
        db.session.query(WarRoomTeam.team_id)
        .filter(WarRoomTeam.war_room_id == war_room_id)
        .filter(func.lower(WarRoomTeam.name).in_(normalised))
        .all()
    )
    return {r.team_id for r in rows}


def resolve_mentions_to_user_ids(content: Optional[str],
                                 war_room_id: int) -> Set[int]:
    """Union of user IDs from both user-mentions and team-mention expansion.

    Team IDs found in `content` are scoped to `war_room_id` — team IDs
    that don't belong to this war room contribute nobody. Direct user
    mentions are returned as-is; membership scoping is the caller's job
    (see `_fire_message_notifications` for the war-room-member filter).

    Plaintext `@name` fallback also resolves team names for war-room
    content, which is where the chat composer emits plain `@name` tokens
    rather than structured spans.
    """
    if not content:
        return set()

    user_ids = extract_mentioned_user_ids(content)
    team_ids = extract_mentioned_team_ids(content)

    # Plaintext fallback: only run when the content had NO structured
    # user spans (same short-circuit as `extract_mentioned_user_ids`).
    # For plain `@handle` tokens, try user resolution first, then fall
    # through to team-name resolution for any unresolved handles.
    has_user_spans = bool(_MENTION_SPAN_RE.search(content))
    if not has_user_spans:
        handles = {m.group('handle')
                   for m in _LEGACY_MENTION_RE.finditer(content)}
        if handles:
            team_ids = team_ids | _resolve_team_names_to_ids(handles, war_room_id)

    if team_ids:
        # Local import to avoid a business-layer import loop at module load.
        from app.business.war_room_teams import war_room_team_member_user_ids
        user_ids = user_ids | war_room_team_member_user_ids(war_room_id, team_ids)
    return user_ids


def resolve_user_handle(handle: str) -> Optional[int]:
    """Single-handle lookup returning `user_id` or None.

    Convenience wrapper around `resolve_user_handles` for call sites
    that want scalar semantics without importing sets.
    """
    ids = resolve_user_handles([handle])
    if not ids:
        return None
    # Ambiguity (a login and a display name both matching) picks one
    # arbitrarily — mirrors war-room chat's `_resolve_user_handle`
    # behaviour which also picks first.
    return next(iter(ids))
