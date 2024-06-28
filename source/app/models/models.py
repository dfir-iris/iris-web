#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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
import datetime

# IMPORTS ------------------------------------------------
import enum
import uuid

from sqlalchemy import BigInteger, UniqueConstraint, Table
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import LargeBinary
from sqlalchemy import Sequence
from sqlalchemy import String
from sqlalchemy import TIMESTAMP
from sqlalchemy import Text
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

from app import app
from app import db

Base = declarative_base()
metadata = Base.metadata


class CaseStatus(enum.Enum):
    unknown = 0x0
    false_positive = 0x1
    true_positive_with_impact = 0x2
    not_applicable = 0x3
    true_positive_without_impact = 0x4
    legitimate = 0x5


class ReviewStatusList:
    no_review_required = "No review required"
    not_reviewed = "Not reviewed"
    pending_review = "Pending review"
    review_in_progress = "Review in progress"
    reviewed = "Reviewed"


class CompromiseStatus(enum.Enum):
    to_be_determined = 0x0
    compromised = 0x1
    not_compromised = 0x2
    unknown = 0x3

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


def create_safe(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return False
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return True


def create_safe_limited(session, model, keywords_list, **kwargs):
    kwdup = kwargs.keys()
    for kw in list(kwdup):
        if kw not in keywords_list:
            kwargs.pop(kw)

    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return False
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return True


def get_by_value_or_create(session, model, fieldname, **kwargs):
    select_value = {fieldname: kwargs.get(fieldname)}
    instance = session.query(model).filter_by(**select_value).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance


def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance


# CONTENT ------------------------------------------------
class Client(db.Model):
    __tablename__ = 'client'

    client_id = Column(BigInteger, primary_key=True)
    client_uuid = Column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"), nullable=False)
    name = Column(Text, unique=True)
    description = Column(Text)
    sla = Column(Text)
    creation_date = Column(DateTime, server_default=func.now(), nullable=True)
    created_by = Column(ForeignKey('user.id'), nullable=True)
    last_update_date = Column(DateTime, server_default=func.now(), nullable=True)

    custom_attributes = Column(JSON)


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


alert_iocs_association = Table(
    'alert_iocs_association',
    db.Model.metadata,
    Column('alert_id', ForeignKey('alerts.alert_id'), primary_key=True),
    Column('ioc_id', ForeignKey('ioc.ioc_id'), primary_key=True)
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


class AnalysisStatus(db.Model):
    __tablename__ = 'analysis_status'

    id = Column(Integer, primary_key=True)
    name = Column(Text)


class CaseClassification(db.Model):
    __tablename__ = 'case_classification'

    id = Column(Integer, primary_key=True)
    name = Column(Text)
    name_expanded = Column(Text)
    description = Column(Text)
    creation_date = Column(DateTime, server_default=func.now(), nullable=True)
    created_by_id = Column(ForeignKey('user.id'), nullable=True)

    created_by = relationship('User')


class EvidenceTypes(db.Model):
    __tablename__ = 'evidence_type'

    id = Column(Integer, primary_key=True)
    name = Column(Text)
    description = Column(Text)
    creation_date = Column(DateTime, server_default=func.now(), nullable=True)
    created_by_id = Column(ForeignKey('user.id'), nullable=True)

    created_by = relationship('User')


class CaseTemplate(db.Model):
    __tablename__ = 'case_template'

    # Metadata
    id = Column(Integer, primary_key=True)
    created_by_user_id = Column(Integer, db.ForeignKey('user.id'))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    # Data
    name = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    author = Column(String, nullable=True)
    title_prefix = Column(String, nullable=True)
    summary = Column(String, nullable=True)
    tags = Column(JSON, nullable=True)
    tasks = Column(JSON, nullable=True)
    note_directories = Column(JSON, nullable=True)
    classification = Column(String, nullable=True)

    created_by_user = relationship('User')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def update_from_dict(self, data: dict):
        for field, value in data.items():
            setattr(self, field, value)


class Contact(db.Model):
    __tablename__ = 'contact'

    id = Column(BigInteger, primary_key=True)
    contact_uuid = Column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"), nullable=False)
    contact_name = Column(Text)
    contact_email = Column(Text)
    contact_role = Column(Text)
    contact_note = Column(Text)
    contact_work_phone = Column(Text)
    contact_mobile_phone = Column(Text)
    custom_attributes = Column(JSON)
    client_id = Column(ForeignKey('client.client_id'))

    client = relationship('Client')


class CaseEventsAssets(db.Model):
    __tablename__ = 'case_events_assets'

    id = Column(BigInteger, primary_key=True)
    event_id = Column(ForeignKey('cases_events.event_id'))
    asset_id = Column(ForeignKey('case_assets.asset_id'))
    case_id = Column(ForeignKey('cases.case_id'))

    event = relationship('CasesEvent')
    asset = relationship('CaseAssets')
    case = relationship('Cases')


class CaseEventsIoc(db.Model):
    __tablename__ = 'case_events_ioc'

    id = Column(BigInteger, primary_key=True)
    event_id = Column(ForeignKey('cases_events.event_id'))
    ioc_id = Column(ForeignKey('ioc.ioc_id'))
    case_id = Column(ForeignKey('cases.case_id'))

    event = relationship('CasesEvent')
    ioc = relationship('Ioc')
    case = relationship('Cases')


class ObjectState(db.Model):
    __tablename__ = 'object_state'

    object_id = Column(BigInteger, primary_key=True)
    object_case_id = Column(ForeignKey('cases.case_id'))
    object_updated_by_id = db.Column(db.Integer(), db.ForeignKey('user.id'))
    object_name = Column(Text)
    object_state = Column(BigInteger)
    object_last_update = Column(TIMESTAMP)

    case = relationship('Cases')
    updated_by = relationship('User')


class EventCategory(db.Model):
    __tablename__ = 'event_category'

    id = Column(Integer, primary_key=True)
    name = Column(Text)


class CaseEventCategory(db.Model):
    __tablename__ = 'case_events_category'

    id = Column(Integer, primary_key=True)
    event_id = Column(ForeignKey('cases_events.event_id'), unique=True)
    category_id = Column(ForeignKey('event_category.id'))

    event = relationship('CasesEvent', cascade="delete")
    category = relationship('EventCategory')


class CaseGraphAssets(db.Model):
    __tablename__ = 'case_graph_assets'

    id = Column(Integer, primary_key=True)
    case_id = Column(ForeignKey('cases.case_id'))
    asset_id = Column(Integer)
    asset_type_id = Column(ForeignKey('assets_type.asset_id'))

    case = relationship('Cases')
    asset_type = relationship('AssetsType')


class CaseGraphLinks(db.Model):
    __tablename__ = 'case_graph_links'

    id = Column(Integer, primary_key=True)
    case_id = Column(ForeignKey('cases.case_id'))
    source_id = Column(ForeignKey('case_graph_assets.id'))
    dest_id = Column(ForeignKey('case_graph_assets.id'))

    case = relationship('Cases')


class Languages(db.Model):
    __tablename__ = 'languages'

    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(), unique=True)
    code = db.Column(db.String(), unique=True)


class ReportType(db.Model):
    __tablename__ = 'report_type'

    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.Text(), unique=True)


