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
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import db


RULE_ACTION_CREATE_CLUSTER = 'create_cluster'

# The `attach_flow` action was removed — investigation flows now own
# their own matching conditions (`InvestigationFlow.flow_conditions`),
# so there's a single source of truth for "when does this flow apply".
# Kept the constant name here would be misleading; anyone importing it
# should switch to reading `InvestigationFlow.flow_conditions` instead.


class ClusterRule(db.Model):
    __tablename__ = 'cluster_rules'

    rule_id = Column(BigInteger, primary_key=True)
    rule_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                       server_default=text('gen_random_uuid()'), unique=True)
    rule_name = Column(Text, nullable=False)
    rule_description = Column(Text)
    rule_is_active = Column(Boolean, nullable=False, default=True, server_default=text('true'))
    rule_priority = Column(Integer, nullable=False, default=100, server_default=text('100'))
    # null → all customers; otherwise list of client_id ints
    rule_customer_scope = Column(JSONB, nullable=True)
    rule_conditions = Column(JSONB, nullable=False)
    rule_action_type = Column(Text, nullable=False)
    rule_action_config = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    rule_created_by = Column(ForeignKey('user.id'), nullable=True)
    rule_created_at = Column(DateTime, nullable=False, server_default=text('now()'))
    rule_updated_at = Column(DateTime, nullable=False, server_default=text('now()'))

    creator = relationship('User', foreign_keys=[rule_created_by])
