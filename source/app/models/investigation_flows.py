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
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import db


# `flow_target` values — a flow declares whether it applies to alerts,
# alert clusters, or both. Rules used to decide flow attachment; that was
# consolidated into the flow itself so there's one place to look for
# "when does this flow apply".
FLOW_TARGET_ALERT = 'alert'
FLOW_TARGET_CLUSTER = 'alert_cluster'
FLOW_TARGET_BOTH = 'both'
FLOW_TARGETS = (FLOW_TARGET_ALERT, FLOW_TARGET_CLUSTER, FLOW_TARGET_BOTH)


class InvestigationFlow(db.Model):
    __tablename__ = 'investigation_flows'

    flow_id = Column(BigInteger, primary_key=True)
    flow_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                       server_default=text('gen_random_uuid()'), unique=True)
    flow_name = Column(Text, nullable=False)
    flow_description = Column(Text)
    flow_is_active = Column(Boolean, nullable=False, default=True, server_default=text('true'))
    # null → all customers; otherwise list of client_id ints
    flow_customer_scope = Column(JSONB, nullable=True)
    # Which entities this flow can attach to: 'alert' / 'alert_cluster' / 'both'.
    # See FLOW_TARGET_* constants.
    flow_target = Column(Text, nullable=False,
                         server_default=text("'alert'"), default=FLOW_TARGET_ALERT)
    # Match conditions — same DSL shape as `ClusterRule.rule_conditions`
    # (`{"logic": "and", "conditions": [{field, operator, value}, ...]}`)
    # evaluated by `app.datamgmt.filtering.apply_custom_conditions`.
    # A flow with an empty condition list never auto-attaches; use
    # /deploy against manual selection or wait for a rule to expand.
    flow_conditions = Column(JSONB, nullable=False, server_default=text("'{\"logic\":\"and\",\"conditions\":[]}'::jsonb"))
    # Priority for tie-breaking when multiple flows match the same entity;
    # lower = higher priority, matching the cluster-rules convention.
    flow_priority = Column(Integer, nullable=False, default=100, server_default=text('100'))
    flow_created_by = Column(ForeignKey('user.id'), nullable=True)
    flow_created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    flow_updated_at = Column(DateTime, nullable=False, server_default=text('now()'))

    creator = relationship('User', foreign_keys=[flow_created_by])
    steps = relationship(
        'InvestigationFlowStep',
        back_populates='flow',
        cascade='all, delete-orphan',
        order_by='InvestigationFlowStep.step_order'
    )


class InvestigationFlowStep(db.Model):
    __tablename__ = 'investigation_flow_steps'

    step_id = Column(BigInteger, primary_key=True)
    flow_id = Column(ForeignKey('investigation_flows.flow_id', ondelete='CASCADE'), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    step_title = Column(Text, nullable=False)
    step_description = Column(Text)
    step_is_required = Column(Boolean, nullable=False, default=False, server_default=text('false'))

    flow = relationship('InvestigationFlow', back_populates='steps')


class AlertInvestigationProgress(db.Model):
    __tablename__ = 'alert_investigation_progress'
    __table_args__ = (
        UniqueConstraint('alert_id', 'step_id', name='uq_alert_investigation_progress_alert_step'),
    )

    id = Column(BigInteger, primary_key=True)
    alert_id = Column(ForeignKey('alerts.alert_id', ondelete='CASCADE'), nullable=False, index=True)
    step_id = Column(ForeignKey('investigation_flow_steps.step_id', ondelete='CASCADE'), nullable=False)
    completed_by_user_id = Column(ForeignKey('user.id'), nullable=False)
    completed_at = Column(DateTime, nullable=False, server_default=text('now()'))
    note = Column(Text)

    alert = relationship('Alert')
    step = relationship('InvestigationFlowStep')
    completed_by = relationship('User', foreign_keys=[completed_by_user_id])


class AlertClusterInvestigationProgress(db.Model):
    """Per-cluster, per-step check-off. Mirrors AlertInvestigationProgress
    but scoped to an alert cluster so the cluster-level checklist is fully
    independent of any member alert's checklist — an analyst working the
    cluster as a whole may cover steps that no single alert has yet."""
    __tablename__ = 'alert_cluster_investigation_progress'
    __table_args__ = (
        UniqueConstraint('cluster_id', 'step_id',
                         name='uq_alert_cluster_investigation_progress_cluster_step'),
    )

    id = Column(BigInteger, primary_key=True)
    cluster_id = Column(ForeignKey('alert_clusters.cluster_id', ondelete='CASCADE'),
                        nullable=False, index=True)
    step_id = Column(ForeignKey('investigation_flow_steps.step_id', ondelete='CASCADE'),
                     nullable=False)
    completed_by_user_id = Column(ForeignKey('user.id'), nullable=False)
    completed_at = Column(DateTime, nullable=False, server_default=text('now()'))
    note = Column(Text)

    cluster = relationship('AlertCluster')
    step = relationship('InvestigationFlowStep')
    completed_by = relationship('User', foreign_keys=[completed_by_user_id])
