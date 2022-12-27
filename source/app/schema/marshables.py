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
import datetime
import dateutil.parser
import marshmallow
import os
import pyminizip
import random
import re
import string
from flask_login import current_user
from marshmallow import fields
from marshmallow import post_load
from marshmallow import pre_load
from marshmallow.validate import Length
from marshmallow_sqlalchemy import auto_field
from pathlib import Path
from sqlalchemy import func

from app import app
from app import db
from app import ma
from app.datamgmt.case.case_db import save_case_tags
from app.datamgmt.datastore.datastore_db import datastore_get_standard_path
from app.datamgmt.manage.manage_attribute_db import merge_custom_attributes
from app.iris_engine.access_control.utils import ac_mask_from_val_list
from app.models import AnalysisStatus
from app.models import AssetsType
from app.models import CaseAssets
from app.models import CaseReceivedFile
from app.models import CaseTasks
from app.models import Cases
from app.models import CasesEvent
from app.models import Client
from app.models import Comments
from app.models import Contact
from app.models import DataStoreFile
from app.models import EventCategory
from app.models import GlobalTasks
from app.models import Ioc
from app.models import IocType
from app.models import Notes
from app.models import NotesGroup
from app.models import ServerSettings
from app.models import TaskStatus
from app.models import Tlp
from app.models.authorization import Group
from app.models.authorization import Organisation
from app.models.authorization import User
from app.util import file_sha256sum
from app.util import stream_sha256sum

ALLOWED_EXTENSIONS = {'png', 'svg'}


def allowed_file_icon(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_random_string(length):
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


def store_icon(file):
    if not file:
        return None, 'Icon file is not valid'

    if not allowed_file_icon(file.filename):
        return None, 'Icon filetype is not allowed'

    filename = get_random_string(18)

    try:

        store_fullpath = os.path.join(app.config['ASSET_STORE_PATH'], filename)
        show_fullpath = os.path.join(app.config['APP_PATH'], 'app',
                                     app.config['ASSET_SHOW_PATH'].strip(os.path.sep),
                                     filename)
        file.save(store_fullpath)
        os.symlink(store_fullpath, show_fullpath)

    except Exception as e:
        return None, f"Unable to add icon {e}"

    return filename, 'Saved'


class CaseNoteSchema(ma.SQLAlchemyAutoSchema):
    csrf_token = fields.String(required=False)
    group_id = fields.Integer()
    group_uuid = fields.UUID()
    group_title = fields.String()

    class Meta:
        model = Notes
        load_instance = True


class CaseAddNoteSchema(ma.Schema):
    note_id = fields.Integer(required=False)
    note_title = fields.String(required=True, validate=Length(min=1, max=154), allow_none=False)
    note_content = fields.String(required=False, validate=Length(min=1))
    group_id = fields.Integer(required=True)
    csrf_token = fields.String(required=False)
    custom_attributes = fields.Dict(required=False)

    def verify_group_id(self, data, **kwargs):
        group = NotesGroup.query.filter(
            NotesGroup.group_id == data.get('group_id'),
            NotesGroup.group_case_id == kwargs.get('caseid')
        ).first()
        if group:
            return data

        raise marshmallow.exceptions.ValidationError("Invalid group id for note",
                                                     field_name="group_id")

    @post_load
    def custom_attributes_merge(self, data, **kwargs):
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('note_id'), 'note')

        return data


class CaseGroupNoteSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = NotesGroup
        load_instance = True


class CaseAssetsSchema(ma.SQLAlchemyAutoSchema):
    asset_name = auto_field('asset_name', required=True, validate=Length(min=2), allow_none=False)
    ioc_links = fields.List(fields.String, required=False)

    class Meta:
        model = CaseAssets
        include_fk = True
        load_instance = True

    @pre_load
    def verify_data(self, data, **kwargs):
        asset_type = AssetsType.query.filter(AssetsType.asset_id == data.get('asset_type_id')).count()
        if not asset_type:
            raise marshmallow.exceptions.ValidationError("Invalid asset type ID",
                                                         field_name="asset_type_id")

        status = AnalysisStatus.query.filter(AnalysisStatus.id == data.get('analysis_status_id')).count()
        if not status:
            raise marshmallow.exceptions.ValidationError("Invalid analysis status ID",
                                                         field_name="analysis_status_id")

        return data

    @post_load
    def custom_attributes_merge(self, data, **kwargs):
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('asset_id'), 'asset')

        return data


