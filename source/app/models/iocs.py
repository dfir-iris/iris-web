#  IRIS Source Code
#  Copyright (C) ${current_year} - DFIR-IRIS
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

from app.db import db

from sqlalchemy import Table
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import String
from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text
from sqlalchemy.orm import relationship


alert_iocs_association = Table(
    'alert_iocs_association',
    db.Model.metadata,
    Column('alert_id', ForeignKey('alerts.alert_id'), primary_key=True),
    Column('ioc_id', ForeignKey('ioc.ioc_id'), primary_key=True)
)


class Tlp(db.Model):
    __tablename__ = 'tlp'

    tlp_id = Column(Integer, primary_key=True)
    tlp_name = Column(Text)
    tlp_bscolor = Column(Text)


class Ioc(db.Model):
    __tablename__ = 'ioc'

    ioc_id = Column(BigInteger, primary_key=True)
    ioc_uuid = Column(UUID(as_uuid=True), server_default=text('gen_random_uuid()'), nullable=False)
    ioc_value = Column(Text)
    ioc_type_id = Column(ForeignKey('ioc_type.type_id'))
    ioc_description = Column(Text)
    ioc_tags = Column(String(512))
    user_id = Column(ForeignKey('user.id'))
    ioc_misp = Column(Text)
    ioc_tlp_id = Column(ForeignKey('tlp.tlp_id'))
    custom_attributes = Column(JSON)
    ioc_enrichment = Column(JSONB)
    modification_history = Column(JSON)

    case_id = Column(ForeignKey('cases.case_id'), nullable=True)

    user = relationship('User')
    tlp = relationship('Tlp')
    ioc_type = relationship('IocType')
    case = relationship('Cases')
    assets = relationship('IocAssetLink', back_populates='ioc', cascade='delete')
    events = relationship('CaseEventsIoc', back_populates='ioc', cascade='delete')
    comments = relationship('IocComments', back_populates='ioc', cascade='all, delete')
    alerts = relationship('Alert', secondary=alert_iocs_association, back_populates='iocs')
