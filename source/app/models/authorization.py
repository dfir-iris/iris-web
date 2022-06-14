import uuid

import secrets

from flask_login import UserMixin
from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app import db


class Organisation(db.Model):
    __tablename__ = 'organisations'

    org_id = Column(BigInteger, primary_key=True)
    org_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    org_name = Column(Text, nullable=False, unique=True)
    org_description = Column(Text)
    org_url = Column(Text)
    org_logo = Column(Text)
    org_email = Column(Text)
    org_nationality = Column(Text)
    org_sector = Column(Text)
    org_type = Column(Text)


class OrganisationCaseAccess(db.Model):
    __tablename__ = "organisation_case_access"

    id = Column(BigInteger, primary_key=True)
    org_id = Column(BigInteger, ForeignKey('organisations.org_id'), nullable=False)
    case_id = Column(BigInteger, ForeignKey('cases.case_id'), nullable=False)
    access_level = Column(BigInteger, nullable=False)

    org = relationship('Organisation')
    case = relationship('Case')


class Group(db.Model):
    __tablename__ = 'groups'

    group_id = Column(BigInteger, primary_key=True)
    group_uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    group_name = Column(Text, nullable=False, unique=True)
    group_description = Column(Text)
    group_permissions = Column(Text)


class GroupCaseAccess(db.Model):
    __tablename__ = "group_case_access"

    id = Column(BigInteger, primary_key=True)
    group_id = Column(BigInteger, ForeignKey('groups.group_id'), nullable=False)
    case_id = Column(BigInteger, ForeignKey('cases.case_id'), nullable=False)
    access_level = Column(BigInteger, nullable=False)

    group = relationship('Group')
    case = relationship('Case')


class Role(db.Model):
    __tablename__ = 'roles'
    id = Column(Integer(), primary_key=True)
    name = Column(String(50), unique=True)


# Define the UserRoles association table
class UserRoles(db.Model):
    __tablename__ = 'user_roles'
    id = Column(Integer(), primary_key=True)
    user_id = Column(Integer(), ForeignKey('user.id', ondelete='CASCADE'))
    role_id = Column(Integer(), ForeignKey('roles.id', ondelete='CASCADE'))


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = Column(db.Integer, primary_key=True)
    user = Column(String(64), unique=True)
    name = Column(String(64), unique=False)
    email = Column(String(120), unique=True)
    password = Column(String(500))
    ctx_case = Column(Integer)
    ctx_human_case = Column(String(256))
    active = Column(Boolean())
    api_key = Column(Text(), unique=True)
    external_id = Column(Text, unique=True)
    in_dark_mode = Column(Boolean())

    roles = relationship('Role', secondary='user_roles')

    def __init__(self, user: str, name: str, email: str, password: str, active: str, external_id: str = None):
        self.user = user
        self.name = name
        self.password = password
        self.email = email
        self.active = active
        self.external_id = external_id
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


# mapping tables
UserOrganisation = db.Table(
    'user_organisation', db.Model.metadata,
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('org_id', db.Integer, db.ForeignKey('organisations.org_id'))
)