#!/usr/bin/env python3
#
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

# IMPORTS ------------------------------------------------
import secrets

from app import db, app
from flask_login import UserMixin

from sqlalchemy import Boolean, Column, Date, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text, \
    LargeBinary, DateTime, Sequence, or_, BigInteger, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, backref


Base = declarative_base()
metadata = Base.metadata


def create_safe(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return False
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return True


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

    client_id = Column(Integer, primary_key=True)
    name = Column(String(2048), unique=True)

    def __init__(self, name):
        self.name = name


class AssetsType(db.Model):
    __tablename__ = 'assets_type'

    asset_id = Column(Integer, primary_key=True)
    asset_name = Column(String(155))
    asset_description = Column(String(255))


class CaseAssets(db.Model):
    __tablename__ = 'case_assets'

    asset_id = Column(Integer, primary_key=True)
    asset_name = Column(Text)
    asset_description = Column(Text)
    asset_domain = Column(Text)
    asset_ip = Column(Text)
    asset_info = Column(Text)
    asset_compromised = Column(Boolean)
    asset_type_id = Column(ForeignKey('assets_type.asset_id'))
    asset_tags = Column(Text)
    case_id = Column(ForeignKey('cases.case_id'))
    date_added = Column(DateTime)
    date_update = Column(DateTime)
    user_id = Column(ForeignKey('user.id'))
    analysis_status_id = Column(ForeignKey('analysis_status.id'))

    case = relationship('Cases')
    user = relationship('User')
    asset_type = relationship('AssetsType')
    analysis_status = relationship('AnalysisStatus')


class AnalysisStatus(db.Model):
    __tablename__ = 'analysis_status'

    id = Column(Integer, primary_key=True)
    name = Column(Text)


class CaseEventsAssets(db.Model):
    __tablename__ = 'case_events_assets'

    id = Column(Integer, primary_key=True)
    event_id = Column(ForeignKey('cases_events.event_id'))
    asset_id = Column(ForeignKey('case_assets.asset_id'))
    case_id = Column(ForeignKey('cases.case_id'))

    event = relationship('CasesEvent')
    asset = relationship('CaseAssets')
    case = relationship('Cases')


class ObjectState(db.Model):
    object_id = Column(Integer, primary_key=True)
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


class FileBehavior(db.Model):
    __tablename__ = 'file_behaviors'

    id = Column(UUID, primary_key=True)
    behaviors = Column(String(256), unique=True)


class FileContentHash(db.Model):
    __tablename__ = 'file_content_hash'

    content_hash = Column(UUID, primary_key=True)
    vt_url = Column(String(512))
    vt_score = Column(Numeric)
    comment = Column(String(2048))
    flag = Column(String(256))
    seen_count = Column(Integer)
    last_update = Column(Date)
    sha256 = Column(String(128))
    misp = Column(Text)


class FileEdna(db.Model):
    __tablename__ = 'file_edna'

    id = Column(UUID, primary_key=True)
    edna = Column(Text, unique=True)


class FileImphash(db.Model):
    __tablename__ = 'file_imphash'

    id = Column(UUID, primary_key=True)
    imphash = Column(String(256), unique=True)


class FileImport(db.Model):
    __tablename__ = 'file_imports'

    id = Column(UUID, primary_key=True)
    imports = Column(Integer, unique=True)


class FileName(db.Model):
    __tablename__ = 'file_name'

    fn_hash = Column(UUID, primary_key=True)
    filename = Column(String(256))


class FileSection(db.Model):
    __tablename__ = 'file_sections'

    id = Column(UUID, primary_key=True)
    sections = Column(String(512), unique=True)


class PathName(db.Model):
    __tablename__ = 'path_name'

    path_hash = Column(UUID, primary_key=True)
    path = Column(String(1024))

"""
class TemplateGroup(db.Model):
    __tablename__ = 'template_group'

    group_id = Column(Integer, primary_key=True, server_default=text("nextval('template_group_group_id_seq'::regclass)"))
    name = Column(String(256), unique=True)
    description = Column(String(2048))
    author = Column(String(256))


class TemplateSne(db.Model):
    __tablename__ = 'template_sne'

    template_id = Column(Integer, primary_key=True, server_default=text("nextval('template_template_id_seq'::regclass)"))
    template_name = Column(String(256), unique=True)
    template_desc = Column(String(2048))
    registration_date = Column(Date)
"""

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)


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