class CaseTemplateReport(db.Model):
    __tablename__ = 'case_template_report'

    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String())
    description = db.Column(db.String())
    internal_reference = db.Column(db.String(), unique=True)
    naming_format = db.Column(db.String())
    created_by_user_id = db.Column(db.Integer(), db.ForeignKey('user.id'))
    date_created = db.Column(DateTime)
    language_id = db.Column(db.Integer(), db.ForeignKey('languages.id'))
    report_type_id = db.Column(db.Integer(), db.ForeignKey('report_type.id'))

    report_type = relationship('ReportType')
    language = relationship('Languages')
    created_by_user = relationship('User')


class Tlp(db.Model):
    __tablename__ = 'tlp'

    tlp_id = Column(Integer, primary_key=True)
    tlp_name = Column(Text)
    tlp_bscolor = Column(Text)


class Ioc(db.Model):
    __tablename__ = 'ioc'

    ioc_id = Column(BigInteger, primary_key=True)
    ioc_uuid = Column(UUID(as_uuid=True), server_default=text("gen_random_uuid()"), nullable=False)
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

    user = relationship('User')
    tlp = relationship('Tlp')
    ioc_type = relationship('IocType')

    alerts = relationship('Alert', secondary=alert_iocs_association, back_populates='iocs')


class CustomAttribute(db.Model):
    __tablename__ = 'custom_attribute'

    attribute_id = Column(Integer, primary_key=True)
    attribute_display_name = Column(Text)
    attribute_description = Column(Text)
    attribute_for = Column(Text)
    attribute_content = Column(JSON)


