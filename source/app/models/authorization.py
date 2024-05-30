import enum
import secrets
import pyotp
import uuid
from flask_login import UserMixin
from sqlalchemy import BigInteger, JSON
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app import db


class CaseAccessLevel(enum.Enum):
    deny_all = 0x1
    read_only = 0x2
    full_access = 0x4

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class Permissions(enum.Enum):
    standard_user = 0x1
    server_administrator = 0x2

    alerts_read = 0x4
    alerts_write = 0x8
    alerts_delete = 0x10

    search_across_cases = 0x20

    customers_read = 0x40
    customers_write = 0x80

    case_templates_read = 0x100
    case_templates_write = 0x200

    activities_read = 0x400
    all_activities_read = 0x800


class Organisation(db.Model):
    __tablename__ = 'organisations'

    org_id = Column(BigInteger, primary_key=True)
    org_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                      server_default=text('gen_random_uuid()'), unique=True)
    org_name = Column(Text, nullable=False, unique=True)
    org_description = Column(Text)
    org_url = Column(Text)
    org_logo = Column(Text)
    org_email = Column(Text)
    org_nationality = Column(Text)
    org_sector = Column(Text)
    org_type = Column(Text)

    UniqueConstraint('org_name')


class OrganisationCaseAccess(db.Model):
    __tablename__ = "organisation_case_access"

    id = Column(BigInteger, primary_key=True)
    org_id = Column(BigInteger, ForeignKey('organisations.org_id'), nullable=False)
    case_id = Column(BigInteger, ForeignKey('cases.case_id'), nullable=False)
    access_level = Column(BigInteger, nullable=False)

    org = relationship('Organisation')
    case = relationship('Cases')

    UniqueConstraint('case_id', 'org_id')


class Group(db.Model):
    __tablename__ = 'groups'

    group_id = Column(BigInteger, primary_key=True)
    group_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                        server_default=text('gen_random_uuid()'), unique=True)
    group_name = Column(Text, nullable=False, unique=True)
    group_description = Column(Text)
    group_permissions = Column(BigInteger, nullable=False)
    group_auto_follow = Column(Boolean, nullable=False, default=False)
    group_auto_follow_access_level = Column(BigInteger, nullable=False, default=0)

    UniqueConstraint('group_name')


class GroupCaseAccess(db.Model):
    __tablename__ = "group_case_access"

    id = Column(BigInteger, primary_key=True)
    group_id = Column(BigInteger, ForeignKey('groups.group_id'), nullable=False)
    case_id = Column(BigInteger, ForeignKey('cases.case_id'), nullable=False)
    access_level = Column(BigInteger, nullable=False)

    group = relationship('Group')
    case = relationship('Cases')

    UniqueConstraint('case_id', 'group_id')


class UserCaseAccess(db.Model):
    __tablename__ = "user_case_access"

    id = Column(BigInteger, primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    case_id = Column(BigInteger, ForeignKey('cases.case_id'), nullable=False)
    access_level = Column(BigInteger, nullable=False)

    user = relationship('User')
    case = relationship('Cases')

    UniqueConstraint('case_id', 'user_id')


class UserCaseEffectiveAccess(db.Model):
    __tablename__ = "user_case_effective_access"

    id = Column(BigInteger, primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    case_id = Column(BigInteger, ForeignKey('cases.case_id'), nullable=False)
    access_level = Column(BigInteger, nullable=False)

    user = relationship('User')
    case = relationship('Cases')

    UniqueConstraint('case_id', 'user_id')


class UserOrganisation(db.Model):
    __tablename__ = "user_organisation"

    id = Column(BigInteger, primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    org_id = Column(BigInteger, ForeignKey('organisations.org_id'), nullable=False)
    is_primary_org = Column(Boolean, nullable=False)

    user = relationship('User')
    org = relationship('Organisation')

    UniqueConstraint('user_id', 'org_id')


class UserGroup(db.Model):
    __tablename__ = "user_group"

    id = Column(BigInteger, primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    group_id = Column(BigInteger, ForeignKey('groups.group_id'), nullable=False)

    user = relationship('User')
    group = relationship('Group')

    UniqueConstraint('user_id', 'group_id')


class UserClient(db.Model):
    __tablename__ = "user_client"

    id = Column(BigInteger, primary_key=True, nullable=False)
    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    client_id = Column(BigInteger, ForeignKey('client.client_id'), nullable=False)
    access_level = Column(BigInteger, nullable=False)
    allow_alerts = Column(Boolean, nullable=False)

    user = relationship('User')
    client = relationship('Client')

    UniqueConstraint('user_id', 'client_id')


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = Column(BigInteger, primary_key=True)
    user = Column(String(64), unique=True)
    name = Column(String(64), unique=False)
    email = Column(String(120), unique=True)
    uuid = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False,
                  server_default=text('gen_random_uuid()'), unique=True)
    password = Column(String(500))
    ctx_case = Column(Integer)
    ctx_human_case = Column(String(256))
    active = Column(Boolean())
    api_key = Column(Text(), unique=True)
    external_id = Column(Text, unique=True)
    in_dark_mode = Column(Boolean())
    has_mini_sidebar = Column(Boolean(), default=False)
    has_deletion_confirmation = Column(Boolean(), default=False)
    is_service_account = Column(Boolean(), default=False)
    mfa_secrets = Column(Text, nullable=True)
    webauthn_credentials = Column(JSON, nullable=True)
    mfa_setup_complete = Column(Boolean(), default=False)

    def __init__(self, user: str, name: str, email: str, password: str, active: bool,
                 external_id: str = None, is_service_account: bool = False, mfa_secret: str = None,
                 webauthn_credentials: list = None):
        self.user = user
        self.name = name
        self.password = password
        self.email = email
        self.active = active
        self.external_id = external_id
        self.is_service_account = is_service_account
        self.mfa_secrets = mfa_secret
        self.mfa_setup_complete = False
        self.webauthn_credentials = webauthn_credentials or []

    def __repr__(self):
        return str(self.id) + ' - ' + str(self.user)

    def save(self):

        self.api_key = secrets.token_urlsafe(nbytes=64)

        # inject self into db session
        db.session.add(self)
        db.session.commit()

        return self