class IocSchema(ma.SQLAlchemyAutoSchema):
    ioc_value = auto_field('ioc_value', required=True, validate=Length(min=1), allow_none=False)
    ioc_type = auto_field('ioc_type', required=False)

    class Meta:
        model = Ioc
        load_instance = True
        include_fk = True

    @pre_load
    def verify_data(self, data, **kwargs):
        ioc_type = IocType.query.filter(IocType.type_id == data.get('ioc_type_id')).first()
        if not ioc_type:
            raise marshmallow.exceptions.ValidationError("Invalid ioc type ID",
                                                         field_name="ioc_type_id")

        tlp_id = Tlp.query.filter(Tlp.tlp_id == data.get('ioc_tlp_id')).count()
        if not tlp_id:
            raise marshmallow.exceptions.ValidationError("Invalid TLP ID",
                                                         field_name="ioc_tlp_id")

        if ioc_type.type_validation_regex:
            if not re.fullmatch(ioc_type.type_validation_regex, data.get('ioc_value'), re.IGNORECASE):
                error = f"The input doesn\'t match the expected format " \
                        f"(expected: {ioc_type.type_validation_expect or ioc_type.type_validation_regex})"
                raise marshmallow.exceptions.ValidationError(error,
                                                             field_name="ioc_ioc_value")

        return data

    @post_load
    def custom_attributes_merge(self, data, **kwargs):
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('ioc_id'), 'ioc')

        return data


class CommentSchema(ma.SQLAlchemyAutoSchema):

    class Meta:
        model = Comments
        load_instance = True
        include_fk = True


class EventSchema(ma.SQLAlchemyAutoSchema):
    event_title = auto_field('event_title', required=True, validate=Length(min=2), allow_none=False)
    event_assets = fields.List(fields.Integer, required=True, allow_none=False)
    event_iocs = fields.List(fields.Integer, required=True, allow_none=False)
    event_date = fields.DateTime("%Y-%m-%dT%H:%M:%S.%f", required=True, allow_none=False)
    event_tz = fields.String(required=True, allow_none=False)
    event_category_id = fields.Integer(required=True, allow_none=False)
    event_date_wtz = fields.DateTime("%Y-%m-%dT%H:%M:%S.%f", required=False, allow_none=False)
    modification_history = auto_field('modification_history', required=False, readonly=True)
    event_comments_map = fields.List(fields.Integer, required=False, allow_none=True)

    class Meta:
        model = CasesEvent
        load_instance = True
        include_fk = True

    def validate_date(self, event_date, event_tz):
        date_time = "{}{}".format(event_date, event_tz)
        date_time_wtz = "{}".format(event_date)

        try:

            self.event_date = dateutil.parser.isoparse(date_time)
            self.event_date_wtz = dateutil.parser.isoparse(date_time_wtz)

        except Exception as e:
            raise marshmallow.exceptions.ValidationError("Invalid date time",
                                                         field_name="event_date")

        return self.event_date, self.event_date_wtz

    @pre_load
    def verify_data(self, data, **kwargs):
        if not isinstance(int(data.get('event_category_id')), int):
            raise marshmallow.exceptions.ValidationError("Invalid event category ID",
                                                         field_name="event_category_id")

        event_cat = EventCategory.query.filter(EventCategory.id == int(data.get('event_category_id'))).count()
        if not event_cat:
            raise marshmallow.exceptions.ValidationError("Invalid event category ID",
                                                         field_name="event_category_id")

        for asset in data.get('event_assets'):
            ast = CaseAssets.query.filter(CaseAssets.asset_id == asset).count()
            if not ast:
                raise marshmallow.exceptions.ValidationError("Invalid assets ID",
                                                             field_name="event_assets")

        for ioc in data.get('event_iocs'):
            ast = Ioc.query.filter(Ioc.ioc_id == ioc).count()
            if not ast:
                raise marshmallow.exceptions.ValidationError("Invalid IOC ID",
                                                             field_name="event_assets")
        if data.get('event_color') and data.get('event_color') not in ['#fff', '#1572E899', '#6861CE99', '#48ABF799',
                                                                       '#31CE3699',  '#F2596199', '#FFAD4699']:
            data['event_color'] = ''
        return data

    @post_load
    def custom_attributes_merge(self, data, **kwargs):
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('event_id'), 'event')

        return data