class DataStorePath(db.Model):
    __tablename__ = 'data_store_path'

    path_id = Column(BigInteger, primary_key=True)
    path_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    path_name = Column(Text, nullable=False)
    path_parent_id = Column(BigInteger)
    path_is_root = Column(Boolean)
    path_case_id = Column(ForeignKey('cases.case_id'), nullable=False)

    case = relationship('Cases')


class DataStoreFile(db.Model):
    __tablename__ = 'data_store_file'

    file_id = Column(BigInteger, primary_key=True)
    file_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"), nullable=False)
    file_original_name = Column(Text, nullable=False)
    file_local_name = Column(Text, nullable=False)
    file_description = Column(Text)
    file_date_added = Column(DateTime)
    file_tags = Column(Text)
    file_size = Column(BigInteger)
    file_is_ioc = Column(Boolean)
    file_is_evidence = Column(Boolean)
    file_password = Column(Text)
    file_parent_id = Column(ForeignKey('data_store_path.path_id'), nullable=False)
    file_sha256 = Column(Text)
    added_by_user_id = Column(ForeignKey('user.id'), nullable=False)
    modification_history = Column(JSON)
    file_case_id = Column(ForeignKey('cases.case_id'), nullable=False)

    case = relationship('Cases')
    user = relationship('User')
    data_parent = relationship('DataStorePath')


class IocType(db.Model):
    __tablename__ = 'ioc_type'

    type_id = Column(Integer, primary_key=True)
    type_name = Column(Text)
    type_description = Column(Text)
    type_taxonomy = Column(Text)
    type_validation_regex = Column(Text)
    type_validation_expect = Column(Text)


class IocLink(db.Model):
    __tablename__ = 'ioc_link'

    ioc_link_id = Column(Integer, primary_key=True)
    ioc_id = Column(ForeignKey('ioc.ioc_id'))
    case_id = Column(ForeignKey('cases.case_id'), nullable=False)

    ioc = relationship('Ioc')
    case = relationship('Cases')


class IocAssetLink(db.Model):
    __tablename__ = 'ioc_asset_link'

    ioc_asset_link_id = Column(Integer, primary_key=True)
    ioc_id = Column(ForeignKey('ioc.ioc_id'), nullable=False)
    asset_id = Column(ForeignKey('case_assets.asset_id'), nullable=False)

    ioc = relationship('Ioc')
    asset = relationship('CaseAssets')


class OsType(db.Model):
    __tablename__ = 'os_type'

    type_id = Column(Integer, primary_key=True)
    type_name = Column(String(155))


class CasesAssetsExt(db.Model):
    __tablename__ = 'cases_assets_ext'

    asset_id = Column(Integer, primary_key=True)
    type_id = Column(ForeignKey('assets_type.asset_id'))
    case_id = Column(ForeignKey('cases.case_id'))
    asset_content = Column(Text)

    type = relationship('AssetsType')
    case = relationship('Cases')


class Notes(db.Model):
    __tablename__ = 'notes'

    note_id = Column(BigInteger, primary_key=True)
    note_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"), nullable=False)
    note_title = Column(String(155))
    note_content = Column(Text)
    note_user = Column(ForeignKey('user.id'))
    note_creationdate = Column(DateTime)
    note_lastupdate = Column(DateTime)
    note_case_id = Column(ForeignKey('cases.case_id'))
    custom_attributes = Column(JSON)
    directory_id = Column(ForeignKey('note_directory.id'), nullable=True)
    modification_history = Column(JSON)

    user = relationship('User')
    case = relationship('Cases')
    directory = relationship('NoteDirectory', backref='notes')
    versions = relationship('NoteRevisions', back_populates='note', cascade="all, delete-orphan")


class NoteRevisions(db.Model):
    __tablename__ = 'note_revisions'

    revision_id = Column(BigInteger, primary_key=True)
    note_id = Column(BigInteger, ForeignKey('notes.note_id'), nullable=False)
    revision_number = Column(Integer, nullable=False)
    note_title = Column(String(155))
    note_content = Column(Text)
    note_user = Column(ForeignKey('user.id'))
    revision_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship('User')
    note = relationship('Notes', back_populates='versions')


