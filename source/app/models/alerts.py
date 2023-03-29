import uuid
from psycopg2.extensions import JSON
from sqlalchemy import BigInteger, Table
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app import db
from app.models import Base

alert_case_association = Table('alert_case_association', Base.metadata,
                               Column('alert_id', BigInteger, ForeignKey('alerts.alert_id'), primary_key=True),
                               Column('case_id', BigInteger, ForeignKey('cases.case_id'), primary_key=True)
                               )


class Alert(db.Model):
    __tablename__ = 'alerts'

    alert_id = Column(BigInteger, primary_key=True)
    alert_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                        server_default=text('gen_random_uuid()'), unique=True)
    alert_title = Column(Text, nullable=False)
    alert_description = Column(Text)
    alert_source = Column(Text)
    alert_source_ref = Column(Text)
    alert_source_link = Column(Text)
    alert_source_content = Column(JSON)
    alert_severity = Column(ForeignKey('alert_severity.severity_id'), nullable=False)
    alert_status = Column(ForeignKey('alert_status.status_id'), nullable=False)
    alert_display_content = Column(JSON)
    alert_context = Column(JSON)
    alert_source_event_time = Column(DateTime, nullable=False, server_default=text("now()"))
    alert_creation_time = Column(DateTime, nullable=False, server_default=text("now()"))
    alert_note = Column(Text)
    alert_tags = Column(Text)
    alert_owner_id = Column(ForeignKey('user.id'))
    modification_history = Column(JSON)
    alert_iocs = Column(JSON)
    alert_assets = Column(JSON)

    user = relationship('User', foreign_keys=[alert_owner_id])
    severity = relationship('AlertSeverity')
    status = relationship('AlertStatus')

    cases = relationship('Cases', secondary=alert_case_association, back_populates='alerts')


class AlertSeverity(db.Model):
    __tablename__ = 'alert_severity'

    severity_id = Column(Integer, primary_key=True)
    severity_name = Column(Text, nullable=False, unique=True)
    severity_description = Column(Text)


class AlertStatus(db.Model):
    __tablename__ = 'alert_status'

    status_id = Column(Integer, primary_key=True)
    status_name = Column(Text, nullable=False, unique=True)
    status_description = Column(Text)



