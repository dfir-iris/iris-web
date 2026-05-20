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

import uuid

from sqlalchemy import Column
from sqlalchemy import BigInteger
from sqlalchemy import UUID
from sqlalchemy import text
from sqlalchemy import Text
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.db import db


class Comments(db.Model):
    __tablename__ = "comments"

    comment_id = Column(BigInteger, primary_key=True)
    comment_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"),
                          nullable=False)
    comment_text = Column(Text)
    comment_date = Column(DateTime)
    comment_update_date = Column(DateTime)
    comment_user_id = Column(ForeignKey('user.id'))
    comment_case_id = Column(ForeignKey('cases.case_id'))
    comment_alert_id = Column(ForeignKey('alerts.alert_id'))

    user = relationship('User')
    case = relationship('Cases')
    alert = relationship('Alert')


class EventComments(db.Model):
    __tablename__ = "event_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_event_id = Column(ForeignKey('cases_events.event_id'))

    event = relationship('CasesEvent')
    comment = relationship('Comments')


class TaskComments(db.Model):
    __tablename__ = "task_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_task_id = Column(ForeignKey('case_tasks.id'))

    task = relationship('CaseTasks')
    comment = relationship('Comments')


class IocComments(db.Model):
    __tablename__ = "ioc_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_ioc_id = Column(ForeignKey('ioc.ioc_id'))

    ioc = relationship('Ioc')
    comment = relationship('Comments')


class AssetComments(db.Model):
    __tablename__ = "asset_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_asset_id = Column(ForeignKey('case_assets.asset_id'))

    asset = relationship('CaseAssets')
    comment = relationship('Comments')


class EvidencesComments(db.Model):
    __tablename__ = "evidence_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_evidence_id = Column(ForeignKey('case_received_file.id'))

    evidence = relationship('CaseReceivedFile')
    comment = relationship('Comments')


class NotesComments(db.Model):
    __tablename__ = "note_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_note_id = Column(ForeignKey('notes.note_id'))

    note = relationship('Notes')
    comment = relationship('Comments')