# Define the UserRoles association table
class UserRoles(db.Model):
    __tablename__ = 'user_roles'
    id = db.Column(db.Integer(), primary_key=True)
    user_id = db.Column(db.Integer(), db.ForeignKey('user.id', ondelete='CASCADE'))
    role_id = db.Column(db.Integer(), db.ForeignKey('roles.id', ondelete='CASCADE'))


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(64), unique=False)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(500))
    ctx_case = db.Column(Integer)
    ctx_human_case = db.Column(db.String(256))
    active = db.Column(db.Boolean())
    api_key = db.Column(db.Text(), unique=True)

    roles = db.relationship('Role', secondary='user_roles')

    def __init__(self, user, name, email, password, active):
        self.user = user
        self.name = name
        self.password = password
        self.email = email
        self.active = active
        self.roles = []

    def __repr__(self):
        return str(self.id) + ' - ' + str(self.user)

    def save(self):

        # Default roles:
        roles = Role.query.filter(or_(Role.id == 2, Role.id == 3)).all()
        self.roles = roles

        self.api_key = secrets.token_urlsafe(nbytes=64)

        # inject self into db session
        db.session.add(self)
        db.session.commit()

        for role in roles:
            ur = UserRoles()
            ur.user_id = self.id
            ur.role_id = role.id
            db.session.add(ur)

        # commit change and save the object
        db.session.commit()

        return self

    def is_admin(self):
        roles = [role.name for role in self.roles]
        if "administrator" in roles:
            return True
        return False


class Fullpath(db.Model):
    __tablename__ = 'fullpath'

    full_path_hash = Column(UUID, primary_key=True)
    full_path = Column(String(2048))
    path_hash = Column(ForeignKey('path_name.path_hash'))
    fn_hash = Column(ForeignKey('file_name.fn_hash'))

    file_name = relationship('FileName')
    path_name = relationship('PathName')


class Tlp(db.Model):
    __tablename__ = 'tlp'

    tlp_id = Column(Integer, primary_key=True)
    tlp_name = Column(Text)
    tlp_bscolor = Column(Text)


class Ioc(db.Model):
    __tablename__ = 'ioc'

    ioc_id = Column(Integer, primary_key=True)
    ioc_value = Column(Text)
    ioc_type_id = Column(ForeignKey('ioc_type.type_id'))
    ioc_description = Column(Text)
    ioc_tags = Column(String(512))
    user_id = Column(ForeignKey('user.id'))
    ioc_misp = Column(Text)
    ioc_tlp_id = Column(ForeignKey('tlp.tlp_id'))

    user = relationship('User')
    tlp = relationship('Tlp')
    ioc_type = relationship('IocType')


class IocType(db.Model):
    __tablename__ = 'ioc_type'

    type_id = Column(Integer, primary_key=True)
    type_name = Column(Text)
    type_description = Column(Text)
    type_taxonomy = Column(Text)


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


class HashLink(db.Model):
    __tablename__ = 'hash_link'

    link_key = Column(UUID, primary_key=True)
    content_hash = Column(ForeignKey('file_content_hash.content_hash'))
    fn_hash = Column(ForeignKey('file_name.fn_hash'))
    path_hash = Column(ForeignKey('path_name.path_hash'))
    seen_count = Column(Integer)
    edna_id = Column(ForeignKey('file_edna.id'))
    imphash_id = Column(ForeignKey('file_imphash.id'))
    behaviors_id = Column(ForeignKey('file_behaviors.id'))
    sections_id = Column(ForeignKey('file_sections.id'))
    imports_id = Column(ForeignKey('file_imports.id'))

    behaviors = relationship('FileBehavior')
    file_content_hash = relationship('FileContentHash')
    edna = relationship('FileEdna')
    file_name = relationship('FileName')
    imphash = relationship('FileImphash')
    imports = relationship('FileImport')
    path_name = relationship('PathName')
    sections = relationship('FileSection')


