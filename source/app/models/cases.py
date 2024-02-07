#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

from datetime import datetime
from flask_login import current_user
# IMPORTS ------------------------------------------------
from sqlalchemy import BigInteger, Table, CheckConstraint
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref

from app import db
from app.datamgmt.states import update_assets_state
from app.datamgmt.states import update_evidences_state
from app.datamgmt.states import update_ioc_state
from app.datamgmt.states import update_notes_state
from app.datamgmt.states import update_tasks_state
from app.datamgmt.states import update_timeline_state
from app.models.models import Client, Base


class Cases(db.Model):
    __tablename__ = 'cases'

    case_id = Column(BigInteger, primary_key=True)
    soc_id = Column(String(256))
    client_id = Column(ForeignKey('client.client_id'), nullable=False)
    name = Column(String(256))
    description = Column(Text)
    open_date = Column(Date)
    close_date = Column(Date)
    initial_date = Column(DateTime, nullable=False, server_default=text("now()"))
    closing_note = Column(Text)
    user_id = Column(ForeignKey('user.id'))
    owner_id = Column(ForeignKey('user.id'))
    status_id = Column(Integer, nullable=False, server_default=text("0"))
    state_id = Column(ForeignKey('case_state.state_id'), nullable=True)
    custom_attributes = Column(JSON)
    case_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"),
                       nullable=False)
    classification_id = Column(ForeignKey('case_classification.id'))
    reviewer_id = Column(ForeignKey('user.id'), nullable=True)
    review_status_id = Column(ForeignKey('review_status.id'), nullable=True)
    severity_id = Column(ForeignKey('severities.severity_id'), nullable=True)

    modification_history = Column(JSON)

    client = relationship('Client')
    user = relationship('User', foreign_keys=[user_id])
    owner = relationship('User', foreign_keys=[owner_id])
    classification = relationship('CaseClassification')
    reviewer = relationship('User', foreign_keys=[reviewer_id])
    severity = relationship('Severity')

    alerts = relationship('Alert', secondary="alert_case_association", back_populates='cases', viewonly=True)

    tags = relationship('Tags', secondary="case_tags", back_populates='cases')
    state = relationship('CaseState', back_populates='cases')

    review_status = relationship('ReviewStatus')

    def __init__(self,
                 name=None,
                 soc_id=None,
                 client_id=None,
                 description=None,
                 user=None,
                 custom_attributes=None,
                 classification_id=None,
                 state_id=None
                 ):
        self.name = name[:200] if name else None,
        self.soc_id = soc_id,
        self.client_id = client_id,
        self.description = description,
        self.user_id = current_user.id if current_user else user.id
        self.owner_id = self.user_id
        self.author = current_user.user if current_user else user.user
        self.description = description
        self.open_date = datetime.utcnow()
        self.close_date = None
        self.initial_date = datetime.utcnow()
        self.custom_attributes = custom_attributes
        self.case_uuid = uuid.uuid4()
        self.status_id = 0
        self.classification_id = classification_id
        self.state_id = state_id

    def save(self):
        """
        Save the current case in database
        :return:
        """
        # Inject self into db
        db.session.add(self)

        # Commit the changes
        db.session.commit()

        # Rename case with the ID
        self.name = "#{id} - {name}".format(id=self.case_id, name=self.name)

        # Create the states
        update_timeline_state(caseid=self.case_id, userid=self.user_id)
        update_tasks_state(caseid=self.case_id, userid=self.user_id)
        update_evidences_state(caseid=self.case_id, userid=self.user_id)
        update_ioc_state(caseid=self.case_id, userid=self.user_id)
        update_assets_state(caseid=self.case_id, userid=self.user_id)
        update_notes_state(caseid=self.case_id, userid=self.user_id)

        db.session.commit()

        return self

    def validate_on_build(self):
        """
        Execute an autocheck of the case metadata and validate it
        :return: True if valid else false; Tuple with errors
        """
        # TODO : Check if case name already exists

        res = Client.query\
            .with_entities(Client.client_id)\
            .filter(Client.client_id == self.client_id)\
            .first()

        self.client_id = res[0]

        return True, []


class CaseTags(db.Model):
    __tablename__ = 'case_tags'
    __table_args__ = (
        UniqueConstraint('case_id', 'tag_id', name='case_tags_case_id_tag_id_key'),
    )

    case_id = Column(ForeignKey('cases.case_id'), primary_key=True, nullable=False)
    tag_id = Column(ForeignKey('tags.id'), primary_key=True, nullable=False, index=True)


class CasesEvent(db.Model):
    __tablename__ = "cases_events"

    event_id = Column(BigInteger, primary_key=True)
    parent_event_id = Column(BigInteger, ForeignKey('cases_events.event_id'), nullable=True)
    event_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"),
                        nullable=False)
    case_id = Column(ForeignKey('cases.case_id'))
    event_title = Column(Text)
    event_source = Column(Text)
    event_content = Column(Text)
    event_raw = Column(Text)
    event_date = Column(DateTime)
    event_added = Column(DateTime)
    event_in_graph = Column(Boolean)
    event_in_summary = Column(Boolean)
    user_id = Column(ForeignKey('user.id'))
    modification_history = Column(JSONB)
    event_color = Column(Text)
    event_tags = Column(Text)
    event_tz = Column(Text)
    event_date_wtz = Column(DateTime)
    event_is_flagged = Column(Boolean, default=False)
    custom_attributes = Column(JSONB)

    case = relationship('Cases')
    user = relationship('User')
    category = relationship('EventCategory', secondary="case_events_category",
                            primaryjoin="CasesEvent.event_id==CaseEventCategory.event_id",
                            secondaryjoin="CaseEventCategory.category_id==EventCategory.id",
                            viewonly=True)
    children = relationship("CasesEvent", backref=backref('parent', remote_side=[event_id]))

    __table_args__ = (
        CheckConstraint('event_id != parent_event_id', name='check_different_ids'),
    )


class CaseState(db.Model):
    __tablename__ = 'case_state'

    state_id = Column(Integer, primary_key=True)
    state_name = Column(Text, nullable=False)
    state_description = Column(Text)
    protected = Column(Boolean, default=False)

    cases = relationship('Cases', back_populates='state')


class CaseProtagonist(db.Model):
    __tablename__ = "case_protagonist"

    id = Column(Integer, primary_key=True)
    case_id = Column(ForeignKey('cases.case_id'))
    user_id = Column(ForeignKey('user.id'))
    name = Column(Text)
    contact = Column(Text)
    role = Column(Text)

    case = relationship('Cases')
    user = relationship('User')
