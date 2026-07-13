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

from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import db


class CustomDashboard(db.Model):
    __tablename__ = 'custom_dashboard'

    id = Column(Integer, primary_key=True)
    dashboard_uuid = Column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(ForeignKey('user.id'), nullable=True)
    is_shared = Column(Boolean, nullable=False, server_default=text("false"))
    is_system = Column(Boolean, nullable=False, server_default=text("false"))
    definition = Column(JSONB, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    owner = relationship('User')
    widgets = relationship('CustomDashboardWidget', back_populates='dashboard', cascade='all, delete-orphan')


class CustomDashboardWidget(db.Model):
    __tablename__ = 'custom_dashboard_widget'

    id = Column(Integer, primary_key=True)
    widget_uuid = Column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"), nullable=False, unique=True)
    dashboard_id = Column(ForeignKey('custom_dashboard.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    chart_type = Column(String(64), nullable=False)
    definition = Column(JSONB, nullable=False)
    position = Column(Integer, nullable=False, server_default=text("0"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    dashboard = relationship('CustomDashboard', back_populates='widgets')
