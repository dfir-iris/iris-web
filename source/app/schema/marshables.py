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
import os
import pyminizip
import random
import re
import shutil
import string
import tempfile
from flask import current_app
from marshmallow import EXCLUDE
from marshmallow import fields
from marshmallow import post_dump
from marshmallow import post_load
from marshmallow import pre_load
from marshmallow.exceptions import ValidationError
from marshmallow.validate import Length
from marshmallow_sqlalchemy import auto_field
from pathlib import Path
from sqlalchemy import func
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from app.business.customers import customers_exists_another_with_same_name
from app.db import db
from app import ma
from app.blueprints.iris_user import iris_current_user
from app.logger import logger
from app.datamgmt.datastore.datastore_db import datastore_get_standard_path
from app.datamgmt.manage.manage_attribute_db import merge_custom_attributes
from app.datamgmt.manage.manage_tags_db import add_db_tag
from app.datamgmt.case.case_iocs_db import get_ioc_links
from app.datamgmt.case.case_tasks_db import get_task_assignees
from app.iris_engine.access_control.utils import ac_mask_from_val_list
from app.models.models import SavedFilter
from app.models.models import DataStorePath
from app.models.models import IrisModuleHook
from app.models.models import Tags
from app.models.models import ReviewStatus
from app.models.evidences import EvidenceTypes, CaseReceivedFile
from app.models.models import NoteDirectory
from app.models.models import NoteRevisions
from app.models.assets import AssetsType, CaseAssets, AnalysisStatus
from app.models.models import CaseTasks
from app.models.cases import Cases, CaseStatus, CaseClassification
from app.models.cases import CasesEvent
from app.models.customers import Client
from app.models.comments import Comments
from app.models.models import Contact
from app.models.models import DataStoreFile
from app.models.models import EventCategory
from app.models.models import GlobalTasks
from app.models.iocs import Ioc
from app.models.models import IocType
from app.models.models import IrisModule
from app.models.models import Notes
from app.models.models import NotesGroup
from app.models.models import ServerSettings
from app.models.models import TaskStatus
from app.models.iocs import Tlp
from app.models.alerts import Alert
from app.models.alerts import Severity
from app.models.alerts import AlertStatus
from app.models.alerts import AlertResolutionStatus
from app.models.alert_clusters import AlertCluster
from app.models.alert_clusters import AlertClusterStatus
from app.models.cluster_rules import ClusterRule
from app.models.cluster_rules import RULE_ACTION_CREATE_CLUSTER
from app.models.investigation_flows import InvestigationFlow
from app.models.investigation_flows import InvestigationFlowStep
from app.models.investigation_flows import AlertInvestigationProgress
from app.models.investigation_flows import AlertClusterInvestigationProgress
from app.models.authorization import Group
from app.models.authorization import Organisation
from app.models.authorization import User
from app.models.cases import CaseState
from app.models.cases import CaseProtagonist
from app.schema.utils import assert_type_mml
from app.schema.utils import file_sha256sum
from app.schema.utils import stream_sha256sum
from app.schema.utils import str_to_bool
from app.business.users import get_primary_organisation
from app.business.users import get_organisations
from app.datamgmt.case.assets_type import get_asset_type_by_name_case_insensitive
from app.iris_engine.access_control.utils import ac_get_fast_user_cases_access


ALLOWED_EXTENSIONS = {'png', 'svg'}
POSTGRES_INT_MAX = 2147483647
POSTGRES_BIGINT_MAX = 9223372036854775807


def allowed_file_icon(filename: str):
    """
    Checks if the file extension of the given filename is allowed.

    Args:
        filename (str): The name of the file to check.

    Returns:
        bool: True if the filename has an extension and the extension is in the ALLOWED_EXTENSIONS set, False otherwise.
    """
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_random_string(length: int) -> str:
    """
    Generates a random string of lowercase letters.

    Args:
        length (int): The length of the string to generate.

    Returns:
        str: A random string of lowercase letters with the given length.
    """
    letters = string.ascii_lowercase
    result_str = ''.join(random.choice(letters) for i in range(length))
    return result_str


def _is_valid_icon_content(file_storage: FileStorage) -> bool:
    """Validate the file content against its declared icon type (magic bytes).

    PNG is verified by its signature. SVG is XML text, so we check it starts with an
    XML/SVG declaration. The stream is rewound so the caller can still save it.
    Returns True if the content matches a supported icon type.
    """
    try:
        header = file_storage.stream.read(512)
        file_storage.stream.seek(0)
    except Exception:
        return False

    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True

    try:
        text = header.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        return False

    stripped = text.lstrip('\ufeff').lstrip()
    if stripped.startswith('<?xml') or stripped.startswith('<svg'):
        return True

    return False


def store_icon(file):
    """Stores an icon file.

    This function stores an icon file in the asset store path and creates a symlink to it in the asset show path.
    The file is saved with a randomly generated filename. If the file is not valid or its filetype is not allowed,
    the function returns an error message.

    Args:
        file: The icon file to store.

    Returns:
        A tuple containing the filename of the stored file (or None if an error occurred) and a message.

    """
    if not file:
        return None, 'Icon file is not valid'

    if not allowed_file_icon(file.filename):
        return None, 'Icon filetype is not allowed'

    if not _is_valid_icon_content(file):
        return None, 'Icon content does not match an allowed filetype'

    # Preserve the original (sanitized) filename so icons are recognizable when reused.
    original = secure_filename(file.filename)
    if not original or '.' not in original:
        original = get_random_string(18)
    base, ext = original.rsplit('.', 1)
    ext = ext.lower()

    store_dir = current_app.config['ASSET_STORE_PATH']
    show_dir = os.path.join(current_app.config['APP_PATH'],
                            current_app.config['ASSET_SHOW_PATH'].strip(os.path.sep))

    def _icon_path(candidate: str):
        return (os.path.join(store_dir, candidate), os.path.join(show_dir, candidate))

    filename = f"{base}.{ext}"
    store_fullpath, show_fullpath = _icon_path(filename)
    counter = 1
    while os.path.exists(store_fullpath) or os.path.lexists(show_fullpath):
        filename = f"{base}_{counter}.{ext}"
        store_fullpath, show_fullpath = _icon_path(filename)
        counter += 1

    try:
        file.save(store_fullpath)
        if os.path.lexists(show_fullpath):
            os.unlink(show_fullpath)
        os.symlink(store_fullpath, show_fullpath)

    except Exception as e:
        return None, f"Unable to add icon {e}"

    return filename, 'Saved'


class CaseNoteDirectorySchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseNoteDirectory objects.

    This schema defines the fields to include when serializing and deserializing CaseNoteDirectory objects.
    It includes fields for the CSRF token, directory name, directory description, and directory ID.
    It also includes a method for verifying the directory name.

    """

    class Meta:
        model = NoteDirectory
        load_instance = True
        include_fk = True
        unknown = EXCLUDE

    def verify_parent_id(self, parent_id, case_id, current_id=None):

        if current_id is not None and int(parent_id) == int(current_id):
            raise ValidationError('Invalid parent id for the directory', field_name='parent_id')
        directory = NoteDirectory.query.filter(
            NoteDirectory.id == parent_id,
            NoteDirectory.case_id == case_id
        ).first()
        if directory:
            if current_id is not None and directory.parent_id == int(current_id):
                raise ValidationError('Invalid parent id for the directory', field_name='parent_id')
            return parent_id

        raise ValidationError('Invalid parent id for the directory', field_name='parent_id')

    @pre_load
    def verify_directory_name(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the directory name is unique.

        This method verifies that the directory name specified in the data is unique. If the directory name is not
        unique, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the directory name is not unique.

        """
        assert_type_mml(input_var=data.get('name'),
                        field_name="name",
                        type=str,
                        allow_none=True)

        assert_type_mml(input_var=data.get('parent_id'),
                        field_name="parent_id",
                        type=int,
                        allow_none=True)

        return data


class SearchCaseNoteDirectorySchema(CaseNoteDirectorySchema):
    """Schema for serializing and deserializing SearchCaseNoteDirectory objects.

    This schema defines the fields to include when serializing and deserializing CaseNoteDirectory objects.
    It includes fields for the CSRF token, directory name, directory description, and directory ID.
    It also includes a method for verifying the directory name.

    """

    note_count: int = fields.Integer(required=False)
    subdirectories: List[str] = fields.List(fields.String, required=False)
    notes:  List[str] = fields.List(fields.String, required=False)


class UserSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing User objects.

    This schema defines the fields to include when serializing and deserializing User objects.
    It includes fields for the user's name, login, email, password, admin status, CSRF token, ID, primary organization ID,
    and service account status. It also includes methods for verifying the username, email, and password.

    """
    user_roles_str: List[str] = fields.List(fields.String, required=False)
    user_name: str = auto_field('name', required=True, validate=Length(min=2))
    user_login: str = auto_field('user', required=True, validate=Length(min=2))
    user_email: str = auto_field('email', required=True, validate=Length(min=2))
    user_password: Optional[str] = auto_field('password', required=False, load_only=True)
    user_isadmin: bool = fields.Boolean(required=True)
    user_id: Optional[int] = fields.Integer(required=False)
    user_primary_organisation_id: Optional[int] = fields.Integer(required=False)
    user_is_service_account: Optional[bool] = auto_field('is_service_account', required=False)

    class Meta:
        model = User
        load_instance = True
        include_fk = True
        # `avatar_blob` is bytes — never serialise it through JSON;
        # the actual image is fetched lazily from
        # `/api/v2/users/<id>/avatar`. `avatar_mime` is an
        # implementation detail, also dropped. `avatar_updated_at`
        # passes through so the SPA can cache-bust the avatar URL.
        exclude = ['api_key', 'password', 'ctx_case', 'ctx_human_case', 'user', 'name', 'email',
                   'is_service_account', 'mfa_secrets', 'webauthn_credentials',
                   'avatar_blob', 'avatar_mime',
                   # `preferences` has its own dedicated endpoints — no
                   # reason to ship a potentially large JSONB blob on
                   # every user serialisation.
                   'preferences']
        unknown = EXCLUDE

    @pre_load()
    def verify_username(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the username is not already taken.

        This method verifies that the specified username is not already taken by another user. If the username is already
        taken, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the username is already taken.

        """
        user = data.get('user_login')
        user_id = data.get('user_id')

        assert_type_mml(input_var=user_id,
                        field_name="user_id",
                        type=int,
                        allow_none=True)

        assert_type_mml(input_var=user,
                        field_name="user_login",
                        type=str,
                        allow_none=True)

        luser = User.query.filter(
            User.user == user
        ).all()
        for usr in luser:
            if usr.id != user_id:
                raise ValidationError('User name already taken', field_name="user_login")

        return data

    @pre_load()
    def verify_email(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the email is not already taken.

        This method verifies that the specified email is not already taken by another user. If the email is already
        taken, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the email is already taken.

        """
        email = data.get('user_email')
        user_id = data.get('user_id')

        assert_type_mml(input_var=user_id,
                        field_name="user_id",
                        type=int,
                        allow_none=True)

        assert_type_mml(input_var=email,
                        field_name="user_email",
                        type=str,
                        allow_none=True)

        luser = User.query.filter(
            User.email == email
        ).all()
        for usr in luser:
            if usr.id != user_id:
                raise ValidationError('User email already taken', field_name="user_email")

        return data

    @pre_load()
    def verify_password(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the password meets the server's password policy.

        This method verifies that the specified password meets the server's password policy. If the password does not
        meet the policy, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the password does not meet the server's password policy.

        """
        server_settings = ServerSettings.query.first()
        password = data.get('user_password')

        if (password == '' or password is None) and str_to_bool(data.get('user_is_service_account')) is True:
            return data

        if (password == '' or password is None) and data.get('user_id') != 0:
            # Update
            data.pop('user_password') if 'user_password' in data else None

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
                raise ValidationError(password_error, field_name="user_password")

        return data


class CommentSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Comment objects.

    This schema defines the fields to include when serializing and deserializing Comment objects.
    It includes fields for the comment ID, the user who made the comment, the comment text, and the timestamp of the comment.

    """
    user = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'])

    class Meta:
        model = Comments
        load_instance = True
        include_fk = True
        unknown = EXCLUDE


class CaseNoteRevisionSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseNoteVersion objects."""
    user_name = fields.String()

    class Meta:
        model = NoteRevisions
        load_instance = True
        include_fk = True
        unknown = EXCLUDE


class CaseNoteSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseNote objects.

    This schema defines the fields to include when serializing and deserializing CaseNote objects.
    It includes fields for the CSRF token, group ID, group UUID, and group title.

    """
    comments = fields.Nested('CommentSchema', many=True)
    directory = fields.Nested('CaseNoteDirectorySchema', many=False)

    class Meta:
        model = Notes
        load_instance = True
        include_fk = True
        unknown = EXCLUDE

    def verify_directory_id(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the directory ID is valid.

        This method verifies that the directory ID specified in the data is valid for the case ID specified in kwargs.
        If the group ID is valid, it returns the data. Otherwise, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments, including the case ID.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the directory ID is invalid.

        """
        assert_type_mml(input_var=data.get('directory_id'),
                        field_name='directory_id',
                        type=int)

        directory = NoteDirectory.query.filter(
            NoteDirectory.id == data.get('directory_id'),
            NoteDirectory.case_id == kwargs.get('caseid')
        ).first()
        if directory:
            return data

        raise ValidationError("Invalid directory id for the case", field_name="directory_id")

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes.

        This method merges any custom attributes specified in the data with the existing custom attributes for the note.
        If there are no custom attributes specified, it returns the data unchanged.

        Args:
            data: The data to merge.
            kwargs: Additional keyword arguments.

        Returns:
            The merged data.

        """
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            assert_type_mml(input_var=data.get('note_id'),
                            field_name="note_id",
                            type=int,
                            allow_none=True)

            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('note_id'), 'note')

        return data


class CaseAddNoteSchema(ma.Schema):
    """Schema for serializing and deserializing CaseNote objects.

    This schema defines the fields to include when serializing and deserializing CaseNote objects.
    It includes fields for the note ID, note title, note content, group ID, CSRF token, and custom attributes.
    It also includes a method for verifying the group ID and a post-load method for merging custom attributes.

    """
    note_id: int = fields.Integer(required=False)
    note_title: str = fields.String(required=True, validate=Length(min=1, max=154), allow_none=False)
    note_content: str = fields.String(required=False)
    custom_attributes: Dict[str, Any] = fields.Dict(required=False)

    def verify_directory_id(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the directory ID is valid.

        This method verifies that the directory ID specified in the data is valid for the case ID specified in kwargs.
        If the group ID is valid, it returns the data. Otherwise, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments, including the case ID.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the directory ID is invalid.

        """
        assert_type_mml(input_var=data.get('directory_id'),
                        field_name="directory_id",
                        type=int)

        directory = NoteDirectory.query.filter(
            NoteDirectory.id == data.get('directory_id'),
            NoteDirectory.case_id == kwargs.get('caseid')
        ).first()
        if directory:
            return data

        raise ValidationError("Invalid directory id for the case", field_name="directory_id")

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes.

        This method merges any custom attributes specified in the data with the existing custom attributes for the note.
        If there are no custom attributes specified, it returns the data unchanged.

        Args:
            data: The data to merge.
            kwargs: Additional keyword arguments.

        Returns:
            The merged data.

        """
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            assert_type_mml(input_var=data.get('note_id'),
                            field_name="note_id",
                            type=int,
                            allow_none=True)

            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('note_id'), 'note')

        return data


class CaseGroupNoteSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing NotesGroup objects.

    This schema defines the fields to include when serializing and deserializing NotesGroup objects.
    It includes fields for the group ID, group UUID, group title, and the notes associated with the group.

    """

    class Meta:
        model = NotesGroup
        load_instance = True
        unknown = EXCLUDE


class AssetTypeSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing AssetsType objects.

    This schema defines the fields to include when serializing and deserializing AssetsType objects.
    It includes fields for the CSRF token, asset name, asset description, and asset icons for both compromised and
    not compromised states. It also includes a method for verifying that the asset name is unique and a method for
    loading and storing asset icons.

    """
    asset_name: str = auto_field('asset_name', required=True, validate=Length(min=2), allow_none=False)
    asset_description: str = auto_field('asset_description', required=True, validate=Length(min=2), allow_none=False)
    asset_icon_compromised: str = auto_field('asset_icon_compromised')
    asset_icon_not_compromised: str = auto_field('asset_icon_not_compromised')

    class Meta:
        model = AssetsType
        load_instance = True
        unknown = EXCLUDE

    @post_load
    def verify_unique(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the asset name is unique.

        This method verifies that the asset name specified in the data is unique. If the asset name is not unique,
        it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the asset name is not unique.

        """

        assert_type_mml(input_var=data.asset_name,
                        field_name='asset_name',
                        type=str)

        assert_type_mml(input_var=data.asset_id,
                        field_name='asset_id',
                        type=int,
                        allow_none=True)

        asset_type = get_asset_type_by_name_case_insensitive(data.asset_name)
        if asset_type and asset_type.asset_id != data.asset_id:
            raise ValidationError('Asset type name already exists', field_name='asset_name')

        return data

    def load_store_icon(self, file_storage: Any, field_type: str) -> Optional[str]:
        """Loads and stores an asset icon.

        This method loads and stores an asset icon from the specified file storage. If the file storage is not valid
        or its filetype is not allowed, it raises a validation error.

        Args:
            file_storage: The file storage containing the asset icon.
            field_type: The type of asset icon to load and store.

        Returns:
            The filename of the stored asset icon, or None if an error occurred.

        Raises:
            ValidationError: If the file storage is not valid or its filetype is not allowed.

        """
        if not file_storage or not file_storage.filename:
            return None

        fpath, message = store_icon(file_storage)

        if fpath is None:
            raise ValidationError(message, field_name=field_type)

        setattr(self, field_type, fpath)

        return fpath


class CaseAssetsSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseAssets objects.

    This schema defines the fields to include when serializing and deserializing CaseAssets objects.
    It includes fields for the asset name, IOC links, asset enrichment, asset type, and custom attributes.
    It also includes methods for verifying the asset type ID and analysis status ID, and for merging custom attributes.

    """
    asset_name: str = auto_field('asset_name', required=True, allow_none=False)
    asset_type_id: str = auto_field('asset_type_id', required=True, allow_none=False)
    ioc_links: List[int] = fields.List(fields.Integer, required=False)
    asset_enrichment: str = auto_field('asset_enrichment', required=False)
    asset_type: AssetTypeSchema = ma.Nested(AssetTypeSchema, required=False)
    alerts = fields.Nested('AlertSchema', many=True, exclude=['assets'])
    analysis_status = fields.Nested('AnalysisStatusSchema', required=False)
    iocs = fields.Nested('IocSchemaForAPIV2', many=True, only=['ioc_id'])

    class Meta:
        model = CaseAssets
        sqla_session = db.session
        include_fk = True
        load_instance = True
        unknown = EXCLUDE

    @staticmethod
    def is_unique_for_cid(case_id, request_data):
        """
        Check if the asset is unique for the customer
        """

        asset = CaseAssets.query.filter(
            func.lower(CaseAssets.asset_name) == func.lower(request_data.get('asset_name')),
            CaseAssets.asset_type_id == request_data.get('asset_type_id'),
            CaseAssets.asset_id != request_data.get('asset_id'),
            CaseAssets.case_id == case_id
        ).first()

        if asset is not None:
            raise ValidationError('Asset name already exists in this case', field_name='asset_name')

        return True

    @pre_load
    def verify_data(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies the asset type ID and analysis status ID.

        This method verifies that the asset type ID and analysis status ID specified in the data are valid.
        If either ID is invalid, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If either ID is invalid.

        """
        if data.get('asset_type_id'):
            assert_type_mml(input_var=data.get('asset_type_id'),
                            field_name="asset_type_id",
                            type=int)

            asset_type = AssetsType.query.filter(AssetsType.asset_id == data.get('asset_type_id')).count()
            if not asset_type:
                raise ValidationError("Invalid asset type ID", field_name="asset_type_id")

        if data.get('analysis_status_id'):
            assert_type_mml(input_var=data.get('analysis_status_id'),
                            field_name="analysis_status_id", type=int,
                            allow_none=True)

        if data.get('analysis_status_id'):
            status = AnalysisStatus.query.filter(AnalysisStatus.id == data.get('analysis_status_id')).count()
            if not status:
                raise ValidationError("Invalid analysis status ID", field_name="analysis_status_id")

        if data.get('asset_tags'):
            for tag in data.get('asset_tags').split(','):
                if not isinstance(tag, str):
                    raise ValidationError("All items in list must be strings", field_name="asset_tags")
                add_db_tag(tag.strip())

        return data

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes.

        This method merges any custom attributes specified in the data with the existing custom attributes for the asset.
        If there are no custom attributes specified, it returns the data unchanged.

        Args:
            data: The data to merge.
            kwargs: Additional keyword arguments.

        Returns:
            The merged data.

        """
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            assert_type_mml(input_var=data.get('asset_id'),
                            field_name="asset_id", type=int,
                            allow_none=True)

            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('asset_id'), 'asset')

        return data


class CaseTemplateSchema(ma.Schema):
    """Schema for serializing and deserializing CaseTemplate objects.

    This schema defines the fields to include when serializing and deserializing CaseTemplate objects.
    It includes fields for the template ID, the user ID of the user who created the template, the creation and update
    timestamps, the name, display name, description, author, title prefix, summary, tags, and classification of the
    template. It also includes fields for the tasks and note groups associated with the template, and methods for
    validating the format of the tasks and note groups.

    """
    id: int = fields.Integer(dump_only=True)
    created_by_user_id: int = fields.Integer(required=True)
    created_at: datetime = fields.DateTime(dump_only=True)
    updated_at: datetime = fields.DateTime(dump_only=True)
    name: str = fields.String(required=True)
    display_name: Optional[str] = fields.String(allow_none=True, missing="")
    description: Optional[str] = fields.String(allow_none=True, missing="")
    author: Optional[str] = fields.String(allow_none=True, validate=Length(max=128), missing="")
    title_prefix: Optional[str] = fields.String(allow_none=True, validate=Length(max=32), missing="")
    summary: Optional[str] = fields.String(allow_none=True, missing="")
    tags: Optional[List[str]] = fields.List(fields.String(), allow_none=True, missing=[])
    classification: Optional[str] = fields.String(allow_none=True, missing="")
    note_directories: Optional[List[Dict[str, Union[str, List[Dict[str, str]]]]]] = fields.List(fields.Dict(),
                                                                                                allow_none=True,
                                                                                                missing=[])

    @staticmethod
    def validate_string_or_list(value: Union[str, List[str]]) -> Union[str, List[str]]:
        """Validates that a value is a string or a list of strings.

        This method validates that a value is either a string or a list of strings. If the value is a list, it also
        validates that all items in the list are strings.

        Args:
            value: The value to validate.

        Returns:
            The validated value.

        Raises:
            ValidationError: If the value is not a string or a list of strings.

        """
        if not isinstance(value, (str, list)):
            raise ValidationError('Value must be a string or a list of strings')
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    raise ValidationError('All items in list must be strings')
        return value

    @staticmethod
    def validate_string_or_list_of_dict(value: Union[str, List[Dict[str, str]]]) -> Union[str, List[Dict[str, str]]]:
        """Validates that a value is a string or a list of dictionaries with string values.

        This method validates that a value is either a string or a list of dictionaries with string values. If the value
        is a list, it also validates that all items in the list are dictionaries with string values.

        Args:
            value: The value to validate.

        Returns:
            The validated value.

        Raises:
            ValidationError: If the value is not a string or a list of dictionaries with string values.

        """
        if not isinstance(value, (str, list)):
            raise ValidationError('Value must be a string or a list of strings')
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    raise ValidationError('All items in list must be dict')
                for ivalue in item.values():
                    if not isinstance(ivalue, str):
                        raise ValidationError('All items in dict must be str')
        return value

    tasks: Optional[List[Dict[str, Union[str, List[str]]]]] = fields.List(
        fields.Dict(keys=fields.Str(), values=fields.Raw(validate=[validate_string_or_list])),
        allow_none=True,
        missing=[]
    )


class IocTypeSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing IocType objects.

    This schema defines the fields to include when serializing and deserializing IocType objects.
    It includes fields for the IOC type name, description, taxonomy, validation regex, and validation expectation.
    It also includes a method for verifying that the IOC type name is unique.

    """
    type_name: str = auto_field('type_name', required=True, validate=Length(min=2), allow_none=False)
    type_description: str = auto_field('type_description', required=True, validate=Length(min=2), allow_none=False)
    type_taxonomy: Optional[str] = auto_field('type_taxonomy')
    type_validation_regex: Optional[str] = auto_field('type_validation_regex')
    type_validation_expect: Optional[str] = auto_field('type_validation_expect')

    class Meta:
        model = IocType
        load_instance = True
        unknown = EXCLUDE

    @post_load
    def verify_unique(self, data: IocType, **kwargs: Any) -> IocType:
        """Verifies that the IOC type name is unique.

        This method verifies that the IOC type name specified in the data is unique.
        If the name is not unique, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the IOC type name is not unique.

        """
        client = IocType.query.filter(
            func.lower(IocType.type_name) == func.lower(data.type_name),
            IocType.type_id != data.type_id
        ).first()
        if client:
            raise ValidationError("IOC type name already exists", field_name="type_name")

        return data


class TlpSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Tlp
        load_instance = True
        include_fk = True
        unknown = EXCLUDE


# TODO try to remove IocSchema and replace it by this new schema
class IocSchemaForAPIV2(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing IOC objects.

    This schema defines the fields to include when serializing and deserializing IOC objects.
    It includes fields for the IOC value, enrichment data, and the IOC type associated with the IOC.
    It also includes methods for verifying the format of the IOC value and merging custom attributes.

    """
    ioc_value: str = auto_field('ioc_value', required=True, validate=Length(min=1), allow_none=False)
    ioc_enrichment: Optional[Dict[str, Any]] = auto_field('ioc_enrichment', required=False)
    ioc_type: Optional[IocTypeSchema] = ma.Nested(IocTypeSchema, required=False)
    tlp = ma.Nested(TlpSchema)

    def get_link(self, ioc):
        user_search_limitations = ac_get_fast_user_cases_access(iris_current_user.id)
        ial = get_ioc_links(ioc.ioc_id, user_search_limitations)
        return [row._asdict() for row in ial]

    link = ma.Method('get_link')

    class Meta:
        model = Ioc
        sqla_session = db.session
        load_instance = True
        include_fk = True
        unknown = EXCLUDE

    @pre_load
    def verify_data(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies the format of the IOC value and associated IOC type.

        This method verifies that the IOC value specified in the data matches the expected format for the associated
        IOC type. If the value does not match the expected format, it raises a validation error. It also verifies that
        the specified IOC type ID and TLP ID are valid.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the IOC value does not match the expected format or if the specified IOC type ID or
            TLP ID are invalid.

        """
        if data.get('ioc_type_id'):
            assert_type_mml(input_var=data.get('ioc_type_id'), field_name="ioc_type_id", type=int)
            ioc_type = IocType.query.filter(IocType.type_id == data.get('ioc_type_id')).first()
            if not ioc_type:
                raise ValidationError("Invalid IOC type ID", field_name="ioc_type_id")

            if ioc_type.type_validation_regex:
                if not re.fullmatch(ioc_type.type_validation_regex, data.get('ioc_value'), re.IGNORECASE):
                    error = f"The input doesn\'t match the expected format " \
                            f"(expected: {ioc_type.type_validation_expect or ioc_type.type_validation_regex})"
                    raise ValidationError(error, field_name="ioc_ioc_value")

        if data.get('ioc_tlp_id'):
            assert_type_mml(input_var=data.get('ioc_tlp_id'), field_name="ioc_tlp_id", type=int,
                            max_val=POSTGRES_INT_MAX)

            Tlp.query.filter(Tlp.tlp_id == data.get('ioc_tlp_id')).count()

        if data.get('ioc_tags'):
            for tag in data.get('ioc_tags').split(','):
                if not isinstance(tag, str):
                    raise ValidationError("All items in list must be strings", field_name="ioc_tags")
                add_db_tag(tag.strip())

        return data

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes with the IOC data.

        This method merges any custom attributes specified in the data with the IOC data. If no custom attributes are
        specified, it returns the original data.

        Args:
            data: The data to merge.
            kwargs: Additional keyword arguments.

        Returns:
            The merged data.

        """
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            assert_type_mml(input_var=data.get('ioc_id'),
                            field_name="ioc_id",
                            type=int,
                            allow_none=True)

            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('ioc_id'), 'ioc')

        return data


class IocSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing IOC objects.

    This schema defines the fields to include when serializing and deserializing IOC objects.
    It includes fields for the IOC value, enrichment data, and the IOC type associated with the IOC.
    It also includes methods for verifying the format of the IOC value and merging custom attributes.

    """
    ioc_value: str = auto_field('ioc_value', required=True, validate=Length(min=1), allow_none=False)
    ioc_enrichment: Optional[Dict[str, Any]] = auto_field('ioc_enrichment', required=False)
    ioc_type: Optional[IocTypeSchema] = ma.Nested(IocTypeSchema, required=False)

    class Meta:
        model = Ioc
        sqla_session = db.session
        load_instance = True
        include_fk = True
        unknown = EXCLUDE

    @pre_load
    def verify_data(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies the format of the IOC value and associated IOC type.

        This method verifies that the IOC value specified in the data matches the expected format for the associated
        IOC type. If the value does not match the expected format, it raises a validation error. It also verifies that
        the specified IOC type ID and TLP ID are valid.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the IOC value does not match the expected format or if the specified IOC type ID or
            TLP ID are invalid.

        """
        if data.get('ioc_type_id'):
            assert_type_mml(input_var=data.get('ioc_type_id'), field_name='ioc_type_id', type=int)
            ioc_type = IocType.query.filter(IocType.type_id == data.get('ioc_type_id')).first()
            if not ioc_type:
                raise ValidationError('Invalid IOC type ID', field_name='ioc_type_id')

            if ioc_type.type_validation_regex:
                if not re.fullmatch(ioc_type.type_validation_regex, data.get('ioc_value'), re.IGNORECASE):
                    error = f'The input doesn\'t match the expected format ' \
                            f'(expected: {ioc_type.type_validation_expect or ioc_type.type_validation_regex})'
                    raise ValidationError(error, field_name="ioc_ioc_value")

        if data.get('ioc_tlp_id'):
            assert_type_mml(input_var=data.get('ioc_tlp_id'), field_name='ioc_tlp_id', type=int,
                            max_val=POSTGRES_INT_MAX)

            Tlp.query.filter(Tlp.tlp_id == data.get('ioc_tlp_id')).count()

        if data.get('ioc_tags'):
            for tag in data.get('ioc_tags').split(','):
                if not isinstance(tag, str):
                    raise ValidationError('All items in list must be strings', field_name='ioc_tags')
                add_db_tag(tag.strip())

        return data

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes with the IOC data.

        This method merges any custom attributes specified in the data with the IOC data. If no custom attributes are
        specified, it returns the original data.

        Args:
            data: The data to merge.
            kwargs: Additional keyword arguments.

        Returns:
            The merged data.

        """
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            assert_type_mml(input_var=data.get('ioc_id'),
                            field_name="ioc_id",
                            type=int,
                            allow_none=True)

            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('ioc_id'), 'ioc')

        return data


class UserFullSchema(ma.SQLAlchemyAutoSchema):
    """
    Schema for serializing and deserializing User objects.

    This schema defines the fields to include when serializing and deserializing User objects.
    It includes fields for the user's name, login, email, password, admin status, CSRF token, ID, primary organization ID,
    and service account status. It also includes methods for verifying the username, email, and password.
    """

    class Meta:
        model = User
        load_instance = True
        include_fk = True
        exclude = ['password', 'ctx_case', 'ctx_human_case', 'mfa_secrets', 'webauthn_credentials',
                   'avatar_blob', 'avatar_mime',
                   # `preferences` has its own dedicated endpoints.
                   'preferences']
        unknown = EXCLUDE


class EventSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Event objects.

    This schema defines the fields to include when serializing and deserializing Event objects.
    It includes fields for the event ID, event title, assets associated with the event, IOCs associated with the event,
    the date and time of the event, the time zone of the event, the category ID of the event, and the modification history
    of the event.

    """
    event_title: str = auto_field('event_title', required=True, validate=Length(min=2), allow_none=False)
    event_assets: List[int] = fields.List(fields.Integer, required=True, allow_none=False)
    event_iocs: List[int] = fields.List(fields.Integer, required=True, allow_none=False)
    event_date: datetime = fields.DateTime("%Y-%m-%dT%H:%M:%S.%f", required=True, allow_none=False)
    event_tz: str = fields.String(required=True, allow_none=False)
    event_category_id: int = ma.Method('get_event_category_id')
    event_date_wtz: datetime = fields.DateTime("%Y-%m-%dT%H:%M:%S.%f", required=False, allow_none=False)
    modification_history: str = auto_field('modification_history', required=False, readonly=True)
    event_comments_map: List[int] = fields.List(fields.Integer, required=False, allow_none=True)
    event_sync_iocs_assets: bool = fields.Boolean(required=False)
    children = fields.Nested('EventSchema', many=True, required=False)

    class Meta:
        model = CasesEvent
        load_instance = True
        include_fk = True
        unknown = EXCLUDE

    def validate_date(self, event_date: str, event_tz: str):
        """Validates the date and time of the event.

        This method validates the date and time of the event by parsing the date and time string and time zone string
        and returning the parsed date and time as datetime objects.

        Args:
            event_date: The date and time of the event as a string.
            event_tz: The time zone of the event as a string.

        Returns:
            A tuple containing the parsed date and time as datetime objects.

        Raises:
            ValidationError: If the date and time string or time zone string are invalid.

        """
        date_time = f'{event_date}{event_tz}'
        date_time_wtz = f'{event_date}'

        try:
            self.event_date = dateutil.parser.isoparse(date_time)
            self.event_date_wtz = dateutil.parser.isoparse(date_time_wtz)
        except Exception:
            raise ValidationError("Invalid date time", field_name="event_date")

        return self.event_date, self.event_date_wtz

    @pre_load
    def verify_data(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies the data for the event.

        This method verifies that the data for the event is valid by checking that all required fields are present and
        that the specified asset and IOC IDs are valid.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the data is invalid.

        """
        if data is None:
            raise ValidationError('Received empty data')

        for field in ['event_title', 'event_date', 'event_tz', 'event_category_id', 'event_assets', 'event_iocs']:
            if field not in data:
                raise ValidationError(f'Missing field {field}', field_name=field)

        assert_type_mml(input_var=data.get('event_category_id'),
                        field_name='event_category_id',
                        type=int)

        event_cat = EventCategory.query.filter(EventCategory.id == int(data.get('event_category_id'))).count()
        if not event_cat:
            raise ValidationError("Invalid event category ID", field_name="event_category_id")

        assert_type_mml(input_var=data.get('event_assets'),
                        field_name='event_assets',
                        type=list)

        for asset in data.get('event_assets'):

            assert_type_mml(input_var=int(asset),
                            field_name='event_assets',
                            type=int)

            ast = CaseAssets.query.filter(CaseAssets.asset_id == asset).count()
            if not ast:
                raise ValidationError("Invalid assets ID", field_name="event_assets")

        assert_type_mml(input_var=data.get('event_iocs'),
                        field_name='event_iocs',
                        type=list)

        for ioc in data.get('event_iocs'):

            assert_type_mml(input_var=int(ioc),
                            field_name='event_iocs',
                            type=int)

            ast = Ioc.query.filter(Ioc.ioc_id == ioc).count()
            if not ast:
                raise ValidationError("Invalid IOC ID", field_name="event_assets")

        if data.get('event_color') and data.get('event_color') not in ['#fff', '#1572E899', '#6861CE99', '#48ABF799',
                                                                       '#31CE3699', '#F2596199', '#FFAD4699']:
            data['event_color'] = ''

        if data.get('event_tags'):
            for tag in data.get('event_tags').split(','):
                if not isinstance(tag, str):
                    raise ValidationError("All items in list must be strings", field_name="event_tags")
                add_db_tag(tag.strip())

        return data

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes with the event data.

        This method merges any custom attributes specified in the data with the event data. If no custom attributes are
        specified, it returns the original data.

        Args:
            data: The data to merge.
            kwargs: Additional keyword arguments.

        Returns:
            The merged data.

        """
        new_attr = data.get('custom_attributes')
        if new_attr is not None:
            assert_type_mml(input_var=data.get('event_id'),
                            field_name='event_id',
                            type=int,
                            allow_none=True)

            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('event_id'), 'event')

        return data

    def get_event_category_id(self, event):
        if not event.category:
            return None
        return event.category[0].id


class DSPathSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing DataStorePath objects.

    This schema defines the fields to include when serializing and deserializing DataStorePath objects.
    It includes fields for the data store path ID, the data store ID, the path name, and the path description.

    """

    class Meta:
        model = DataStorePath
        load_instance = True
        include_fk = True
        unknown = EXCLUDE


class DSFileSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing DataStoreFile objects.

    This schema defines the fields to include when serializing and deserializing DataStoreFile objects.
    It includes fields for the file ID, the original file name, the file description, and the file content.

    """
    file_original_name: str = auto_field('file_original_name', required=True, validate=Length(min=1), allow_none=False)
    file_description: str = auto_field('file_description', allow_none=False)
    file_content: Optional[bytes] = fields.Raw(required=False)
    file_local_name: Optional[str] = auto_field('file_local_name', required=False, load_only=True)

    class Meta:
        model = DataStoreFile
        include_fk = True
        load_instance = True
        unknown = EXCLUDE

    def ds_store_file_b64(self, filename: str, file_content: bytes, dsp: DataStorePath, cid: int) -> Tuple[
        DataStoreFile, bool]:
        """Stores a file in the data store.

        This method stores a file in the data store. If the file already exists in the data store, it returns the
        existing file. Otherwise, it creates a new file and returns it.

        Args:
            filename: The name of the file.
            file_content: The content of the file.
            dsp: The data store path where the file should be stored.
            cid: The ID of the case associated with the file.

        Returns:
            A tuple containing the DataStoreFile object and a boolean indicating whether the file already existed.

        Raises:
            ValidationError: If there is an error storing the file.

        """
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
                dsf.added_by_user_id = iris_current_user.id
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
            raise ValidationError(str(e), field_name='file_password')

        setattr(self, 'file_local_path', str(dsf.file_local_name))

        return dsf, exists

    def ds_store_file(self, file_storage: FileStorage, location: Path, is_ioc: bool, password: Optional[str]) -> Tuple[
        str, int, str]:
        """Stores a file in the data store.

        This method stores a file in the data store. If the file is an IOC and no password is provided, it uses a default
        password. If a password is provided, it encrypts the file with the password. It returns the path, size, and hash
        of the stored file.

        Args:
            file_storage: The file to store.
            location: The location where the file should be stored.
            is_ioc: Whether the file is an IOC.
            password: The password to use for encrypting the file.

        Returns:
            A tuple containing the path, size, and hash of the stored file.

        Raises:
            ValidationError: If there is an error storing the file.

        """
        if file_storage is None:
            raise ValidationError("No file provided", field_name='file_content')

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
                    with tempfile.NamedTemporaryFile(delete=False) as tmp:
                        file_storage.save(tmp)
                        file_storage.close()

                        fn = tmp

                    file_hash = file_sha256sum(fn.name)
                    file_size = os.stat(fn.name).st_size

                    file_path = location.as_posix() + '.zip'

                    shutil.copyfile(fn.name, Path(fn.name).parent / file_hash)

                    pyminizip.compress((Path(fn.name).parent / file_hash).as_posix(), None, file_path, passwd, 0)
                    os.unlink(Path(tmp.name).parent / file_hash)
                    os.unlink(fn.name)

                except Exception as e:
                    logger.exception(e)
                    raise ValidationError(str(e), field_name='file_password')

            else:
                file_storage.save(location)
                file_storage.close()
                file_path = location.as_posix()
                file_size = location.stat().st_size
                file_hash = file_sha256sum(file_path)

        except Exception as e:
            raise ValidationError(str(e), field_name='file_content')

        if location is None:
            raise ValidationError("Unable to save file in target location", field_name='file_content')

        setattr(self, 'file_local_path', str(location))

        return file_path, file_size, file_hash


class ServerSettingsSchema(ma.SQLAlchemyAutoSchema):
    """Schema for the singleton `ServerSettings` row.

    Every editable column on the model is declared explicitly so the
    SvelteKit `/settings/server` page can introspect the field list
    via `Meta.fields` if it ever needs to. Two columns are intentionally
    excluded from load and load-only respectively:

      * `id` — the row is a singleton anchored at id=1; clients never
        get to touch it.
      * `has_updates_available` — written by the periodic update
        checker, surfaced read-only on the page.
    """
    http_proxy: Optional[str] = fields.String(required=False, allow_none=True)
    https_proxy: Optional[str] = fields.String(required=False, allow_none=True)
    prevent_post_mod_repush: Optional[bool] = fields.Boolean(required=False)
    prevent_post_objects_repush: Optional[bool] = fields.Boolean(required=False)
    has_updates_available: Optional[bool] = fields.Boolean(dump_only=True)
    enable_updates_check: Optional[bool] = fields.Boolean(required=False)
    password_policy_min_length: Optional[int] = fields.Integer(required=False)
    password_policy_upper_case: Optional[bool] = fields.Boolean(required=False)
    password_policy_lower_case: Optional[bool] = fields.Boolean(required=False)
    password_policy_digit: Optional[bool] = fields.Boolean(required=False)
    password_policy_special_chars: Optional[str] = fields.String(required=False, allow_none=True)
    enforce_mfa: Optional[bool] = fields.Boolean(required=False)
    force_confirmation_before_delete: Optional[bool] = fields.Boolean(required=False)

    # ---- Mail — outbound (SMTP) --------------------------------------
    # Passwords are load-only: the GET path must never return the
    # ciphertext (leaking it doesn't leak the plaintext, but it does
    # reveal that the field is set, and future rotation of SECRET_KEY
    # would make the exposure worse). Instead the read path returns a
    # sentinel `_password_set` boolean the SPA uses to render "•••••"
    # placeholders in the form — see `ServerOperations.read_settings`.
    mail_smtp_enabled: Optional[bool] = fields.Boolean(required=False, allow_none=True)
    mail_smtp_host: Optional[str] = fields.String(required=False, allow_none=True)
    mail_smtp_port: Optional[int] = fields.Integer(required=False, allow_none=True)
    mail_smtp_user: Optional[str] = fields.String(required=False, allow_none=True)
    mail_smtp_password: Optional[str] = fields.String(required=False, allow_none=True, load_only=True)
    mail_smtp_use_tls: Optional[bool] = fields.Boolean(required=False, allow_none=True)
    mail_smtp_use_ssl: Optional[bool] = fields.Boolean(required=False, allow_none=True)
    mail_from_address: Optional[str] = fields.String(required=False, allow_none=True)
    mail_from_name: Optional[str] = fields.String(required=False, allow_none=True)

    # ---- Mail — inbound (IMAP) ---------------------------------------
    mail_imap_enabled: Optional[bool] = fields.Boolean(required=False, allow_none=True)
    mail_imap_host: Optional[str] = fields.String(required=False, allow_none=True)
    mail_imap_port: Optional[int] = fields.Integer(required=False, allow_none=True)
    mail_imap_user: Optional[str] = fields.String(required=False, allow_none=True)
    mail_imap_password: Optional[str] = fields.String(required=False, allow_none=True, load_only=True)
    mail_imap_use_ssl: Optional[bool] = fields.Boolean(required=False, allow_none=True)
    mail_imap_mailbox: Optional[str] = fields.String(required=False, allow_none=True)
    mail_imap_poll_interval_sec: Optional[int] = fields.Integer(required=False, allow_none=True)
    mail_imap_max_attachment_mb: Optional[int] = fields.Integer(required=False, allow_none=True)

    class Meta:
        model = ServerSettings
        load_instance = True
        # `id` is excluded because the row is a singleton — there's
        # only ever id=1 and the API shouldn't expose a way to change
        # it.
        exclude = ('id',)
        unknown = EXCLUDE


class ContactSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Contact objects.

    This schema defines the fields to include when serializing and deserializing Contact objects.
    It includes fields for the contact name, email, work phone, mobile phone, role, note, and client ID.

    """
    contact_name: str = auto_field('contact_name', required=True, validate=Length(min=2), allow_none=False)
    contact_email: Optional[str] = auto_field('contact_email', required=False, allow_none=False)
    contact_work_phone: Optional[str] = auto_field('contact_work_phone', required=False, allow_none=False)
    contact_mobile_phone: Optional[str] = auto_field('contact_mobile_phone', required=False, allow_none=False)
    contact_role: Optional[str] = auto_field('contact_role', required=False, allow_none=False)
    contact_note: Optional[str] = auto_field('contact_note', required=False, allow_none=False)
    client_id: int = auto_field('client_id', required=True)

    class Meta:
        model = Contact
        load_instance = True
        unknown = EXCLUDE


class CaseClassificationSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseClassification objects.

    This schema defines the fields to include when serializing and deserializing CaseClassification objects.
    It includes fields for the classification name, expanded name, and description.

    """
    name: str = auto_field('name', required=True, validate=Length(min=2), allow_none=False)
    name_expanded: str = auto_field('name_expanded', required=True, validate=Length(min=2), allow_none=False)
    description: str = auto_field('description', required=True, validate=Length(min=2), allow_none=False)

    class Meta:
        model = CaseClassification
        load_instance = True
        unknown = EXCLUDE

    @post_load
    def verify_unique(self, data, **kwargs):
        """Verifies that the classification name is unique.

        This method verifies that the classification name is unique. If the name is not unique, it raises a validation error.

        Args:
            data: The data to load.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the classification name is not unique.

        """
        client = CaseClassification.query.filter(
            func.lower(CaseClassification.name) == func.lower(data.name),
            CaseClassification.id != data.id
        ).first()
        if client:
            raise ValidationError("Case classification name already exists", field_name="name")

        return data


class EvidenceTypeSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing EvidenceType objects.

    This schema defines the fields to include when serializing and deserializing EvidenceType objects.
    It includes fields for the evidence type name, expanded name, and description.

    """
    name: str = auto_field('name', required=True, validate=Length(min=2), allow_none=False)
    description: str = auto_field('description', required=True, allow_none=True)

    class Meta:
        model = EvidenceTypes
        load_instance = True
        unknown = EXCLUDE

    @post_load
    def verify_unique(self, data, **kwargs):
        """Verifies that the evidence type name is unique.

        This method verifies that the evidence type name is unique. If the name is not unique, it raises a validation error.

        Args:
            data: The data to load.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the evidence type name is not unique.

        """
        client = EvidenceTypes.query.filter(
            func.lower(EvidenceTypes.name) == func.lower(data.name),
            EvidenceTypes.id != data.id
        ).first()
        if client:
            raise ValidationError("Evidence type already exists", field_name="name")

        return data


class CaseSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Case objects.

    This schema defines the fields to include when serializing and deserializing Case objects.
    It includes fields for the case name, description, SOC ID, customer ID, organizations, protagonists, tags, CSRF token,
    initial date, and classification ID.

    """
    case_name: str = auto_field('name', required=True, validate=Length(min=2), allow_none=False)
    case_description: str = auto_field('description', required=True, validate=Length(min=2))
    case_soc_id: int = auto_field('soc_id', required=True)
    case_customer: int = auto_field('client_id', required=True)
    case_organisations: List[int] = fields.List(fields.Integer, required=False)
    protagonists: List[Dict[str, Any]] = fields.List(fields.Dict, required=False)
    case_tags: Optional[str] = fields.String(required=False)
    initial_date: Optional[datetime.datetime] = auto_field('initial_date', required=False)
    classification_id: Optional[int] = auto_field('classification_id', required=False, allow_none=True)
    reviewer_id: Optional[int] = auto_field('reviewer_id', required=False, allow_none=True)
    review_status: Optional[str] = auto_field('review_status', required=False, allow_none=True)
    severity_id: Optional[int] = auto_field('severity_id', required=False, allow_none=True)

    class Meta:
        model = Cases
        include_fk = True
        load_instance = True
        exclude = ['name', 'description', 'soc_id', 'client_id', 'initial_date']
        unknown = EXCLUDE

    @pre_load
    def classification_filter(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Filters out empty classification IDs.

        This method filters out empty classification IDs from the data.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The filtered data.

        """
        if data.get('classification_id') == "":
            del data['classification_id']

        return data

    @pre_load
    def verify_customer(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the customer ID is valid.

        This method verifies that the customer ID specified in the data is valid.
        If the ID is not valid, it raises a validation error.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the customer ID is not valid.

        """
        assert_type_mml(input_var=data.get('case_customer'),
                        field_name='case_customer',
                        type=int,
                        allow_none=True)

        client = Client.query.filter(Client.client_id == data.get('case_customer')).first()
        if client:
            return data

        raise ValidationError("Invalid client id", field_name="case_customer")

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes.

        This method merges the custom attributes specified in the data with the existing custom attributes.
        If there are no custom attributes specified, it returns the original data.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data with merged custom attributes.

        """
        new_attr = data.get('custom_attributes')

        assert_type_mml(input_var=new_attr,
                        field_name='custom_attributes',
                        type=dict,
                        allow_none=True)

        assert_type_mml(input_var=data.get('case_id'),
                        field_name='case_id',
                        type=int,
                        allow_none=True)

        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('case_id'), 'case')

        return data


class CaseStateSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseState objects.

    This schema defines the fields to include when serializing and deserializing CaseState objects.
    It includes fields for the case state ID, the case ID, the state name, and the state description.

    """
    case_state_id: int = fields.Integer()
    case_id: int = fields.Integer()
    state_name: str = fields.String()
    state_description: str = fields.String()

    class Meta:
        model = CaseState
        load_instance = True
        unknown = EXCLUDE


class GlobalTasksSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing GlobalTasks objects.

    This schema defines the fields to include when serializing and deserializing GlobalTasks objects.
    It includes fields for the task ID, assignee ID, task title, and CSRF token.

    """
    task_id: int = auto_field('id')
    task_assignee_id: int = auto_field('task_assignee_id', required=True, allow_none=False)
    task_title: str = auto_field('task_title', required=True, validate=Length(min=2), allow_none=False)

    class Meta:
        model = GlobalTasks
        include_fk = True
        load_instance = True
        exclude = ['id']
        unknown = EXCLUDE

    @pre_load
    def verify_data(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the assignee ID and task status ID are valid.

        This method verifies that the assignee ID and task status ID specified in the data are valid.
        If either ID is not valid, it raises a validation error.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the assignee ID or task status ID is not valid.

        """
        assert_type_mml(input_var=data.get('task_assignee_id'),
                        field_name='task_assignee_id',
                        type=int)

        user = User.query.filter(User.id == data.get('task_assignee_id')).count()
        if not user:
            raise ValidationError("Invalid user id for assignee", field_name="task_assignees_id")

        assert_type_mml(input_var=data.get('task_status_id'),
                        field_name='task_status_id',
                        type=int)
        status = TaskStatus.query.filter(TaskStatus.id == data.get('task_status_id')).count()
        if not status:
            raise ValidationError("Invalid task status ID", field_name="task_status_id")

        return data


class CustomerSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Customer objects.

    This schema defines the fields to include when serializing and deserializing Customer objects.
    It includes fields for the customer name, description, SLA, customer ID, and CSRF token.

    """
    customer_name: str = auto_field('name', required=True, validate=Length(min=2), allow_none=False)
    customer_description: Optional[str] = auto_field('description', allow_none=True)
    customer_sla: Optional[str] = auto_field('sla', allow_none=True)
    customer_id: int = auto_field('client_id')

    class Meta:
        model = Client
        load_instance = True
        exclude = ['name', 'client_id', 'description', 'sla']
        unknown = EXCLUDE

    @pre_load
    def verify_unique_name(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        if 'customer_name' not in data:
            return data
        identifier = data.get('customer_id')
        name = data['customer_name']
        if customers_exists_another_with_same_name(identifier, name):
            raise ValidationError('Customer already exists', field_name='customer_name')
        return data

    @post_load
    def verify_unique(self, data: Client, **kwargs: Any) -> Client:
        """Verifies that the customer name is unique.

        This method verifies that the customer name is unique. If the name is not unique, it raises a validation error.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the customer name is not unique.

        """
        assert_type_mml(input_var=data.name,
                        field_name='customer_name',
                        type=str)

        assert_type_mml(input_var=data.client_id,
                        field_name='customer_id',
                        type=int,
                        allow_none=True)

        return data

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes.

        This method merges the custom attributes specified in the data with the existing custom attributes.
        If there are no custom attributes specified, it returns the original data.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data with merged custom attributes.

        """
        new_attr = data.get('custom_attributes')

        assert_type_mml(input_var=new_attr,
                        field_name='custom_attributes',
                        type=dict,
                        allow_none=True)

        if new_attr is not None:
            assert_type_mml(input_var=data.get('client_id'),
                            field_name='customer_id',
                            type=int,
                            allow_none=True)

            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('client_id'), 'client')

        return data


class TaskLogSchema(ma.Schema):
    """Schema for serializing and deserializing TaskLog objects.

    This schema defines the fields to include when serializing and deserializing TaskLog objects.
    It includes fields for the log content and CSRF token.

    """
    log_content: Optional[str] = fields.String(required=False, validate=Length(min=1))

    class Meta:
        load_instance = True
        unknown = EXCLUDE


class AnalysisStatusSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing AnalysisStatus objects.

    This schema defines the fields to include when serializing and deserializing AnalysisStatus objects.
    It includes fields for the analysis status name and analysis status value.

    """

    class Meta:
        model = AnalysisStatus
        load_instance = True
        unknown = EXCLUDE


class TaskStatusSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing TaskStatus objects.

    This schema defines the fields to include when serializing and deserializing TaskStatus objects.
    It includes fields for the task status name, task status value, and CSRF token.

    """

    class Meta:
        model = TaskStatus
        load_instance = True
        unknown = EXCLUDE


class CaseTaskSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseTask objects.

    This schema defines the fields to include when serializing and deserializing CaseTask objects.
    It includes fields for the task title, task status ID, task assignees ID, task assignees, and CSRF token.

    """
    task_title: str = auto_field('task_title', required=True, validate=Length(min=2), allow_none=False)
    task_status_id: int = auto_field('task_status_id', required=True)
    task_assignees_id: Optional[List[int]] = fields.List(fields.Integer, required=False, allow_none=True)
    task_assignees: Optional[List[Dict[str, Any]]] = fields.List(fields.Dict, required=False, allow_none=True)
    status = ma.Nested(TaskStatusSchema)
    case = ma.Nested(CaseSchema, only=['case_name', 'case_id'])

    class Meta:
        model = CaseTasks
        load_instance = True
        include_fk = True
        unknown = EXCLUDE

    @pre_load
    def verify_data(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the task status ID is valid.

        This method verifies that the task status ID specified in the data is valid.
        If the ID is not valid, it raises a validation error.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the task status ID is not valid.

        """
        assert_type_mml(input_var=data.get('task_status_id'),
                        field_name='task_status_id',
                        type=int)

        status = TaskStatus.query.filter(TaskStatus.id == data.get('task_status_id')).count()
        if not status:
            raise ValidationError("Invalid task status ID", field_name="task_status_id")

        if data.get('task_tags'):
            for tag in data.get('task_tags').split(','):
                if not isinstance(tag, str):
                    raise ValidationError("All items in list must be strings", field_name="task_tags")
                add_db_tag(tag.strip())

        return data

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes.

        This method merges the custom attributes specified in the data with the existing custom attributes.
        If there are no custom attributes specified, it returns the original data.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data with merged custom attributes.

        """
        new_attr = data.get('custom_attributes')

        assert_type_mml(input_var=new_attr,
                        field_name='custom_attributes',
                        type=dict,
                        allow_none=True)

        assert_type_mml(input_var=data.get('id'),
                        field_name='task_id',
                        type=int,
                        allow_none=True)

        if new_attr is not None:
            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('id'), 'task')

        return data

    @post_dump(pass_original=True)
    def populate_assignees(self, data: Dict[str, Any], original: Any, **kwargs: Any) -> Dict[str, Any]:
        """Inject the assignee list for the task.

        `task_assignees` and `task_assignees_id` are declared as schema
        fields, but the `CaseTasks` model itself has no relationship to
        `TaskAssignee` — so without this hook both fields always serialise
        to `None`, which silently hides the assignees stored in the DB
        and breaks the frontend assignee picker on re-edit.

        We query `TaskAssignee` once per dumped task and back-fill both
        fields. When the schema is dumped without a model instance (e.g.
        from a dict), we leave the data untouched.
        """
        task_id = getattr(original, 'id', None) if original is not None else None
        if task_id is None:
            return data

        assignees = get_task_assignees(task_id)
        data['task_assignees'] = assignees
        data['task_assignees_id'] = [assignee['id'] for assignee in assignees]
        return data


class CaseEvidenceSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseEvidence objects.

    This schema defines the fields to include when serializing and deserializing CaseEvidence objects.
    It includes fields for the filename and CSRF token.

    """
    filename: str = auto_field('filename', required=True, validate=Length(min=2), allow_none=False)
    type = ma.Nested(EvidenceTypeSchema)
    user = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'])

    class Meta:
        model = CaseReceivedFile
        load_instance = True
        include_relationships = True
        include_fk = True
        unknown = EXCLUDE

    @post_load
    def custom_attributes_merge(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Merges custom attributes.

        This method merges the custom attributes specified in the data with the existing custom attributes.
        If there are no custom attributes specified, it returns the original data.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data with merged custom attributes.

        """
        new_attr = data.get('custom_attributes')

        assert_type_mml(input_var=new_attr,
                        field_name='custom_attributes',
                        type=dict,
                        allow_none=True)

        if new_attr is not None:
            assert_type_mml(input_var=data.get('id'),
                            field_name='evidence_id',
                            type=int,
                            allow_none=True)

            data['custom_attributes'] = merge_custom_attributes(new_attr, data.get('id'), 'evidence')

        return data


class AuthorizationGroupSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing AuthorizationGroup objects.

    This schema defines the fields to include when serializing and deserializing AuthorizationGroup objects.
    It includes fields for the group name, group description, group auto follow access level, and group permissions.

    """
    group_name: str = auto_field('group_name', required=True, validate=Length(min=2), allow_none=False)
    group_description: str = auto_field('group_description', required=True, validate=Length(min=2))
    group_auto_follow_access_level: Optional[bool] = auto_field('group_auto_follow_access_level', required=False,
                                                                default=False)
    group_permissions: int = fields.Integer(required=False)
    group_members: Optional[List[Dict[str, Any]]] = fields.List(fields.Dict, required=False, allow_none=True)
    group_permissions_list: Optional[List[Dict[str, Any]]] = fields.List(fields.Dict, required=False, allow_none=True)
    group_cases_access: Optional[List[Dict[str, Any]]] = fields.List(fields.Dict, required=False, allow_none=True)

    class Meta:
        model = Group
        load_instance = True
        include_fk = True
        unknown = EXCLUDE

    @pre_load
    def verify_unique(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the group name is unique.

        This method verifies that the group name specified in the data is unique.
        If the name is not unique, it raises a validation error.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the group name is not unique.

        """
        assert_type_mml(input_var=data.get('group_name'),
                        field_name='group_name',
                        type=str)

        groups = Group.query.filter(
            func.upper(Group.group_name) == data.get('group_name').upper()
        ).all()

        for group in groups:
            if data.get('group_id') is None or group.group_id != data.get('group_id'):
                raise ValidationError("Group already exists", field_name="group_name")

        return data

    @pre_load
    def parse_permissions(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Normalise `group_permissions` into an access-control bitmask.

        Accepts either an int (already a mask) or a list of ints
        (OR-folded into a mask). Historically this method injected
        `group_permissions = 0` when the caller omitted the key, which
        silently wiped a group's permissions on any partial PATCH that
        happened to only touch `group_name` / `group_description`.
        We now leave the key alone when it isn't supplied so `load(...,
        partial=True)` can preserve the persisted value.

        Args:
            data: The raw payload to load.
            kwargs: Marshmallow-supplied context (unused).

        Returns:
            The payload with `group_permissions` normalised, or
            untouched if the caller didn't send it.
        """
        if 'group_permissions' not in data:
            return data

        permissions = data['group_permissions']
        if permissions is None:
            # Explicit null → treat as "clear all permissions" (0).
            # Distinct from "key absent", which we skip above.
            data['group_permissions'] = 0
            return data

        if not isinstance(permissions, list):
            permissions = [permissions]

        data['group_permissions'] = ac_mask_from_val_list(permissions)
        return data


class AuthorizationOrganisationSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing AuthorizationOrganisation objects.

    This schema defines the fields to include when serializing and deserializing AuthorizationOrganisation objects.
    It includes fields for the organization name and description.

    """
    org_name: str = auto_field('org_name', required=True, validate=Length(min=2), allow_none=False)
    org_description: str = auto_field('org_description', required=True, validate=Length(min=2))

    class Meta:
        model = Organisation
        load_instance = True
        unknown = EXCLUDE

    @pre_load
    def verify_unique(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the organization name is unique.

        This method verifies that the organization name specified in the data is unique.
        If the name is not unique, it raises a validation error.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the organization name is not unique.

        """
        assert_type_mml(input_var=data.get('org_name'),
                        field_name='org_name',
                        type=str)

        organisations = Organisation.query.filter(
            func.upper(Organisation.org_name) == data.get('org_name').upper()
        ).all()

        for organisation in organisations:
            if data.get('org_id') is None or organisation.org_id != data.get('org_id'):
                raise ValidationError('Organisation name already exists', field_name='org_name')

        return data


class BasicUserSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing basic User objects.

    This schema defines the fields to include when serializing and deserializing basic User objects.
    It includes fields for the user name, login, and email.

    """
    user_id: Optional[int] = auto_field('id', required=False)
    user_uuid: Optional[str] = auto_field('uuid', required=False)
    user_name: str = auto_field('name', required=True, validate=Length(min=2))
    user_login: str = auto_field('user', required=True, validate=Length(min=2))
    user_email: str = auto_field('email', required=True, validate=Length(min=2))
    has_deletion_confirmation: Optional[bool] = auto_field('has_deletion_confirmation', required=False, default=False)

    class Meta:
        model = User
        load_instance = True
        exclude = ['password', 'api_key', 'ctx_case', 'ctx_human_case', 'active', 'external_id', 'in_dark_mode',
                   'id', 'name', 'email', 'user', 'uuid', 'mfa_secrets', 'webauthn_credentials',
                   'avatar_blob', 'avatar_mime']
        unknown = EXCLUDE


class SeveritySchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Severity objects.

    This schema defines the fields to include when serializing and deserializing Severity objects.
    It includes fields for the severity name and severity value.

    """

    class Meta:
        model = Severity
        load_instance = True
        unknown = EXCLUDE


class AlertStatusSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing AlertStatus objects.

    This schema defines the fields to include when serializing and deserializing AlertStatus objects.
    It includes fields for the alert status name and alert status value.

    """

    class Meta:
        model = AlertStatus
        load_instance = True
        unknown = EXCLUDE


class AlertResolutionSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing AlertResolution objects.

    This schema defines the fields to include when serializing and deserializing AlertStatus objects.
    It includes fields for the alert status name and alert status value.

    """

    class Meta:
        model = AlertResolutionStatus
        load_instance = True
        unknown = EXCLUDE


class EventCategorySchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing EventCategory objects.

    This schema defines the fields to include when serializing and deserializing EventCategory objects.
    It includes fields for the event category name and event category value.

    """

    class Meta:
        model = EventCategory
        load_instance = True
        unknown = EXCLUDE


class AlertCaseSchema(ma.Schema):
    case_id: int = fields.Integer(required=True)

    @post_load
    def make_case(self, data: Dict[str, Any], **kwargs: Any) -> Cases:
        return Cases.query.filter(Cases.case_id == data.get('case_id')).first()


class AlertSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Alert objects.

    This schema defines the fields to include when serializing and deserializing Alert objects.
    It includes fields for the alert severity, status, customer, classification, owner, IOCs, and assets.

    """
    severity = ma.Nested(SeveritySchema)
    status = ma.Nested(AlertStatusSchema)
    customer = ma.Nested(CustomerSchema)
    classification = ma.Nested(CaseClassificationSchema)
    owner = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'])
    iocs = ma.Nested(IocSchema, many=True)
    assets = ma.Nested(CaseAssetsSchema, many=True, exclude=['alerts'])
    resolution_status = ma.Nested(AlertResolutionSchema)
    cases = fields.Pluck(AlertCaseSchema, 'case_id', many=True, required=False)
    clusters = fields.Method('_cluster_ids', dump_only=True)
    investigation_flow = fields.Method('_flow_summary', dump_only=True)

    class Meta:
        model = Alert
        include_relationships = True
        include_fk = True
        load_instance = True
        unknown = EXCLUDE

    def _cluster_ids(self, alert: Alert):
        return [c.cluster_id for c in (alert.clusters or [])]

    def _flow_summary(self, alert: Alert):
        flow = alert.investigation_flow
        if not flow:
            return None
        return {'flow_id': flow.flow_id, 'flow_name': flow.flow_name}

    @pre_load
    def verify_data(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Verify that the alert tags are valid and save them if they don't exist
        """
        if data.get('alert_tags'):
            for tag in data.get('alert_tags').split(','):
                if not isinstance(tag, str):
                    raise ValidationError("All items in list must be strings", field_name="alert_tags")
                add_db_tag(tag.strip())

        return data


class SavedFilterSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing SavedFilter objects.

    This schema defines the fields to include when serializing and deserializing SavedFilter objects.

    """

    class Meta:
        model = SavedFilter
        load_instance = True
        include_fk = True
        include_relationships = True
        unknown = EXCLUDE


class IrisModuleSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = IrisModule
        load_instance = True
        unknown = EXCLUDE


class ModuleHooksSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing ModuleHooks objects.

    This schema defines the fields to include when serializing and deserializing ModuleHooks objects.

    """

    class Meta:
        model = IrisModuleHook
        load_instance = True
        include_fk = True
        include_relationships = True
        unknown = EXCLUDE


class TagsSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Tags
        load_instance = True
        include_fk = True
        include_relationships = True
        unknown = EXCLUDE


class ReviewStatusSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ReviewStatus
        load_instance = True
        include_fk = True
        include_relationships = True
        unknown = EXCLUDE


class CaseProtagonistSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseProtagonist objects."""

    class Meta:
        model = CaseProtagonist
        load_instance = True
        include_fk = True
        include_relationships = True


# This is the new schema for /api/v2/cases. It's in between CaseSchema and CaseDetailsSchema
# The goal was to have the same type for the cases returned in the following endpoints:
# * GET /api/v2/cases
# * POST /api/v2/cases
# * GET /api/v2/cases/{identifier}
# TODO The objective could then be to remove CaseSchema and CaseDetailsSchema
class CaseSchemaForAPIV2(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Case objects.

    This schema defines the fields to include when serializing and deserializing Case objects.
    It includes fields for the case name, description, SOC ID, customer ID, organizations, protagonists, tags, CSRF token,
    initial date, and classification ID.

    """
    case_name: str = auto_field('name', required=True, validate=Length(min=2), allow_none=False)
    case_description: str = auto_field('description', required=True, validate=Length(min=2))
    case_soc_id: int = auto_field('soc_id', required=True)
    case_customer_id: int = auto_field('client_id', required=True)
    case_organisations: List[int] = fields.List(fields.Integer, required=False)
    protagonists: List[Dict[str, Any]] = fields.List(fields.Dict, required=False)
    case_tags: Optional[str] = fields.String(required=False)
    initial_date: Optional[datetime.datetime] = auto_field('initial_date', required=False)
    classification_id: Optional[int] = auto_field('classification_id', required=False, allow_none=True)
    reviewer_id: Optional[int] = auto_field('reviewer_id', required=False, allow_none=True)
    access_level = fields.Integer(required=False)

    owner = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'])
    severity = ma.Nested(SeveritySchema)
    classification = ma.Nested(CaseClassificationSchema)
    reviewer = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'])
    tags = ma.Nested(TagsSchema, many=True, only=['tag_title', 'id'])
    state = ma.Nested(CaseStateSchema)
    case_customer = ma.Nested(CustomerSchema, attribute='client')
    review_status = ma.Nested(ReviewStatusSchema)

    class Meta:
        model = Cases
        include_fk = True
        load_instance = True
        exclude = ['name', 'description', 'soc_id', 'client_id', 'initial_date']
        unknown = EXCLUDE

    @pre_load
    def classification_filter(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Filters out empty classification IDs.

        This method filters out empty classification IDs from the data.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The filtered data.

        """
        if data.get('classification_id') == "":
            del data['classification_id']

        return data

    @pre_load
    def verify_customer(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the customer ID is valid.

        This method verifies that the customer ID specified in the data is valid.
        If the ID is not valid, it raises a validation error.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data.

        Raises:
            ValidationError: If the customer ID is not valid.

        """
        customer_identifier = data.get('case_customer_id')
        assert_type_mml(input_var=customer_identifier,
                        field_name='case_customer_id',
                        type=int,
                        allow_none=True)

        client = Client.query.filter(Client.client_id == customer_identifier).first()
        if client:
            return data

        raise ValidationError('Invalid client id', field_name='case_customer_id')


class CaseDetailsSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing Case objects in details."""
    client = ma.Nested(CustomerSchema)
    owner = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'])
    classification = ma.Nested(CaseClassificationSchema)
    state = ma.Nested(CaseStateSchema)
    tags = ma.Nested(TagsSchema, many=True, only=['tag_title', 'id'])
    user = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'])
    reviewer = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'])
    review_status = ma.Nested(ReviewStatusSchema)
    severity = ma.Nested(SeveritySchema)

    def get_status_name(self, obj):
        return CaseStatus(obj.status_id).name

    def get_protagonists(self, obj):
        cp = CaseProtagonist.query.with_entities(
            CaseProtagonist.role,
            CaseProtagonist.name,
            CaseProtagonist.contact,
            User.name.label('user_name'),
            User.user.label('user_login')
        ).filter(
            CaseProtagonist.case_id == obj.case_id
        ).outerjoin(
            CaseProtagonist.user
        ).all()
        cp = CaseProtagonistSchema(many=True).dump(cp)
        return cp

    status_name = ma.Method('get_status_name')
    protagonists = ma.Method('get_protagonists')

    class Meta:
        model = Cases
        include_fk = True
        load_instance = True
        include_relationships = True
        unknown = EXCLUDE


class UserSchemaForAPIV2(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing User objects.

    This schema defines the fields to include when serializing and deserializing User objects.
    It includes fields for the user's name, login, email, password, admin status, CSRF token, ID, primary organization ID,
    and service account status. It also includes methods for verifying the username, email, and password.

    """
    user_roles_str: List[str] = fields.List(fields.String, required=False)
    user_name: str = auto_field('name', required=True, validate=Length(min=2))
    user_login: str = auto_field('user', required=True, validate=Length(min=2))
    user_email: str = auto_field('email', required=True, validate=Length(min=2))
    user_active: bool = auto_field('active', required=True)
    user_id: bool = auto_field('id', required=True, dump_only=True)
    user_api_key: bool = auto_field('api_key', required=False, dump_only=True)
    user_password: Optional[str] = auto_field('password', required=False, load_only=True)
    user_isadmin: bool = fields.Boolean(required=True)
    user_is_service_account: Optional[bool] = auto_field('is_service_account', required=False)

    user_groups = ma.Nested(AuthorizationGroupSchema, many=True, attribute='groups', only=['group_name', 'group_id', 'group_uuid'])
    user_permissions = ma.Nested(AuthorizationGroupSchema, many=True, attribute='permissions', only=['group_name', 'group_permissions'])
    user_customers = ma.Nested(CustomerSchema, many=True, attribute='customers', only=['customer_name', 'customer_id'])
    user_cases_access = ma.Nested(CaseSchemaForAPIV2, many=True, attribute='cases_access', only=['access_level', 'case_id', 'case_name'])
    user_organisations = fields.Method('get_user_organisations', only=['org_name', 'org_id', 'org_uuid', 'is_primary_org'])
    user_primary_organisation_id = fields.Method('get_user_primary_organisation', only=['id'])

    class Meta:
        model = User
        load_instance = True
        include_fk = True
        exclude = ['api_key', 'password', 'ctx_human_case', 'user', 'name', 'email', 'is_service_account', 'mfa_secrets',
                   'webauthn_credentials', 'mfa_setup_complete', 'external_id', 'active', 'id',
                   # See UserSchema above — bytes blob never goes
                   # through JSON; image bytes are served lazily.
                   'avatar_blob', 'avatar_mime',
                   # `preferences` has its own dedicated endpoints —
                   # kept out of the general user serialiser.
                   'preferences']
        unknown = EXCLUDE

    def get_user_primary_organisation(self, obj):
        return get_primary_organisation(obj.id)

    def get_user_organisations(self, obj):
        return get_organisations(obj.id)

    @pre_load()
    def verify_username(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the username is not already taken.

        This method verifies that the specified username is not already taken by another user. If the username is already
        taken, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the username is already taken.

        """
        user = data.get('user_login')
        user_id = data.get('user_id')

        assert_type_mml(input_var=user_id,
                        field_name='user_id',
                        type=int,
                        allow_none=True)

        assert_type_mml(input_var=user,
                        field_name='user_login',
                        type=str,
                        allow_none=True)

        luser = User.query.filter(
            User.user == user
        ).all()
        for usr in luser:
            if usr.id != user_id:
                raise ValidationError('User name already taken', field_name='user_login')

        return data

    @pre_load()
    def verify_email(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the email is not already taken.

        This method verifies that the specified email is not already taken by another user. If the email is already
        taken, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the email is already taken.

        """
        email = data.get('user_email')
        user_id = data.get('user_id')

        assert_type_mml(input_var=user_id,
                        field_name='user_id',
                        type=int,
                        allow_none=True)

        assert_type_mml(input_var=email,
                        field_name='user_email',
                        type=str,
                        allow_none=True)

        luser = User.query.filter(
            User.email == email
        ).all()
        for usr in luser:
            if usr.id != user_id:
                raise ValidationError('User email already taken', field_name='user_email')

        return data

    @pre_load()
    def verify_password(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Verifies that the password meets the server's password policy.

        This method verifies that the specified password meets the server's password policy. If the password does not
        meet the policy, it raises a validation error.

        Args:
            data: The data to verify.
            kwargs: Additional keyword arguments.

        Returns:
            The verified data.

        Raises:
            ValidationError: If the password does not meet the server's password policy.

        """
        server_settings = ServerSettings.query.first()
        password = data.get('user_password')

        if (password == '' or password is None) and str_to_bool(data.get('user_is_service_account')) is True:
            return data

        if (password == '' or password is None) and data.get('user_id') != 0:
            # Update
            data.pop('user_password') if 'user_password' in data else None

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
                    password_error += f'Password must contain a special char [{server_settings.password_policy_special_chars}].'

            if len(password_error) > 0:
                raise ValidationError(password_error, field_name='user_password')

        return data


class AlertClusterStatusSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AlertClusterStatus
        load_instance = True
        unknown = EXCLUDE


class AlertClusterSchema(ma.SQLAlchemyAutoSchema):
    status = ma.Nested(AlertClusterStatusSchema, dump_only=True)
    severity = ma.Nested(SeveritySchema, dump_only=True)
    customer = ma.Nested(CustomerSchema, dump_only=True)
    owner = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login', 'user_email'], dump_only=True)
    alert_ids = fields.Method('_alert_ids', dump_only=True)
    investigation_flow = fields.Method('_flow_summary', dump_only=True)
    source_rule = fields.Method('_source_rule_summary', dump_only=True)

    class Meta:
        model = AlertCluster
        include_relationships = True
        include_fk = True
        load_instance = True
        unknown = EXCLUDE

    def _alert_ids(self, cluster: AlertCluster):
        return [a.alert_id for a in (cluster.alerts or [])]

    def _flow_summary(self, cluster: AlertCluster):
        flow = cluster.investigation_flow
        if not flow:
            return None
        return {'flow_id': flow.flow_id, 'flow_name': flow.flow_name}

    def _source_rule_summary(self, cluster: AlertCluster):
        # Surface the rule that created the cluster so the detail page can
        # link back to /settings/cluster-rules for auditability.
        rule = cluster.source_rule
        if not rule:
            return None
        return {'rule_id': rule.rule_id, 'rule_name': rule.rule_name}


def _validate_condition_node(node, path):
    """Recursively check that a condition tree is well-formed.

    A node is either:
      * a leaf `{field, operator[, value]}`
      * a group `{logic, conditions: [...]}` where each entry is itself a node

    Same shape `apply_custom_conditions` accepts. We stay lenient — the
    SQL layer will reject unknown fields / operators when the rule
    fires; the goal here is only to reject obviously malformed rows.
    """
    if not isinstance(node, dict):
        raise ValidationError(f'{path} must be an object')
    if 'conditions' in node and 'field' not in node:
        # Group node
        logic = node.get('logic', 'and')
        if logic not in ('and', 'or', 'not'):
            raise ValidationError(f"{path}.logic must be one of 'and'/'or'/'not'")
        inner = node.get('conditions')
        if not isinstance(inner, list):
            raise ValidationError(f'{path}.conditions must be a list')
        for idx, sub in enumerate(inner):
            _validate_condition_node(sub, f'{path}.conditions[{idx}]')
        return
    # Leaf node
    if 'field' not in node or 'operator' not in node:
        raise ValidationError(f'{path} must include field and operator')


def _validate_rule_conditions(payload):
    if not isinstance(payload, dict):
        raise ValidationError('rule_conditions must be an object')
    logic = payload.get('logic', 'and')
    if logic not in ('and', 'or', 'not'):
        raise ValidationError("rule_conditions.logic must be one of 'and'/'or'/'not'")
    conditions = payload.get('conditions')
    if not isinstance(conditions, list) or not conditions:
        raise ValidationError('rule_conditions.conditions must be a non-empty list')
    for idx, cond in enumerate(conditions):
        _validate_condition_node(cond, f'rule_conditions.conditions[{idx}]')
    time_window = payload.get('time_window_seconds')
    if time_window is not None and (not isinstance(time_window, int) or time_window < 0):
        raise ValidationError('rule_conditions.time_window_seconds must be a non-negative integer')
    group_by = payload.get('group_by')
    if group_by is not None and (not isinstance(group_by, list)
                                 or not all(isinstance(g, str) for g in group_by)):
        raise ValidationError('rule_conditions.group_by must be a list of field names')


class ClusterRuleSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ClusterRule
        include_fk = True
        load_instance = True
        unknown = EXCLUDE

    @pre_load
    def _validate(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        if 'rule_conditions' in data:
            _validate_rule_conditions(data['rule_conditions'])
        action = data.get('rule_action_type')
        # The historical `attach_flow` action was removed — flows now own
        # their own conditions (see InvestigationFlow.flow_conditions), so
        # the only remaining rule action is stacking alerts into clusters.
        if action is not None and action != RULE_ACTION_CREATE_CLUSTER:
            raise ValidationError(
                f'rule_action_type must be {RULE_ACTION_CREATE_CLUSTER}'
            )
        scope = data.get('rule_customer_scope')
        if scope is not None and (not isinstance(scope, list)
                                  or not all(isinstance(s, int) for s in scope)):
            raise ValidationError('rule_customer_scope must be null or a list of customer ids')
        return data


class InvestigationFlowStepSchema(ma.SQLAlchemyAutoSchema):
    # `flow_id` is set by the route from the URL path (see
    # `flow_step_create` in `app/business/investigation_flows.py`), so the
    # client must not have to repeat it in the body. Without this override
    # marshmallow-sqlalchemy makes it required (the column is
    # `nullable=False`) and the POST 400s with "Missing data for required
    # field.". `load_default=None` lets `.load()` succeed without it; the
    # route stamps the correct id before commit.
    flow_id = auto_field(required=False, load_default=None)

    class Meta:
        model = InvestigationFlowStep
        include_fk = True
        load_instance = True
        unknown = EXCLUDE


class InvestigationFlowSchema(ma.SQLAlchemyAutoSchema):
    steps = ma.Nested(InvestigationFlowStepSchema, many=True)

    class Meta:
        model = InvestigationFlow
        include_relationships = True
        include_fk = True
        load_instance = True
        unknown = EXCLUDE

    @pre_load
    def _validate(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        # Reuse the same conditions validator as cluster rules so the DSL
        # semantics stay identical across features. `flow_conditions` may
        # be omitted (an empty condition list is the default), but a
        # payload that includes it must be well-formed.
        from app.models.investigation_flows import FLOW_TARGETS
        conditions = data.get('flow_conditions')
        if conditions is not None:
            if not isinstance(conditions, dict):
                raise ValidationError('flow_conditions must be an object')
            logic = conditions.get('logic', 'and')
            if logic not in ('and', 'or', 'not'):
                raise ValidationError("flow_conditions.logic must be 'and'/'or'/'not'")
            cond_list = conditions.get('conditions')
            if not isinstance(cond_list, list):
                raise ValidationError('flow_conditions.conditions must be a list')
            # Empty list is allowed here (unlike rules) — a flow with no
            # conditions simply never auto-attaches; deploy skips it too.
            for idx, cond in enumerate(cond_list):
                _validate_condition_node(cond, f'flow_conditions.conditions[{idx}]')
        target = data.get('flow_target')
        if target is not None and target not in FLOW_TARGETS:
            raise ValidationError(
                f'flow_target must be one of {"/".join(FLOW_TARGETS)}'
            )
        scope = data.get('flow_customer_scope')
        if scope is not None and (not isinstance(scope, list)
                                  or not all(isinstance(s, int) for s in scope)):
            raise ValidationError('flow_customer_scope must be null or a list of customer ids')
        return data


class AlertInvestigationProgressSchema(ma.SQLAlchemyAutoSchema):
    completed_by = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login'], dump_only=True)

    class Meta:
        model = AlertInvestigationProgress
        include_fk = True
        load_instance = True
        unknown = EXCLUDE


class AlertClusterInvestigationProgressSchema(ma.SQLAlchemyAutoSchema):
    completed_by = ma.Nested(UserSchema, only=['id', 'user_name', 'user_login'], dump_only=True)

    class Meta:
        model = AlertClusterInvestigationProgress
        include_fk = True
        load_instance = True
        unknown = EXCLUDE