class DSFileSchema(ma.SQLAlchemyAutoSchema):
    csrf_token = fields.String(required=False)
    file_original_name = auto_field('file_original_name', required=True, validate=Length(min=1), allow_none=False)
    file_description = auto_field('file_description', allow_none=False)
    file_content = fields.Raw(required=False)

    class Meta:
        model = DataStoreFile
        include_fk = True
        load_instance = True

    def ds_store_file_b64(self, filename, file_content, dsp, cid):
        try:
            filename = filename.rstrip().replace('\t', '').replace('\n', '').replace('\r', '')
            file_hash = stream_sha256sum(file_content)

            dsf = DataStoreFile.query.filter(DataStoreFile.file_sha256 == file_hash).first()
            if dsf:
                exists = True

            else:
                dsf = DataStoreFile()
                dsf.file_original_name = filename
                dsf.file_description = "Pasted in notes"
                dsf.file_tags = "notes"
                dsf.file_password = ""
                dsf.file_is_ioc = False
                dsf.file_is_evidence = False
                dsf.file_case_id = cid
                dsf.file_date_added = datetime.datetime.now()
                dsf.added_by_user_id = current_user.id
                dsf.file_local_name = 'tmp_xc'
                dsf.file_parent_id = dsp.path_id
                dsf.file_sha256 = file_hash

                db.session.add(dsf)
                db.session.commit()

                dsf.file_local_name = datastore_get_standard_path(dsf, cid).as_posix()
                db.session.commit()

                with open(dsf.file_local_name, 'wb') as fout:
                    fout.write(file_content)

                exists = False

        except Exception as e:
            raise marshmallow.exceptions.ValidationError(
                str(e),
                field_name='file_password'
            )

        setattr(self, 'file_local_path', str(dsf.file_local_name))

        return dsf, exists

    def ds_store_file(self, file_storage, location, is_ioc, password):
        if file_storage is None:
            raise marshmallow.exceptions.ValidationError(
                "Not file provided",
                field_name='file_content'
            )

        if not file_storage.filename:
            return None

        passwd = None

        try:
            if is_ioc and not password:
                passwd = 'infected'
            elif password:
                passwd = password

            if passwd is not None:
                try:

                    temp_location = Path('/tmp/') / location.name
                    file_storage.save(temp_location)
                    file_hash = file_sha256sum(temp_location)
                    file_size = temp_location.stat().st_size

                    temp_location = temp_location.rename(Path('/tmp/') / file_hash)

                    pyminizip.compress(temp_location.as_posix(), None, location.as_posix() + '.zip', passwd, 0)

                    Path(temp_location).unlink()

                    file_path = location.as_posix() + '.zip'

                except Exception as e:
                    raise marshmallow.exceptions.ValidationError(
                        str(e),
                        field_name='file_password'
                    )

            else:
                file_storage.save(location)
                file_path = location.as_posix()
                file_size = location.stat().st_size
                file_hash = file_sha256sum(file_path)

        except Exception as e:
            raise marshmallow.exceptions.ValidationError(
                str(e),
                field_name='file_content'
            )

        if location is None:
            raise marshmallow.exceptions.ValidationError(
                f"Unable to save file in target location",
                field_name='file_content'
            )

        setattr(self, 'file_local_path', str(location))

        return file_path, file_size, file_hash


