#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
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

from sqlalchemy import BigInteger
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import db


class IncidentStatus(db.Model):
    __tablename__ = 'incident_status'

    status_id = Column(Integer, primary_key=True)
    status_name = Column(Text, nullable=False, unique=True)
    status_description = Column(Text)


class AlertIncidentAssociation(db.Model):
    __tablename__ = 'alert_incident_association'

    alert_id = Column(ForeignKey('alerts.alert_id'), primary_key=True, nullable=False)
    incident_id = Column(ForeignKey('incidents.incident_id'), primary_key=True, nullable=False, index=True)


class Incident(db.Model):
    __tablename__ = 'incidents'

    incident_id = Column(BigInteger, primary_key=True)
    incident_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                           server_default=text('gen_random_uuid()'), unique=True)
    incident_title = Column(Text, nullable=False)
    incident_description = Column(Text)
    incident_status_id = Column(ForeignKey('incident_status.status_id'), nullable=False)
    incident_severity_id = Column(ForeignKey('severities.severity_id'), nullable=True)
    incident_customer_id = Column(ForeignKey('client.client_id'), nullable=False)
    incident_owner_id = Column(ForeignKey('user.id'), nullable=True)
    incident_creation_time = Column(DateTime, nullable=False, server_default=text('now()'))
    incident_source_rule_id = Column(ForeignKey('incident_rules.rule_id'), nullable=True)
    incident_case_id = Column(ForeignKey('cases.case_id'), nullable=True)
    # Stacking dedupe key computed from the rule that opened the incident.
    # Rows sharing this key inside the rule's time window are merged into
    # the same open incident. Left free-text so different rules can key
    # by whatever fields they group_by.
    incident_dedupe_key = Column(Text, nullable=True, index=True)
    # Cached investigation-flow attachment — mirrors the alert-side FK.
    # Set by the flow evaluator when a flow's conditions match this
    # incident, so the detail page doesn't re-evaluate every render.
    incident_investigation_flow_id = Column(
        ForeignKey('investigation_flows.flow_id'), nullable=True
    )
    modification_history = Column(JSON)

    status = relationship('IncidentStatus')
    severity = relationship('Severity')
    customer = relationship('Client')
    owner = relationship('User', foreign_keys=[incident_owner_id])
    source_rule = relationship('IncidentRule', foreign_keys=[incident_source_rule_id])
    case = relationship('Cases', foreign_keys=[incident_case_id])
    investigation_flow = relationship(
        'InvestigationFlow', foreign_keys=[incident_investigation_flow_id]
    )

    alerts = relationship('Alert', secondary='alert_incident_association', back_populates='incidents')
