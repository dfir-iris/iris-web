import secrets

from flask_login import UserMixin
from sqlalchemy import Integer
from sqlalchemy import or_

from app import db


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(50), unique=True)


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
    external_id = db.Column(db.Text, unique=True)
    in_dark_mode = db.Column(db.Boolean())

    roles = db.relationship('Role', secondary='user_roles')

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