class AssetSchema(ma.SQLAlchemyAutoSchema):
    csrf_token = fields.String(required=False)
    asset_name = auto_field('asset_name', required=True, validate=Length(min=2), allow_none=False)
    asset_description = auto_field('asset_description', required=True, validate=Length(min=2), allow_none=False)
    asset_icon_compromised = auto_field('asset_icon_compromised')
    asset_icon_not_compromised = auto_field('asset_icon_not_compromised')

    class Meta:
        model = AssetsType
        load_instance = True

    @post_load
    def verify_unique(self, data, **kwargs):
        client = AssetsType.query.filter(
            func.lower(AssetsType.asset_name) == func.lower(data.asset_name),
            AssetsType.asset_id != data.asset_id
        ).first()
        if client:
            raise marshmallow.exceptions.ValidationError(
                "Asset type name already exists",
                field_name="asset_name"
            )

        return data

    def load_store_icon(self, file_storage, type):
        if not file_storage.filename:
            return None

        fpath, message = store_icon(file_storage)

        if fpath is None:
            raise marshmallow.exceptions.ValidationError(
                message,
                field_name=type
            )

        setattr(self, type, fpath)

        return fpath


class ServerSettingsSchema(ma.SQLAlchemyAutoSchema):
    http_proxy = auto_field('http_proxy', required=False, allow_none=False)
    https_proxy = auto_field('https_proxy', required=False, allow_none=False)
    prevent_post_mod_repush = auto_field('prevent_post_mod_repush', required=False)

    class Meta:
        model = ServerSettings
        load_instance = True


class ContactSchema(ma.SQLAlchemyAutoSchema):
    contact_name = auto_field('contact_name', required=True, validate=Length(min=2), allow_none=False)
    contact_email = auto_field('contact_email', required=False, allow_none=False)
    contact_work_phone = auto_field('contact_work_phone', required=False, allow_none=False)
    contact_mobile_phone = auto_field('contact_mobile_phone', required=False, allow_none=False)
    contact_role = auto_field('contact_role', required=False, allow_none=False)
    contact_note = auto_field('contact_note', required=False, allow_none=False)
    client_id = auto_field('client_id', required=True)

    class Meta:
        model = Contact
        load_instance = True


class IocTypeSchema(ma.SQLAlchemyAutoSchema):
    type_name = auto_field('type_name', required=True, validate=Length(min=2), allow_none=False)
    type_description = auto_field('type_description', required=True, validate=Length(min=2), allow_none=False)
    type_taxonomy = auto_field('type_taxonomy')
    type_validation_regex = auto_field('type_validation_regex')
    type_validation_expect = auto_field('type_validation_expect')

    class Meta:
        model = IocType
        load_instance = True

    @post_load
    def verify_unique(self, data, **kwargs):
        client = IocType.query.filter(
            func.lower(IocType.type_name) == func.lower(data.type_name),
            IocType.type_id != data.type_id
        ).first()
        if client:
            raise marshmallow.exceptions.ValidationError(
                "IOC type name already exists",
                field_name="type_name"
            )

        return data


class CaseSchema(ma.SQLAlchemyAutoSchema):
    case_name = auto_field('name', required=True, validate=Length(min=2), allow_none=False)
    case_description = auto_field('description', required=True, validate=Length(min=2))
    case_soc_id = auto_field('soc_id', required=True)
    case_customer = auto_field('client_id', required=True)
    case_organisations = fields.List(fields.Integer, required=False)
    protagonists = fields.List(fields.Dict, required=False)
    case_tags = fields.String(required=False)
    csrf_token = fields.String(required=False)

    class Meta:
        model = Cases
        include_fk = True
        load_instance = True
        exclude = ['name', 'description', 'soc_id', 'client_id']

    @pre_load
    def verify_customer(self, data, **kwargs):
        client = Client.query.filter(Client.client_id == data.get('case_customer')).first()
        if client:
            return data

        raise marshmallow.exceptions.ValidationError("Invalid client id",
                                                     field_name="case_customer")

    @post_load
    def custom_attributes_merge(self, data, **kwargs):
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('case_id'), 'case')

        return data


