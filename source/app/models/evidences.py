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
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import DateTime
from sqlalchemy import func
from sqlalchemy import ForeignKey
from sqlalchemy import BigInteger
from sqlalchemy import UUID
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship

from app import db


class EvidenceTypes(db.Model):
    __tablename__ = 'evidence_type'

    id = Column(Integer, primary_key=True)
    name = Column(Text)
    description = Column(Text)
    creation_date = Column(DateTime, server_default=func.now(), nullable=True)
    created_by_id = Column(ForeignKey('user.id'), nullable=True)

    created_by = relationship('User')


class CaseReceivedFile(db.Model):
    __tablename__ = 'case_received_file'

    id = Column(BigInteger, primary_key=True)
    file_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"), nullable=False)
    filename = Column(Text)
    date_added = Column(DateTime)
    acquisition_date = Column(DateTime)
    file_hash = Column(Text)
    file_description = Column(Text)
    file_size = Column(BigInteger)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    case_id = Column(ForeignKey('cases.case_id'))
    user_id = Column(ForeignKey('user.id'))
    type_id = Column(ForeignKey('evidence_type.id'))
    custom_attributes = Column(JSON)
    chain_of_custody = Column(JSON)
    modification_history = Column(JSON)

    case = relationship('Cases')
    user = relationship('User')
    type = relationship('EvidenceTypes')
