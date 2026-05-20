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

import enum

from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import ForeignKey
from sqlalchemy import BigInteger
from sqlalchemy import UUID
from sqlalchemy import text
from sqlalchemy import Text
from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import db


class CompromiseStatus(enum.Enum):
    to_be_determined = 0x0
    compromised = 0x1
    not_compromised = 0x2
    unknown = 0x3

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class AssetsType(db.Model):
    __tablename__ = 'assets_type'

    asset_id = Column(Integer, primary_key=True)
    asset_name = Column(String(155))
    asset_description = Column(String(255))
    asset_icon_not_compromised = Column(String(255))
    asset_icon_compromised = Column(String(255))


alert_assets_association = Table(
    'alert_assets_association',
    db.Model.metadata,
    Column('alert_id', ForeignKey('alerts.alert_id'), primary_key=True),
    Column('asset_id', ForeignKey('case_assets.asset_id'), primary_key=True)
)


class CaseAssets(db.Model):
    __tablename__ = 'case_assets'

    asset_id = Column(BigInteger, primary_key=True)
    asset_uuid = Column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"), nullable=False)
    asset_name = Column(Text)
    asset_description = Column(Text)
    asset_domain = Column(Text)
    asset_ip = Column(Text)
    asset_info = Column(Text)
    asset_compromise_status_id = Column(Integer, nullable=True)
    asset_type_id = Column(ForeignKey('assets_type.asset_id'))
    asset_tags = Column(Text)
    case_id = Column(ForeignKey('cases.case_id'))
    date_added = Column(DateTime)
    date_update = Column(DateTime)
    user_id = Column(ForeignKey('user.id'))
    analysis_status_id = Column(ForeignKey('analysis_status.id'))
    custom_attributes = Column(JSON)
    asset_enrichment = Column(JSONB)
    modification_history = Column(JSON)

    case = relationship('Cases')
    user = relationship('User')
    asset_type = relationship('AssetsType')
    analysis_status = relationship('AnalysisStatus')

    alerts = relationship('Alert', secondary=alert_assets_association, back_populates='assets')
    iocs = relationship('IocAssetLink', back_populates='asset')


class AnalysisStatus(db.Model):
    __tablename__ = 'analysis_status'

    id = Column(Integer, primary_key=True)
    name = Column(Text)