class GlobalTasksSchema(ma.SQLAlchemyAutoSchema):
    task_id = auto_field('id')
    task_assignee_id = auto_field('task_assignee_id', required=True, allow_None=False)
    task_title = auto_field('task_title', required=True, validate=Length(min=2), allow_none=False)
    csrf_token = fields.String(required=False)

    class Meta:
        model = GlobalTasks
        include_fk = True
        load_instance = True
        exclude = ['id']

    @pre_load
    def verify_data(self, data, **kwargs):
        user = User.query.filter(User.id == data.get('task_assignee_id')).count()
        if not user:
            raise marshmallow.exceptions.ValidationError("Invalid user id for assignee",
                                                         field_name="task_assignees_id")

        status = TaskStatus.query.filter(TaskStatus.id == data.get('task_status_id')).count()
        if not status:
            raise marshmallow.exceptions.ValidationError("Invalid task status ID",
                                                         field_name="task_status_id")

        return data


class CustomerSchema(ma.SQLAlchemyAutoSchema):
    customer_name = auto_field('name', required=True, validate=Length(min=2), allow_none=False)
    customer_description = auto_field('description', allow_none=True)
    customer_sla = auto_field('sla', allow_none=True)
    customer_id = auto_field('client_id')
    csrf_token = fields.String(required=False)

    class Meta:
        model = Client
        load_instance = True
        exclude = ['name', 'client_id', 'description', 'sla']

    @post_load
    def verify_unique(self, data, **kwargs):
        client = Client.query.filter(
            func.upper(Client.name) == data.name.upper(),
            Client.client_id != data.client_id
        ).first()
        if client:
            raise marshmallow.exceptions.ValidationError(
                "Customer already exists",
                field_name="customer_name"
            )

        return data

    @post_load
    def custom_attributes_merge(self, data, **kwargs):
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('client_id'), 'client')

        return data


class TaskLogSchema(ma.Schema):
    log_content = fields.String(required=False, validate=Length(min=1))
    csrf_token = fields.String(required=False)


class CaseTaskSchema(ma.SQLAlchemyAutoSchema):
    task_title = auto_field('task_title', required=True, validate=Length(min=2), allow_none=False)
    task_status_id = auto_field('task_status_id', required=True)

    class Meta:
        model = CaseTasks
        load_instance = True
        include_fk = True

    @pre_load
    def verify_data(self, data, **kwargs):
        status = TaskStatus.query.filter(TaskStatus.id == data.get('task_status_id')).count()
        if not status:
            raise marshmallow.exceptions.ValidationError("Invalid task status ID",
                                                         field_name="task_status_id")

        return data

    @post_load
    def custom_attributes_merge(self, data, **kwargs):
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('id'), 'task')

        return data


class CaseEvidenceSchema(ma.SQLAlchemyAutoSchema):
    filename = auto_field('filename', required=True, validate=Length(min=2), allow_none=False)

    class Meta:
        model = CaseReceivedFile
        load_instance = True

    @post_load
    def custom_attributes_merge(self, data, **kwargs):
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('id'), 'evidence')

        return data


class AuthorizationGroupSchema(ma.SQLAlchemyAutoSchema):
    group_name = auto_field('group_name', required=True, validate=Length(min=2), allow_none=False)
    group_description = auto_field('group_description', required=True, validate=Length(min=2))
    group_auto_follow_access_level = auto_field('group_auto_follow_access_level', required=False, default=False)

    class Meta:
        model = Group
        load_instance = True

    @pre_load
    def verify_unique(self, data, **kwargs):
        groups = Group.query.filter(
            func.upper(Group.group_name) == data.get('group_name').upper()
        ).all()

        for group in groups:
            if data.get('group_id') is None or group.group_id != data.get('group_id'):
                raise marshmallow.exceptions.ValidationError(
                    "Group already exists",
                    field_name="group_name"
                )

        return data

    @pre_load
    def parse_permissions(self, data, **kwargs):
        permissions = data.get('group_permissions')
        if type(permissions) != list and not isinstance(permissions, type(None)):
            permissions = [permissions]

        if permissions is not None:
            data['group_permissions'] = ac_mask_from_val_list(permissions)

        else:
            data['group_permissions'] = 0

        return data


