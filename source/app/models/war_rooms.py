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
from sqlalchemy import Float
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
    custom_attributes = Column(JSONB, nullable=True)

    created_by = relationship('User', foreign_keys=[created_by_id])
    closed_by = relationship('User', foreign_keys=[closed_by_id])
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
    timeline_id = Column(BigInteger,
                         ForeignKey('war_room_timeline.timeline_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    case_id = Column(BigInteger,
                     ForeignKey('cases.case_id', ondelete='SET NULL'),
                     nullable=True)
    event_id = Column(BigInteger,
                      ForeignKey('cases_events.event_id', ondelete='CASCADE'),
                      nullable=True)
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    event_date = Column(DateTime, nullable=True)
    event_tz = Column(String(16), nullable=True)
    color = Column(String(7), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    created_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)

    timeline = relationship('WarRoomTimeline')
    case = relationship('Cases')
    event = relationship('CasesEvent')
    created_by = relationship('User')


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
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    edited_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    war_room = relationship('WarRoom')
    author = relationship('User')


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
    created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    updated_at = Column(DateTime, nullable=False, server_default=text('now()'))
    created_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)
    updated_by_id = Column(BigInteger, ForeignKey('user.id'), nullable=True)

    war_room = relationship('WarRoom')
    created_by = relationship('User', foreign_keys=[created_by_id])
    updated_by = relationship('User', foreign_keys=[updated_by_id])


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


class WarRoomGraphNode(db.Model):
    """One node on the war-room cases-as-graph board.

    `kind` is `case` when the node represents an attached case, or
    `annotation` for free-floating notes/anchors the operator dropped on
    the canvas. `ref_id` points at the case when applicable.
    """
    __tablename__ = 'war_room_graph_node'

    node_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    kind = Column(String(16), nullable=False)
    ref_id = Column(BigInteger, nullable=True)
    label = Column(Text, nullable=True)
    note_md = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)
    x = Column(Float, nullable=False, server_default=text('0'))
    y = Column(Float, nullable=False, server_default=text('0'))


class WarRoomGraphEdge(db.Model):
    __tablename__ = 'war_room_graph_edge'

    edge_id = Column(BigInteger, primary_key=True)
    war_room_id = Column(BigInteger,
                         ForeignKey('war_room.war_room_id', ondelete='CASCADE'),
                         nullable=False, index=True)
    from_node_id = Column(BigInteger,
                          ForeignKey('war_room_graph_node.node_id', ondelete='CASCADE'),
                          nullable=False)
    to_node_id = Column(BigInteger,
                        ForeignKey('war_room_graph_node.node_id', ondelete='CASCADE'),
                        nullable=False)
    label = Column(Text, nullable=True)
    note_md = Column(Text, nullable=True)
    style = Column(String(16), nullable=True)


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