class NoteDirectory(db.Model):
    __tablename__ = 'note_directory'

    id = Column(BigInteger, primary_key=True)
    name = Column(Text, nullable=False)
    parent_id = Column(ForeignKey('note_directory.id'), nullable=True)
    case_id = Column(ForeignKey('cases.case_id'), nullable=False)

    parent = relationship('NoteDirectory', remote_side=[id], backref='subdirectories')
    case = relationship('Cases', backref='note_directories')


class NotesGroup(db.Model):
    __tablename__ = 'notes_group'

    group_id = Column(BigInteger, primary_key=True)
    group_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"),
                        nullable=False)
    group_title = Column(String(155))
    group_user = Column(ForeignKey('user.id'))
    group_creationdate = Column(DateTime)
    group_lastupdate = Column(DateTime)
    group_case_id = Column(ForeignKey('cases.case_id'))

    user = relationship('User')
    case = relationship('Cases')


class NotesGroupLink(db.Model):
    __tablename__ = 'notes_group_link'

    link_id = Column(BigInteger, primary_key=True)
    group_id = Column(ForeignKey('notes_group.group_id'))
    note_id = Column(ForeignKey('notes.note_id'))
    case_id = Column(ForeignKey('cases.case_id'))

    note = relationship('Notes')
    note_group = relationship('NotesGroup')
    case = relationship('Cases')


class CaseKanban(db.Model):
    __tablename__ = 'case_kanban'

    case_id = Column(ForeignKey('cases.case_id'), primary_key=True)
    kanban_data = Column(Text)

    case = relationship('Cases')


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


class TaskStatus(db.Model):
    __tablename__ = 'task_status'

    id = Column(Integer, primary_key=True)
    status_name = Column(Text)
    status_description = Column(Text)
    status_bscolor = Column(Text)


class CaseTasks(db.Model):
    __tablename__ = 'case_tasks'

    id = Column(BigInteger, primary_key=True)
    task_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"), nullable=False)
    task_title = Column(Text)
    task_description = Column(Text)
    task_tags = Column(Text)
    task_open_date = Column(DateTime)
    task_close_date = Column(DateTime)
    task_last_update = Column(DateTime)
    task_userid_open = Column(ForeignKey('user.id'))
    task_userid_close = Column(ForeignKey('user.id'))
    task_userid_update = Column(ForeignKey('user.id'))
    task_status_id = Column(ForeignKey('task_status.id'))
    task_case_id = Column(ForeignKey('cases.case_id'))
    custom_attributes = Column(JSON)
    modification_history = Column(JSON)

    case = relationship('Cases')
    user_open = relationship('User', foreign_keys=[task_userid_open])
    user_close = relationship('User', foreign_keys=[task_userid_close])
    user_update = relationship('User', foreign_keys=[task_userid_update])
    status = relationship('TaskStatus', foreign_keys=[task_status_id])


class Tags(db.Model):
    __tablename__ = 'tags'

    id = Column(BigInteger, primary_key=True, nullable=False)
    tag_title = Column(Text, unique=True)
    tag_creation_date = Column(DateTime)
    tag_namespace = Column(Text)

    cases = relationship('Cases', secondary="case_tags", back_populates='tags', viewonly=True)

    def __init__(self, tag_title, namespace=None):
        self.id = None
        self.tag_title = tag_title
        self.tag_creation_date = datetime.datetime.now()
        self.tag_namespace = namespace

    def save(self):
        existing_tag = self.get_by_title(self.tag_title)
        if existing_tag is not None:
            return existing_tag
        else:
            db.session.add(self)
            db.session.commit()
            return self

    @classmethod
    def get_by_title(cls, tag_title):
        return cls.query.filter_by(tag_title=tag_title).first()