class AuthorizationOrganisationSchema(ma.SQLAlchemyAutoSchema):
    org_name = auto_field('org_name', required=True, validate=Length(min=2), allow_none=False)
    org_description = auto_field('org_description', required=True, validate=Length(min=2))

    class Meta:
        model = Organisation
        load_instance = True

    @pre_load
    def verify_unique(self, data, **kwargs):
        organisations = Organisation.query.filter(
            func.upper(Organisation.org_name) == data.get('org_name').upper()
        ).all()

        for organisation in organisations:
            if data.get('org_id') is None or organisation.org_id != data.get('org_id'):
                raise marshmallow.exceptions.ValidationError(
                    "Organisation name already exists",
                    field_name="org_name"
                )

        return data


class UserSchema(ma.SQLAlchemyAutoSchema):
    user_roles_str = fields.List(fields.String, required=False)
    user_name = auto_field('name', required=True, validate=Length(min=2))
    user_login = auto_field('user', required=True, validate=Length(min=2))
    user_email = auto_field('email', required=True, validate=Length(min=2))
    user_password = auto_field('password', required=True, validate=Length(min=2))
    user_isadmin = fields.Boolean(required=True)
    csrf_token = fields.String(required=False)
    user_id = fields.Integer(required=False)
    user_primary_organisation_id = fields.Integer(required=False)

    class Meta:
        model = User
        load_instance = True
        include_fk = True
        exclude = ['api_key', 'password', 'ctx_case', 'ctx_human_case', 'user', 'name', 'email']

    @pre_load()
    def verify_username(self, data, **kwargs):
        user = data.get('user_login')
        user_id = data.get('user_id')
        luser = User.query.filter(
            User.user == user
        ).all()
        for usr in luser:
            if usr.id != user_id:
                raise marshmallow.exceptions.ValidationError('User name already taken',
                                                             field_name="user_login")

        return data

    @pre_load()
    def verify_email(self, data, **kwargs):
        email = data.get('user_email')
        user_id = data.get('user_id')
        luser = User.query.filter(
            User.email == email
        ).all()
        for usr in luser:
            if usr.id != user_id:
                raise marshmallow.exceptions.ValidationError('User email already taken',
                                                             field_name="user_email")

        return data

    @pre_load()
    def verify_password(self, data, **kwargs):
        server_settings = ServerSettings.query.first()
        password = data.get('user_password')
        if data.get('user_password') == '' and data.get('user_id') != 0:
            # Update
            data.pop('user_password')

        else:
            password_error = ""
            if len(password) < server_settings.password_policy_min_length:
                password_error += f"Password must be longer than {server_settings.password_policy_min_length} characters. "

            if server_settings.password_policy_upper_case:
                if not any(char.isupper() for char in password):
                    password_error += "Password must contain uppercase char. "

            if server_settings.password_policy_lower_case:
                if not any(char.islower() for char in password):
                    password_error += "Password must contain lowercase char. "

            if server_settings.password_policy_digit:
                if not any(char.isdigit() for char in password):
                    password_error += "Password must contain digit. "

            if len(server_settings.password_policy_special_chars) > 0:
                if not any(char in server_settings.password_policy_special_chars for char in password):
                    password_error += f"Password must contain a special char [{server_settings.password_policy_special_chars}]. "

            if len(password_error) > 0:
                raise marshmallow.exceptions.ValidationError(password_error,
                                                             field_name="user_password")

        return data
