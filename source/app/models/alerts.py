from datetime import datetime

import uuid
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy import BigInteger, Table, Boolean, String
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, backref

from app import db
from app.models import Base, alert_assets_association, alert_iocs_association
from app.models.cases import Cases


class AlertCaseAssociation(db.Model):
    __tablename__ = 'alert_case_association'

    alert_id = Column(ForeignKey('alerts.alert_id'), primary_key=True, nullable=False)
    case_id = Column(ForeignKey('cases.case_id'), primary_key=True, nullable=False, index=True)


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
    alert_severity_id = Column(ForeignKey('severities.severity_id'), nullable=False)
    alert_status_id = Column(ForeignKey('alert_status.status_id'), nullable=False)
    alert_context = Column(JSON)
    alert_source_event_time = Column(DateTime, nullable=False, server_default=text("now()"))
    alert_creation_time = Column(DateTime, nullable=False, server_default=text("now()"))
    alert_note = Column(Text)
    alert_tags = Column(Text)
    alert_owner_id = Column(ForeignKey('user.id'))
    modification_history = Column(JSON)
    alert_customer_id = Column(ForeignKey('client.client_id'), nullable=False)
    alert_classification_id = Column(ForeignKey('case_classification.id'))
    alert_resolution_status_id = Column(ForeignKey('alert_resolution_status.resolution_status_id'), nullable=True)

    owner = relationship('User', foreign_keys=[alert_owner_id])
    severity = relationship('Severity')
    status = relationship('AlertStatus')
    customer = relationship('Client')
    classification = relationship('CaseClassification')
    resolution_status = relationship('AlertResolutionStatus')

    cases = relationship('Cases', secondary="alert_case_association", back_populates='alerts')
    comments = relationship('Comments', back_populates='alert', cascade='all, delete-orphan')

    assets = relationship('CaseAssets', secondary=alert_assets_association, back_populates='alerts')
    iocs = relationship('Ioc', secondary=alert_iocs_association, back_populates='alerts')


class Severity(db.Model):
    __tablename__ = 'severities'

    severity_id = Column(Integer, primary_key=True)
    severity_name = Column(Text, nullable=False, unique=True)
    severity_description = Column(Text)


class AlertStatus(db.Model):
    __tablename__ = 'alert_status'

    status_id = Column(Integer, primary_key=True)
    status_name = Column(Text, nullable=False, unique=True)
    status_description = Column(Text)


class AlertResolutionStatus(db.Model):
    __tablename__ = 'alert_resolution_status'

    resolution_status_id = Column(Integer, primary_key=True)
    resolution_status_name = Column(Text, nullable=False, unique=True)
    resolution_status_description = Column(Text)


class SimilarAlertsCache(db.Model):
    __tablename__ = 'similar_alerts_cache'

    id = Column(BigInteger, primary_key=True)
    customer_id = Column(BigInteger, ForeignKey('client.client_id'), nullable=False)
    asset_name = Column(Text, nullable=True)
    ioc_value = Column(Text, nullable=True)
    alert_id = Column(BigInteger, ForeignKey('alerts.alert_id'), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))

    asset_type_id = Column(Integer, ForeignKey('assets_type.asset_id'), nullable=True)
    ioc_type_id = Column(Integer, ForeignKey('ioc_type.type_id'), nullable=True)

    alert = relationship('Alert')
    customer = relationship('Client')
    asset_type = relationship('AssetsType')
    ioc_type = relationship('IocType')

    def __init__(self, customer_id, alert_id, asset_name=None, ioc_value=None, asset_type_id=None, ioc_type_id=None,
                 created_at=None):
        self.customer_id = customer_id
        self.asset_name = asset_name
        self.ioc_value = ioc_value
        self.alert_id = alert_id
        self.asset_type_id = asset_type_id
        self.ioc_type_id = ioc_type_id
        self.created_at = created_at if created_at else datetime.utcnow()


class AlertSimilarity(db.Model):
    __tablename__ = 'alert_similarity'

    id = Column(BigInteger, primary_key=True)
    alert_id = Column(BigInteger, ForeignKey('alerts.alert_id'), nullable=False)
    similar_alert_id = Column(BigInteger, ForeignKey('alerts.alert_id'), nullable=False)
    similarity_type = Column(String(255), nullable=True)
    matching_asset_id = Column(BigInteger, ForeignKey('case_assets.asset_id'), nullable=True)
    matching_ioc_id = Column(BigInteger, ForeignKey('ioc.ioc_id'), nullable=True)

    alert = relationship("Alert", foreign_keys=[alert_id])
    similar_alert = relationship("Alert", foreign_keys=[similar_alert_id])
    matching_asset = relationship("CaseAssets")
    matching_ioc = relationship("Ioc")