class TaskAssignee(db.Model):
    __tablename__ = "task_assignee"

    id = Column(BigInteger, primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    task_id = Column(BigInteger, ForeignKey('case_tasks.id'), nullable=False)

    user = relationship('User')
    task = relationship('CaseTasks')

    UniqueConstraint('user_id', 'task_id')


class GlobalTasks(db.Model):
    __tablename__ = 'global_tasks'

    id = Column(BigInteger, primary_key=True)
    task_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"), nullable=False)
    task_title = Column(Text)
    task_description = Column(Text)
    task_tags = Column(Text)
    task_open_date = Column(DateTime)
    task_close_date = Column(DateTime)
    task_last_update = Column(DateTime)
    task_userid_open = Column(ForeignKey('user.id'))
    task_userid_close = Column(ForeignKey('user.id'))
    task_userid_update = Column(ForeignKey('user.id'))
    task_assignee_id = Column(ForeignKey('user.id'), nullable=True)
    task_status_id = Column(ForeignKey('task_status.id'))

    user_open = relationship('User', foreign_keys=[task_userid_open])
    user_close = relationship('User', foreign_keys=[task_userid_close])
    user_update = relationship('User', foreign_keys=[task_userid_update])
    user_assigned = relationship('User', foreign_keys=[task_assignee_id])
    status = relationship('TaskStatus', foreign_keys=[task_status_id])


class UserActivity(db.Model):
    __tablename__ = "user_activity"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(ForeignKey('user.id'), nullable=True)
    case_id = Column(ForeignKey('cases.case_id'), nullable=True)
    activity_date = Column(DateTime)
    activity_desc = Column(Text)
    user_input = Column(Boolean, default=False)
    is_from_api = Column(Boolean, default=False)
    display_in_ui = Column(Boolean, default=True)

    user = relationship('User')
    case = relationship('Cases')


class ServerSettings(db.Model):
    __table_name__ = "server_settings"

    id = Column(Integer, primary_key=True)
    https_proxy = Column(Text)
    http_proxy = Column(Text)
    prevent_post_mod_repush = Column(Boolean)
    prevent_post_objects_repush = Column(Boolean, default=False)
    has_updates_available = Column(Boolean)
    enable_updates_check = Column(Boolean)
    password_policy_min_length = Column(Integer)
    password_policy_upper_case = Column(Boolean)
    password_policy_lower_case = Column(Boolean)
    password_policy_digit = Column(Boolean)
    password_policy_special_chars = Column(Text)
    enforce_mfa = Column(Boolean)


class Comments(db.Model):
    __tablename__ = "comments"

    comment_id = Column(BigInteger, primary_key=True)
    comment_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, server_default=text("gen_random_uuid()"),
                          nullable=False)
    comment_text = Column(Text)
    comment_date = Column(DateTime)
    comment_update_date = Column(DateTime)
    comment_user_id = Column(ForeignKey('user.id'))
    comment_case_id = Column(ForeignKey('cases.case_id'))
    comment_alert_id = Column(ForeignKey('alerts.alert_id'))

    user = relationship('User')
    case = relationship('Cases')
    alert = relationship('Alert')


class EventComments(db.Model):
    __tablename__ = "event_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_event_id = Column(ForeignKey('cases_events.event_id'))

    event = relationship('CasesEvent')
    comment = relationship('Comments')


class TaskComments(db.Model):
    __tablename__ = "task_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_task_id = Column(ForeignKey('case_tasks.id'))

    task = relationship('CaseTasks')
    comment = relationship('Comments')


class IocComments(db.Model):
    __tablename__ = "ioc_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_ioc_id = Column(ForeignKey('ioc.ioc_id'))

    ioc = relationship('Ioc')
    comment = relationship('Comments')


class AssetComments(db.Model):
    __tablename__ = "asset_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_asset_id = Column(ForeignKey('case_assets.asset_id'))

    asset = relationship('CaseAssets')
    comment = relationship('Comments')


class EvidencesComments(db.Model):
    __tablename__ = "evidence_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_evidence_id = Column(ForeignKey('case_received_file.id'))

    evidence = relationship('CaseReceivedFile')
    comment = relationship('Comments')


class NotesComments(db.Model):
    __tablename__ = "note_comments"

    id = Column(BigInteger, primary_key=True)
    comment_id = Column(ForeignKey('comments.comment_id'))
    comment_note_id = Column(ForeignKey('notes.note_id'))

    note = relationship('Notes')
    comment = relationship('Comments')


