#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""SQLAlchemy models for the War Room feature.

A war room is a crisis-coordination workspace that aggregates multiple
cases under a single command view. It is intentionally peer-of-case
rather than child-of-case: a single war room can pull from any number
of cases the operator has access to, while each case remains
authoritative for its own evidence and investigation.

The tables live here (not in `cases.py`) because a war room is *not*
case-scoped, and the per-war-room ACL precedence (default → group →
user) is identical to the case ACL but routes to a different set of
join tables.
"""

import enum
import uuid

from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import CheckConstraint
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import db


class WarRoomState(enum.Enum):
    """Lifecycle states.

    `open` = newly created, gathering scope. `active` = the crisis is
    being actively run from this room. `standby` = monitored but
    quiescent. `closed` = archival — chat input disabled, read-only.
    """
    open = 'open'
    active = 'active'
    standby = 'standby'
    closed = 'closed'


class WarRoomMemberRole(enum.Enum):
    """Soft roles inside a war room.

    These are presentation/coordination hints — `lead` shows up as the
    Incident Commander chip, `responder` is the default for IR
    operators, `observer` is for stakeholders who need visibility
    without write access. The real access gate is the war-room ACL
    layer, not this role.
    """
    lead = 'lead'
    responder = 'responder'
    observer = 'observer'


class WarRoom(db.Model):
    __tablename__ = 'war_room'

    war_room_id = Column(BigInteger, primary_key=True)
    war_room_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4,
                           server_default=text('gen_random_uuid()'),
                           nullable=False, unique=True)
    name = Column(String(256), nullable=False)
    description = Column(Text, nullable=True)
    state = Column(String(16), nullable=False,
                   server_default=text("'open'"))
    severity_id = Column(BigInteger, ForeignKey('severities.severity_id'), nullable=True)
    color = Column(String(7), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    created_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    # Archive is a filing decision independent of the operational state
    # (open / active / standby / closed). NULL = live in the default
    # list; timestamped = moved out of the default view but still fully
    # readable. See migration c4d1a2b7f503.
    archived_at = Column(DateTime, nullable=True)
    archived_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    custom_attributes = Column(JSONB, nullable=True)

    created_by = relationship('User', foreign_keys=[created_by_id])
    closed_by = relationship('User', foreign_keys=[closed_by_id])
    archived_by = relationship('User', foreign_keys=[archived_by_id])
    severity = relationship('Severity')


class WarRoomCase(db.Model):
    """Many-to-many: a war room aggregates N cases."""
    __tablename__ = 'war_room_case'
    __table_args__ = (
        UniqueConstraint('war_room_id', 'case_id', name='uq_war_room_case'),
    )

    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         primary_key=True, nullable=False)
    case_id = Column(BigInteger,
                     ForeignKey('cases.case_id', ondelete='CASCADE'),
                     primary_key=True, nullable=False, index=True)
    attached_at = Column(DateTime, nullable=False, server_default=text('now()'))
    attached_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    note = Column(Text, nullable=True)

    war_room = relationship('WarRoom')
    case = relationship('Cases')
    attached_by = relationship('User')


class WarRoomMember(db.Model):
    """Roster of users assigned to a war room with their soft role.

    Distinct from the ACL — being a member is a presentation/notification
    affordance, while access is enforced by `UserWarRoomEffectiveAccess`.
    Most flows add a row here AND set the corresponding ACL entry in one
    transaction, but they're decoupled so admin tooling can grant
    read-only ACL access to observers who aren't formal members.
    """
    __tablename__ = 'war_room_member'
    __table_args__ = (
        UniqueConstraint('war_room_id', 'user_id', name='uq_war_room_member'),
    )

    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('user.id', ondelete='CASCADE'),
                     primary_key=True, nullable=False)
    role = Column(String(16), nullable=False, server_default=text("'responder'"))
    added_at = Column(DateTime, nullable=False, server_default=text('now()'))
    added_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)

    war_room = relationship('WarRoom')
    user = relationship('User', foreign_keys=[user_id])
    added_by = relationship('User', foreign_keys=[added_by_id])


class WarRoomTimeline(db.Model):
    """Named timeline on a war room.

    Operationally identical to `CaseTimeline` but scoped to the war
    room. Every war room gets an `is_default=True` row named "Main"
    at creation time; new chat-derived events and cross-case event
    pull-ins are attached to it unless the caller specifies otherwise.
    """
    __tablename__ = 'war_room_timeline'
    __table_args__ = (
        UniqueConstraint('war_room_id', 'name', name='uq_war_room_timeline_name'),
    )

    timeline_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False,
                        server_default=text('false'))
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    created_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)

    war_room = relationship('WarRoom')
    created_by = relationship('User')


class WarRoomTimelineEvent(db.Model):
    """Polymorphic timeline entry.

    Carries either a reference to a case event (the dominant case) OR a
    free-form entry the operator authored inline in the war room. The
    `case_id`/`event_id` pair is nullable for that reason; when both are
    null, `title` and `event_date` are the source of truth.

    Feature parity with `CasesEvent`: this row can carry a source label,
    a machine-raw payload, comma-separated tags, a triage flag, and a
    self-referencing parent for tree rendering. Assets and IOCs attach
    through the `war_room_timeline_event_assets` / `..._iocs` M2M
    tables. Comments hang off the row via a nullable FK on the shared
    `Comments` table (see `models/comments.py`).
    """
    __tablename__ = 'war_room_timeline_event'
    __table_args__ = (
        CheckConstraint(
            "(case_id IS NULL AND event_id IS NULL) OR "
            "(case_id IS NOT NULL AND event_id IS NOT NULL)",
            name='ck_war_room_timeline_event_case_event_pair'
        ),
    )

    id = Column(BigInteger, primary_key=True)
    # Public identifier used by share links. Case events grew one for
    # the same reason — a stable-across-renames external URL that
    # doesn't require the client to know the numeric id.
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                  server_default=text('gen_random_uuid()'), unique=True)
    timeline_id = Column(BigInteger,
                         ForeignKey('war_room_timeline.timeline_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    # Self-ref for parent/child tree rendering. `SET NULL` on parent
    # delete so an orphaned child stays in the timeline rather than
    # cascading away — user's decision to promote it later.
    parent_id = Column(BigInteger,
                       ForeignKey('war_room_timeline_event.id', ondelete='SET NULL'),
                       nullable=True)
    case_id = Column(BigInteger,
                     ForeignKey('cases.case_id', ondelete='SET NULL'),
                     nullable=True)
    event_id = Column(BigInteger,
                      ForeignKey('cases_events.event_id', ondelete='CASCADE'),
                      nullable=True)
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    # Machine-original payload for evidence trail — kept alongside the
    # human-readable `content` so an analyst can always drop back to
    # the untouched source. Matches `CasesEvent.event_raw`.
    raw = Column(Text, nullable=True)
    # Free-text source label (e.g. "Suricata", "Firewall"). Rendered as
    # an uppercase caption in the event card metadata row.
    source = Column(Text, nullable=True)
    # Comma-separated tags. Same wire shape as `CasesEvent.event_tags`;
    # the frontend splits on `,` before rendering as `#foo` pills.
    tags = Column(Text, nullable=True)
    # Triage flag — red flag icon in the metadata row when set. No
    # semantics beyond "someone marked this important".
    is_flagged = Column(Boolean, nullable=False, default=False,
                        server_default=text('false'))
    event_date = Column(DateTime, nullable=True)
    event_tz = Column(String(16), nullable=True)
    color = Column(String(7), nullable=True)
    category = Column(String(64), nullable=True)
    # JSONB audit trail written by `add_obj_history_entry`. Same shape
    # as the case-notes / alert-cluster modification history so the
    # existing history dialog can render both without branching.
    modification_history = Column(JSONB, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    created_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)

    timeline = relationship('WarRoomTimeline')
    case = relationship('Cases')
    event = relationship('CasesEvent')
    created_by = relationship('User')
    parent = relationship('WarRoomTimelineEvent',
                          remote_side=[id], backref='children')


class WarRoomTimelineEventAsset(db.Model):
    """M2M — pin an asset from any case to a war-room timeline event.

    Mirrors `CaseEventsAssets`. War-room events aren't case-scoped, so
    the `case_id` column present on the case-side row is dropped here;
    the linked case is inferable from `case_assets.case_id` if callers
    need it. Cascading DELETE on `event_id` cleans up automatically
    when the parent event goes away.
    """
    __tablename__ = 'war_room_timeline_event_assets'
    __table_args__ = (
        UniqueConstraint('event_id', 'asset_id',
                         name='uq_war_room_timeline_event_asset'),
    )

    id = Column(BigInteger, primary_key=True)
    event_id = Column(BigInteger,
                      ForeignKey('war_room_timeline_event.id', ondelete='CASCADE'),
                      nullable=False, index=True)
    asset_id = Column(BigInteger,
                      ForeignKey('case_assets.asset_id', ondelete='CASCADE'),
                      nullable=False)

    event = relationship('WarRoomTimelineEvent', backref='asset_links')
    asset = relationship('CaseAssets')


class WarRoomTimelineEventIoc(db.Model):
    """M2M — pin an IOC from any case to a war-room timeline event.

    Mirrors `CaseEventsIoc` with the same rationale as
    `WarRoomTimelineEventAsset` — no redundant `case_id`, cascading
    delete on event removal."""
    __tablename__ = 'war_room_timeline_event_iocs'
    __table_args__ = (
        UniqueConstraint('event_id', 'ioc_id',
                         name='uq_war_room_timeline_event_ioc'),
    )

    id = Column(BigInteger, primary_key=True)
    event_id = Column(BigInteger,
                      ForeignKey('war_room_timeline_event.id', ondelete='CASCADE'),
                      nullable=False, index=True)
    ioc_id = Column(BigInteger,
                    ForeignKey('ioc.ioc_id', ondelete='CASCADE'),
                    nullable=False)

    event = relationship('WarRoomTimelineEvent', backref='ioc_links')
    ioc = relationship('Ioc')


class WarRoomChatMessage(db.Model):
    """A single entry in the war room chat stream.

    `kind` discriminates between operator-authored messages and the
    system rows we synthesise from events elsewhere in IRIS (a case
    activity row, a task assignment, a published SitRep). `ref_type`
    and `ref_id` point back to the source object so the chat row can
    render an inline preview without duplicating the source data.
    """
    __tablename__ = 'war_room_chat_message'

    message_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    author_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    body = Column(Text, nullable=True)
    # Discriminator. Lower-case strings rather than an enum so adding a
    # new system message type doesn't require a migration.
    kind = Column(String(32), nullable=False,
                  server_default=text("'message'"))
    # Pointer back to the originating object when `kind` is not 'message'.
    # `ref_type` is a short label like 'user_activity', 'case_task',
    # 'sitrep', 'war_room_task'. `ref_case_id` is denormalised so we can
    # cheaply filter the chat by case without a join.
    ref_type = Column(String(32), nullable=True)
    ref_id = Column(BigInteger, nullable=True)
    ref_case_id = Column(BigInteger, ForeignKey('cases.case_id', ondelete='SET NULL'),
                         nullable=True, index=True)
    # Threading. `parent_message_id` is nullable: a row with NULL parent
    # is a top-level stream message; a row pointing at another message
    # is a reply hanging off that root. Two-level only — replies can
    # never themselves be parents (enforced at the business layer, not
    # at the DB, so we don't pay for a CHECK on every insert).
    #
    # `thread_title` is set on root messages that have been promoted to
    # named topics via `/thread <title>`. NULL means the message is a
    # plain root with no name; readers fall back to a truncation of the
    # body for the threads list.
    parent_message_id = Column(BigInteger,
                               ForeignKey('war_room_chat_message.message_id',
                                          ondelete='CASCADE'),
                               nullable=True, index=True)
    thread_title = Column(String(160), nullable=True)
    # `activity_type` USED to live here when case activity was backfilled
    # into the chat table. The stream now pulls UserActivity rows live
    # and classifies them at read time, so this column is never
    # written to and never selected. The Alembic migration that adds
    # the column (`e5a1b46c7d92`) is still kept for forward-compat
    # in case we want server-side filtering by type later, but
    # absence of the column at the DB level is intentionally tolerated.
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    edited_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    # Analyst-toggled sticky flag. Pinned messages surface in the
    # sidebar "Decisions & Pins" list next to the existing pin-kind
    # system rows and get a small pin badge inline in the stream.
    # Kept as a Boolean column rather than a separate table because
    # pin state is a per-message single-bit toggle and shows up in the
    # message serializer every read — a join would be gratuitous.
    is_pinned = Column(Boolean, nullable=False, default=False,
                       server_default=text('false'))

    war_room = relationship('WarRoom')
    author = relationship('User')


class WarRoomThreadFollower(db.Model):
    """Per-user follow flag for a thread root.

    Pure indicator for now — used by the UI to show the followed-thread
    pill and (later) to drive notifications. One row per (user, root)
    pair; deleted to unfollow.
    """
    __tablename__ = 'war_room_thread_follower'
    __table_args__ = (
        UniqueConstraint('message_id', 'user_id',
                         name='uq_war_room_thread_follower'),
    )

    id = Column(BigInteger, primary_key=True)
    # The thread root — always a `WarRoomChatMessage` with
    # `parent_message_id IS NULL`.
    message_id = Column(BigInteger,
                        ForeignKey('war_room_chat_message.message_id',
                                   ondelete='CASCADE'),
                        nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey('user.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))


class WarRoomChatReaction(db.Model):
    __tablename__ = 'war_room_chat_reaction'
    __table_args__ = (
        UniqueConstraint('message_id', 'user_id', 'emoji',
                         name='uq_war_room_chat_reaction'),
    )

    id = Column(BigInteger, primary_key=True)
    message_id = Column(BigInteger,
                        ForeignKey('war_room_chat_message.message_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey('user.id', ondelete='CASCADE'),
                     nullable=False)
    emoji = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))


class WarRoomChatPoll(db.Model):
    """A poll posted inline in the war-room chat stream.

    Every poll has a companion `WarRoomChatMessage` with `kind='poll'`
    that hosts it in the stream (via `chat_message_id`); deleting the
    message soft-deletes the stream entry but keeps the poll audit
    trail via `ON DELETE SET NULL`. The poll row itself is only
    removed when the war room is deleted (CASCADE on `war_room_id`).

    `is_anonymous` is a display-side toggle — vote rows still carry
    `user_id` so the app can enforce "one vote per user in a
    single-select poll" and "user can retract their own vote". The
    REST serializer strips voter identity on read for anonymous
    polls; a separate admin-audit endpoint can still surface it if a
    war-room admin needs to investigate ballot-stuffing.
    """
    __tablename__ = 'war_room_chat_poll'

    poll_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    author_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    question = Column(Text, nullable=False)
    is_multi_select = Column(Boolean, nullable=False, default=False,
                             server_default=text('false'))
    is_anonymous = Column(Boolean, nullable=False, default=False,
                          server_default=text('false'))
    # Optional deadline. NULL means "no auto-close"; a value in the
    # past means the poll is closed for new votes (business layer
    # rejects new votes past the deadline).
    closes_at = Column(DateTime, nullable=True)
    # Set once the poll is manually closed by author/admin or a vote
    # attempt observed the deadline had passed and lazy-closed it.
    closed_at = Column(DateTime, nullable=True)
    # Backref to the stream message that hosts the poll UI. `SET NULL`
    # so soft-deleting the chat row leaves the poll audit trail intact.
    chat_message_id = Column(BigInteger,
                             ForeignKey('war_room_chat_message.message_id',
                                        ondelete='SET NULL'),
                             nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))

    war_room = relationship('WarRoom')
    author = relationship('User')
    chat_message = relationship('WarRoomChatMessage', foreign_keys=[chat_message_id])
    options = relationship('WarRoomChatPollOption',
                           back_populates='poll',
                           cascade='all, delete-orphan',
                           order_by='WarRoomChatPollOption.sort_order')


class WarRoomChatPollOption(db.Model):
    """One selectable answer on a poll.

    `sort_order` is client-controlled so the composer's drag-reorder
    UX has a stable representation; the business layer only enforces
    uniqueness of the option's parent poll (via cascading FK) and
    doesn't police the numeric range.
    """
    __tablename__ = 'war_room_chat_poll_option'

    option_id = Column(BigInteger, primary_key=True)
    poll_id = Column(BigInteger,
                     ForeignKey('war_room_chat_poll.poll_id', ondelete='CASCADE'),
                     nullable=False, index=True)
    label = Column(Text, nullable=False)
    sort_order = Column(Integer, nullable=False,
                        default=0, server_default=text('0'))

    poll = relationship('WarRoomChatPoll', back_populates='options')
    votes = relationship('WarRoomChatPollVote',
                         back_populates='option',
                         cascade='all, delete-orphan')


class WarRoomChatPollVote(db.Model):
    """A single user's vote for a single option.

    Composite PK `(option_id, user_id)` — same user can NOT vote for
    the same option twice (idempotent toggle instead), but multi-select
    polls allow N rows per user across different options in the same
    poll. Single-select is enforced in the business layer by
    delete-existing-then-insert on vote.
    """
    __tablename__ = 'war_room_chat_poll_vote'

    option_id = Column(BigInteger,
                       ForeignKey('war_room_chat_poll_option.option_id',
                                  ondelete='CASCADE'),
                       primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('user.id', ondelete='CASCADE'),
                     primary_key=True, nullable=False)
    voted_at = Column(DateTime, nullable=False, server_default=text('now()'))

    option = relationship('WarRoomChatPollOption', back_populates='votes')
    user = relationship('User')


class WarRoomTask(db.Model):
    """Task tracked at the war-room level.

    Separate from `CaseTasks` because a war-room task can be cross-case
    (or non-case, e.g. "draft external comms statement"). When promoted
    from / linked to a case task the link goes in
    `source_case_task_id`.
    """
    __tablename__ = 'war_room_task'

    task_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status_id = Column(Integer, ForeignKey('task_status.id'), nullable=True)
    assignee_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    due_at = Column(DateTime, nullable=True)
    source_case_id = Column(BigInteger,
                            ForeignKey('cases.case_id', ondelete='SET NULL'),
                            nullable=True)
    source_case_task_id = Column(BigInteger,
                                 ForeignKey('case_tasks.id', ondelete='SET NULL'),
                                 nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    created_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    tags = Column(Text, nullable=True)
    custom_attributes = Column(JSONB, nullable=True)

    war_room = relationship('WarRoom')
    status = relationship('TaskStatus')
    assignee = relationship('User', foreign_keys=[assignee_id])
    created_by = relationship('User', foreign_keys=[created_by_id])
    closed_by = relationship('User', foreign_keys=[closed_by_id])
    source_case = relationship('Cases')


class WarRoomNoteFolder(db.Model):
    """Folder in a war-room notes tree.

    Self-referencing adjacency-list tree scoped to a single war room —
    same shape as `NoteDirectory` for case notes, but with the friendlier
    "folder" name (case-notes inherited "directory" from the legacy
    `notes_group` table; this is greenfield so we pick the term the UI
    actually uses).

    Deletion is CASCADE at the DB level for `war_room_id` and
    `parent_id`, but the business layer walks the subtree explicitly so
    it can also purge the child notes (whose `folder_id` FK has no
    cascade — see `WarRoomNote.folder_id` below).
    """
    __tablename__ = 'war_room_note_folder'

    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    parent_id = Column(BigInteger,
                       ForeignKey('war_room_note_folder.id', ondelete='CASCADE'),
                       nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    updated_at = Column(DateTime, nullable=False, server_default=text('now()'))

    parent = relationship('WarRoomNoteFolder',
                          remote_side=[id], backref='subfolders')
    war_room = relationship('WarRoom')


class WarRoomNote(db.Model):
    """Note pinned to a war room.

    Mirrors the per-case Notes pattern but scoped to a war room. Body is
    markdown — the collab markdown editor is wired in the frontend via
    the existing socket channel.
    """
    __tablename__ = 'war_room_note'

    note_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    # Nullable so root-level notes (no folder) are valid. No cascade —
    # `war_room_notes_db.delete_folder()` walks the subtree and deletes
    # child notes explicitly so revision history is torn down with them.
    folder_id = Column(BigInteger,
                       ForeignKey('war_room_note_folder.id'), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    updated_at = Column(DateTime, nullable=False, server_default=text('now()'))
    created_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    updated_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)

    war_room = relationship('WarRoom')
    folder = relationship('WarRoomNoteFolder', backref='notes')
    created_by = relationship('User', foreign_keys=[created_by_id])
    updated_by = relationship('User', foreign_keys=[updated_by_id])
    versions = relationship('WarRoomNoteRevision',
                            back_populates='note',
                            cascade='all, delete-orphan')


class WarRoomNoteRevision(db.Model):
    """Immutable snapshot of a war-room note.

    Written by the business layer on every content-changing update
    (dedup: skipped when title+content match the latest revision), plus
    once on create as revision #1. `restore_revision` snapshots the
    current state as a new revision before overwriting, so restore is
    itself undoable. Mirrors `NoteRevisions` for case notes.
    """
    __tablename__ = 'war_room_note_revision'

    revision_id = Column(BigInteger, primary_key=True)
    note_id = Column(BigInteger,
                     ForeignKey('war_room_note.note_id', ondelete='CASCADE'),
                     nullable=False, index=True)
    revision_number = Column(Integer, nullable=False)
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    revised_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    revised_at = Column(DateTime, nullable=False, server_default=text('now()'))

    note = relationship('WarRoomNote', back_populates='versions')
    revised_by = relationship('User', foreign_keys=[revised_by_id])


class WarRoomSitRep(db.Model):
    """Versioned situational report.

    Each row is an immutable-once-published snapshot. `snapshot_json`
    freezes the war-room context (attached cases, task counts, last
    activity) at the moment of publish so historical SitReps stay
    coherent even as the underlying state evolves.
    """
    __tablename__ = 'war_room_sitrep'
    __table_args__ = (
        UniqueConstraint('war_room_id', 'version', name='uq_war_room_sitrep_version'),
    )

    sitrep_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    version = Column(Integer, nullable=False)
    title = Column(Text, nullable=False)
    body_md = Column(Text, nullable=False)
    snapshot_json = Column(JSONB, nullable=True)
    authored_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    authored_at = Column(DateTime, nullable=False, server_default=text('now()'))
    published = Column(Boolean, nullable=False, default=False,
                       server_default=text('false'))

    war_room = relationship('WarRoom')
    authored_by = relationship('User')


class WarRoomDatastoreFile(db.Model):
    """File stored in the war-room datastore.

    The war room's "dedicated space" — files uploaded directly into the
    war room (after-action photos, exported SitReps, evidence bundles
    not yet attributable to a single case). Files attached at the
    war-room level live here; files belonging to a specific attached
    case still live in that case's existing datastore and are surfaced
    in the unified view as virtual rows joined from the cases.
    """
    __tablename__ = 'war_room_datastore_file'

    file_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    filename = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    storage_path = Column(Text, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(128), nullable=True)
    sha256 = Column(String(64), nullable=True)
    uploaded_at = Column(DateTime, nullable=False, server_default=text('now()'))
    uploaded_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    tags = Column(Text, nullable=True)

    war_room = relationship('WarRoom')
    uploaded_by = relationship('User')