class CasesDatum(db.Model):
    __tablename__ = 'cases_data'
    __table_args__ = (
        UniqueConstraint('case_id', 'link_key'),
        Index('idx_invest_data', 'id', 'case_id', 'link_key', unique=True)
    )

    id = Column(Integer, primary_key=True)
    case_id = Column(ForeignKey('cases.case_id'), nullable=False, )
    link_key = Column(ForeignKey('hash_link.link_key'))

    case = relationship('Cases', backref=backref("CasesDatum", cascade="all,delete,delete-orphan"))
    hash_link = relationship('HashLink')


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

    note_id = Column(Integer, primary_key=True)
    note_title = Column(String(155))
    note_content = Column(Text)
    note_user = Column(ForeignKey('user.id'))
    note_creationdate = Column(DateTime)
    note_lastupdate = Column(DateTime)
    note_case_id = Column(ForeignKey('cases.case_id'))

    user = relationship('User')
    case = relationship('Cases')


class NotesGroup(db.Model):
    __tablename__ = 'notes_group'

    group_id = Column(Integer, primary_key=True)
    group_title = Column(String(155))
    group_user = Column(ForeignKey('user.id'))
    group_creationdate = Column(DateTime)
    group_lastupdate = Column(DateTime)
    group_case_id = Column(ForeignKey('cases.case_id'))

    user = relationship('User')
    case = relationship('Cases')


class NotesGroupLink(db.Model):
    __tablename__ = 'notes_group_link'

    link_id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
    filename = Column(Text)
    date_added = Column(DateTime)
    file_hash = Column(String(65))
    file_description = Column(Text)
    file_size = Column(Integer)
    case_id = Column(ForeignKey('cases.case_id'))
    user_id = Column(ForeignKey('user.id'))

    case = relationship('Cases')
    user = relationship('User')


class TaskStatus(db.Model):
    __tablename__ = 'task_status'

    id = Column(Integer, primary_key=True)
    status_name = Column(Text)
    status_description = Column(Text)
    status_bscolor = Column(Text)


class CaseTasks(db.Model):
    __tablename__ = 'case_tasks'

    id = Column(Integer, primary_key=True)
    task_title = Column(Text)
    task_description = Column(Text)
    task_tags = Column(Text)
    task_open_date = Column(DateTime)
    task_close_date = Column(DateTime)
    task_last_update = Column(DateTime)
    task_userid_open = Column(ForeignKey('user.id'))
    task_userid_close = Column(ForeignKey('user.id'))
    task_userid_update = Column(ForeignKey('user.id'))
    task_assignee_id = Column(ForeignKey('user.id'))
    task_status_id = Column(ForeignKey('task_status.id'))
    task_case_id = Column(ForeignKey('cases.case_id'))

    case = relationship('Cases')
    user_open = relationship('User', foreign_keys=[task_userid_open])
    user_close = relationship('User', foreign_keys=[task_userid_close])
    user_update = relationship('User', foreign_keys=[task_userid_update])
    user_assigned = relationship('User', foreign_keys=[task_assignee_id])
    status = relationship('TaskStatus', foreign_keys=[task_status_id])


class GlobalTasks(db.Model):
    __tablename__ = 'global_tasks'

    id = Column(Integer, primary_key=True)
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

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('user.id'), nullable=True)
    case_id = Column(ForeignKey('cases.case_id'), nullable=True)
    activity_date = Column(DateTime)
    activity_desc = Column(Text)
    user_input = Column(Boolean)
    is_from_api = Column(Boolean)

    user = relationship('User')
    case = relationship('Cases')


class IrisModule(db.Model):
    __tablename__ = "iris_module"

    id = Column(Integer, primary_key=True)
    added_by_id = Column(ForeignKey('user.id'), nullable=True)
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

    user = relationship('User')


class IrisReport(db.Model):
    __tablename__ = 'iris_reports'

    report_id = Column(db.Integer,Sequence("iris_reports_id_seq"), primary_key=True)
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


class CeleryTaskMeta(db.Model):
    __bind_key__ = 'iris_tasks'
    __tablename__ = 'celery_taskmeta'

    id = Column(Integer, Sequence('task_id_sequence'), primary_key=True)
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