class IrisModule(db.Model):
    __tablename__ = "iris_module"

    id = Column(Integer, primary_key=True)
    added_by_id = Column(ForeignKey('user.id'), nullable=False)
    module_human_name = Column(Text)
    module_name = Column(Text)
    module_description = Column(Text)
    module_version = Column(Text)
    interface_version = Column(Text)
    date_added = Column(DateTime)
    is_active = Column(Boolean)
    has_pipeline = Column(Boolean)
    pipeline_args = Column(JSON)
    module_config = Column(JSON)
    module_type = Column(Text)

    user = relationship('User')


class IrisHook(db.Model):
    __tablename__ = "iris_hooks"

    id = Column(Integer, primary_key=True)
    hook_name = Column(Text)
    hook_description = Column(Text)


class IrisModuleHook(db.Model):
    __tablename__ = "iris_module_hooks"

    id = Column(BigInteger, primary_key=True)
    module_id = Column(ForeignKey('iris_module.id'), nullable=False)
    hook_id = Column(ForeignKey('iris_hooks.id'), nullable=False)
    is_manual_hook = Column(Boolean)
    manual_hook_ui_name = Column(Text)
    retry_on_fail = Column(Boolean)
    max_retry = Column(Integer)
    run_asynchronously = Column(Boolean)
    wait_till_return = Column(Boolean)

    module = relationship('IrisModule')
    hook = relationship('IrisHook')


class IrisReport(db.Model):
    __tablename__ = 'iris_reports'

    report_id = Column(db.Integer, Sequence("iris_reports_id_seq"), primary_key=True)
    case_id = Column(ForeignKey('cases.case_id'), nullable=False)
    report_title = Column(String(155))
    report_date = Column(DateTime)
    report_content = Column('report_content', JSON)
    user_id = Column(ForeignKey('user.id'))

    user = relationship('User')
    case = relationship('Cases')

    def __init__(self, case_id, report_title, report_date, report_content, user_id):
        self.case_id = case_id
        self.report_title = report_title
        self.report_date = report_date
        self.report_content = report_content
        self.user_id = user_id

    def save(self):
        # Create an engine and a session because this method
        # will be called from Celery thread and might cause
        # error if it uses the session context of the app
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        Session = sessionmaker(bind=engine)
        session = Session()

        # inject self into db session
        session.add(self)

        # commit change and save the object
        session.commit()

        # Close session
        session.close()

        # Dispose engine
        engine.dispose()

        return self


class SavedFilter(db.Model):
    __tablename__ = 'saved_filters'

    filter_id = Column(BigInteger, primary_key=True)
    created_by = Column(ForeignKey('user.id'), nullable=False)
    filter_name = Column(Text, nullable=False)
    filter_description = Column(Text)
    filter_data = Column(JSON, nullable=False)
    filter_is_private = Column(Boolean, nullable=False)
    filter_type = Column(Text, nullable=False)

    user = relationship('User', foreign_keys=[created_by])


class ReviewStatus(db.Model):
    __tablename__ = 'review_status'

    id = Column(Integer, primary_key=True)
    status_name = Column(Text, nullable=False)


class CeleryTaskMeta(db.Model):
    __bind_key__ = 'iris_tasks'
    __tablename__ = 'celery_taskmeta'

    id = Column(BigInteger, Sequence('task_id_sequence'), primary_key=True)
    task_id = Column(String(155))
    status = Column(String(50))
    result = Column(LargeBinary)
    date_done = Column(DateTime)
    traceback = Column(Text)
    name = Column(String(155))
    args = Column(LargeBinary)
    kwargs = Column(LargeBinary)
    worker = Column(String(155))
    retries = Column(Integer)
    queue = Column(String(155))

    def __repr__(self):
        return str(self.id) + ' - ' + str(self.user)


def create_safe_attr(session, attribute_display_name, attribute_description, attribute_for, attribute_content):
    cat = CustomAttribute.query.filter(
        CustomAttribute.attribute_display_name == attribute_display_name,
        CustomAttribute.attribute_description == attribute_description,
        CustomAttribute.attribute_for == attribute_for
    ).first()

    if cat:
        return False
    else:
        instance = CustomAttribute()
        instance.attribute_display_name = attribute_display_name
        instance.attribute_description = attribute_description
        instance.attribute_for = attribute_for
        instance.attribute_content = attribute_content
        session.add(instance)
        session.commit()
        return True


