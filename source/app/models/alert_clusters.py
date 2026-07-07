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


class AlertClusterStatus(db.Model):
    __tablename__ = 'alert_cluster_status'

    status_id = Column(Integer, primary_key=True)
    status_name = Column(Text, nullable=False, unique=True)
    status_description = Column(Text)


class AlertClusterAssociation(db.Model):
    __tablename__ = 'alert_cluster_association'

    alert_id = Column(ForeignKey('alerts.alert_id'), primary_key=True, nullable=False)
    cluster_id = Column(ForeignKey('alert_clusters.cluster_id'), primary_key=True, nullable=False, index=True)


class AlertCluster(db.Model):
    __tablename__ = 'alert_clusters'

    cluster_id = Column(BigInteger, primary_key=True)
    cluster_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                          server_default=text('gen_random_uuid()'), unique=True)
    cluster_title = Column(Text, nullable=False)
    cluster_description = Column(Text)
    cluster_status_id = Column(ForeignKey('alert_cluster_status.status_id'), nullable=False)
    cluster_severity_id = Column(ForeignKey('severities.severity_id'), nullable=True)
    cluster_customer_id = Column(ForeignKey('client.client_id'), nullable=False)
    cluster_owner_id = Column(ForeignKey('user.id'), nullable=True)
    cluster_creation_time = Column(DateTime, nullable=False, server_default=text('now()'))
    cluster_source_rule_id = Column(ForeignKey('cluster_rules.rule_id'), nullable=True)
    cluster_case_id = Column(ForeignKey('cases.case_id'), nullable=True)
    # Stacking dedupe key computed from the rule that opened the cluster.
    # Rows sharing this key inside the rule's time window are merged into
    # the same open cluster. Left free-text so different rules can key
    # by whatever fields they group_by.
    cluster_dedupe_key = Column(Text, nullable=True, index=True)
    # Cached investigation-flow attachment — mirrors the alert-side FK.
    # Set by the flow evaluator when a flow's conditions match this
    # cluster, so the detail page doesn't re-evaluate every render.
    cluster_investigation_flow_id = Column(
        ForeignKey('investigation_flows.flow_id'), nullable=True
    )
    modification_history = Column(JSON)

    status = relationship('AlertClusterStatus')
    severity = relationship('Severity')
    customer = relationship('Client')
    owner = relationship('User', foreign_keys=[cluster_owner_id])
    source_rule = relationship('ClusterRule', foreign_keys=[cluster_source_rule_id])
    case = relationship('Cases', foreign_keys=[cluster_case_id])
    investigation_flow = relationship(
        'InvestigationFlow', foreign_keys=[cluster_investigation_flow_id]
    )

    alerts = relationship('Alert', secondary='alert_cluster_association', back_populates='clusters')
