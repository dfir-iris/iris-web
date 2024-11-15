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
import psycopg2
import pyminizip
import random
import re
import shutil
import string
import tempfile
from flask_login import current_user
from marshmallow import ValidationError, EXCLUDE
from marshmallow import fields
from marshmallow import post_load
from marshmallow import pre_load
from marshmallow.validate import Length
from marshmallow_sqlalchemy import auto_field
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import aliased
from typing import Any, Dict, List, Optional, Tuple, Union
from werkzeug.datastructures import FileStorage

from app import app
from app import db
from app import ma
from app.datamgmt.datastore.datastore_db import datastore_get_standard_path
from app.datamgmt.manage.manage_attribute_db import merge_custom_attributes
from app.datamgmt.manage.manage_tags_db import add_db_tag
from app.iris_engine.access_control.utils import ac_mask_from_val_list
from app.models import AnalysisStatus, CaseClassification, SavedFilter, DataStorePath, IrisModuleHook, Tags, \
    ReviewStatus, EvidenceTypes, CaseStatus, NoteDirectory, NoteRevisions
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
from app.models import IrisModule
from app.models import Notes
from app.models import NotesGroup
from app.models import ServerSettings
from app.models import TaskStatus
from app.models import Tlp
from app.models.alerts import Alert, Severity, AlertStatus, AlertResolutionStatus
from app.models.authorization import Group
from app.models.authorization import Organisation
from app.models.authorization import User
from app.models.cases import CaseState, CaseProtagonist
from app.util import file_sha256sum, str_to_bool, assert_type_mml
from app.util import stream_sha256sum

ALLOWED_EXTENSIONS = {'png', 'svg'}
POSTGRES_INT_MAX = 2147483647
POSTGRES_BIGINT_MAX = 9223372036854775807

log = app.logger


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
            raise marshmallow.exceptions.ValidationError("Invalid parent id for the directory",
                                                         field_name="parent_id")
        directory = NoteDirectory.query.filter(
            NoteDirectory.id == parent_id,
            NoteDirectory.case_id == case_id
        ).first()
        if directory:
            if current_id is not None and directory.parent_id == int(current_id):
                raise marshmallow.exceptions.ValidationError("Invalid parent id for the directory",
                                                             field_name="parent_id")
            return parent_id

        raise marshmallow.exceptions.ValidationError("Invalid parent id for the directory",
                                                     field_name="parent_id")

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
    user_password: Optional[str] = auto_field('password', required=False)
    user_isadmin: bool = fields.Boolean(required=True)
    user_id: Optional[int] = fields.Integer(required=False)
    user_primary_organisation_id: Optional[int] = fields.Integer(required=False)
    user_is_service_account: Optional[bool] = auto_field('is_service_account', required=False)

    class Meta:
        model = User
        load_instance = True
        include_fk = True
        exclude = ['api_key', 'password', 'ctx_case', 'ctx_human_case', 'user', 'name', 'email', 'is_service_account']
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
                raise marshmallow.exceptions.ValidationError('User name already taken',
                                                             field_name="user_login")

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
                raise marshmallow.exceptions.ValidationError('User email already taken',
                                                             field_name="user_email")

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
                raise marshmallow.exceptions.ValidationError(password_error,
                                                             field_name="user_password")

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
                        field_name="directory_id",
                        type=int)

        directory = NoteDirectory.query.filter(
            NoteDirectory.id == data.get('directory_id'),
            NoteDirectory.case_id == kwargs.get('caseid')
        ).first()
        if directory:
            return data

        raise marshmallow.exceptions.ValidationError("Invalid directory id for the case",
                                                     field_name="directory_id")

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

        raise marshmallow.exceptions.ValidationError("Invalid directory id for the case",
                                                     field_name="directory_id")

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
                        field_name="asset_name",
                        type=str)

        assert_type_mml(input_var=data.asset_id,
                        field_name="asset_id",
                        type=int,
                        allow_none=True)

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
        if not file_storage.filename:
            return None

        fpath, message = store_icon(file_storage)

        if fpath is None:
            raise marshmallow.exceptions.ValidationError(
                message,
                field_name=field_type
            )

        setattr(self, field_type, fpath)

        return fpath


class CaseAssetsSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseAssets objects.

    This schema defines the fields to include when serializing and deserializing CaseAssets objects.
    It includes fields for the asset name, IOC links, asset enrichment, asset type, and custom attributes.
    It also includes methods for verifying the asset type ID and analysis status ID, and for merging custom attributes.

    """
    asset_name: str = auto_field('asset_name', required=True, allow_none=False)
    ioc_links: List[int] = fields.List(fields.Integer, required=False)
    asset_enrichment: str = auto_field('asset_enrichment', required=False)
    asset_type: AssetTypeSchema = ma.Nested(AssetTypeSchema, required=False)
    alerts = fields.Nested('AlertSchema', many=True, exclude=['assets'])
    analysis_status = fields.Nested('AnalysisStatusSchema', required=False)

    class Meta:
        model = CaseAssets
        include_fk = True
        load_instance = True
        unknown = EXCLUDE

    @staticmethod
    def is_unique_for_customer(customer_id, request_data):
        """
        Check if the asset is unique for the customer
        """

        if request_data.get('asset_name') is None:
            raise marshmallow.exceptions.ValidationError("Asset name is required",
                                                         field_name="asset_name")

        case_alias = aliased(Cases)
        asset_alias = aliased(CaseAssets)

        asset = db.session.query(
            asset_alias.asset_id
        ).join(
            case_alias, asset_alias.case_id == case_alias.case_id
        ).filter(
            func.lower(asset_alias.asset_name) == request_data.get('asset_name').lower(),
            asset_alias.asset_type_id == request_data.get('asset_type_id'),
            asset_alias.asset_id != request_data.get('asset_id'),
            case_alias.client_id == customer_id
        ).first()
        if asset is not None:
            return asset

        return None

    def is_unique_for_customer_from_cid(self, case_id, request_data):
        """
        Check if the asset is unique for the customer
        """

        case_alias = aliased(Cases)

        customer_id = db.session.query(
            case_alias.client_id
        ).filter(
            case_alias.case_id == case_id
        ).first()

        if customer_id is None:
            raise marshmallow.exceptions.ValidationError("Case not found")

        customer_id = customer_id[0]

        return self.is_unique_for_customer(customer_id, request_data)

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
            raise marshmallow.exceptions.ValidationError("Asset name already exists in this case",
                                                         field_name="asset_name")

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
        assert_type_mml(input_var=data.get('asset_type_id'),
                        field_name="asset_type_id",
                        type=int)

        asset_type = AssetsType.query.filter(AssetsType.asset_id == data.get('asset_type_id')).count()
        if not asset_type:
            raise marshmallow.exceptions.ValidationError("Invalid asset type ID",
                                                         field_name="asset_type_id")

        assert_type_mml(input_var=data.get('analysis_status_id'),
                        field_name="analysis_status_id", type=int,
                        allow_none=True)

        if data.get('analysis_status_id'):
            status = AnalysisStatus.query.filter(AnalysisStatus.id == data.get('analysis_status_id')).count()
            if not status:
                raise marshmallow.exceptions.ValidationError("Invalid analysis status ID",
                                                             field_name="analysis_status_id")

        if data.get('asset_tags'):
            for tag in data.get('asset_tags').split(','):
                if not isinstance(tag, str):
                    raise marshmallow.exceptions.ValidationError("All items in list must be strings",
                                                                 field_name="asset_tags")
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
            raise marshmallow.exceptions.ValidationError(
                "IOC type name already exists",
                field_name="type_name"
            )

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
                raise marshmallow.exceptions.ValidationError("Invalid IOC type ID", field_name="ioc_type_id")

            if ioc_type.type_validation_regex:
                if not re.fullmatch(ioc_type.type_validation_regex, data.get('ioc_value'), re.IGNORECASE):
                    error = f"The input doesn\'t match the expected format " \
                            f"(expected: {ioc_type.type_validation_expect or ioc_type.type_validation_regex})"
                    raise marshmallow.exceptions.ValidationError(error, field_name="ioc_ioc_value")

        if data.get('ioc_tlp_id'):
            assert_type_mml(input_var=data.get('ioc_tlp_id'), field_name="ioc_tlp_id", type=int,
                            max_val=POSTGRES_INT_MAX)

            Tlp.query.filter(Tlp.tlp_id == data.get('ioc_tlp_id')).count()

        if data.get('ioc_tags'):
            for tag in data.get('ioc_tags').split(','):
                if not isinstance(tag, str):
                    raise marshmallow.exceptions.ValidationError("All items in list must be strings",
                                                                 field_name="ioc_tags")
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
        exclude = ['password', 'ctx_case', 'ctx_human_case']
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
    event_category_id: int = fields.Integer(required=True, allow_none=False)
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
        date_time = "{}{}".format(event_date, event_tz)
        date_time_wtz = "{}".format(event_date)

        try:
            self.event_date = dateutil.parser.isoparse(date_time)
            self.event_date_wtz = dateutil.parser.isoparse(date_time_wtz)
        except Exception as e:
            raise marshmallow.exceptions.ValidationError("Invalid date time", field_name="event_date")

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
            raise marshmallow.exceptions.ValidationError("Received empty data")

        for field in ['event_title', 'event_date', 'event_tz', 'event_category_id', 'event_assets', 'event_iocs']:
            if field not in data:
                raise marshmallow.exceptions.ValidationError(f"Missing field {field}", field_name=field)

        assert_type_mml(input_var=int(data.get('event_category_id')),
                        field_name='event_category_id',
                        type=int)

        event_cat = EventCategory.query.filter(EventCategory.id == int(data.get('event_category_id'))).count()
        if not event_cat:
            raise marshmallow.exceptions.ValidationError("Invalid event category ID", field_name="event_category_id")

        assert_type_mml(input_var=data.get('event_assets'),
                        field_name='event_assets',
                        type=list)

        for asset in data.get('event_assets'):

            assert_type_mml(input_var=int(asset),
                            field_name='event_assets',
                            type=int)

            ast = CaseAssets.query.filter(CaseAssets.asset_id == asset).count()
            if not ast:
                raise marshmallow.exceptions.ValidationError("Invalid assets ID", field_name="event_assets")

        assert_type_mml(input_var=data.get('event_iocs'),
                        field_name='event_iocs',
                        type=list)

        for ioc in data.get('event_iocs'):

            assert_type_mml(input_var=int(ioc),
                            field_name='event_iocs',
                            type=int)

            ast = Ioc.query.filter(Ioc.ioc_id == ioc).count()
            if not ast:
                raise marshmallow.exceptions.ValidationError("Invalid IOC ID", field_name="event_assets")

        if data.get('event_color') and data.get('event_color') not in ['#fff', '#1572E899', '#6861CE99', '#48ABF799',
                                                                       '#31CE3699', '#F2596199', '#FFAD4699']:
            data['event_color'] = ''

        if data.get('event_tags'):
            for tag in data.get('event_tags').split(','):
                if not isinstance(tag, str):
                    raise marshmallow.exceptions.ValidationError("All items in list must be strings",
                                                                 field_name="event_tags")
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
            raise marshmallow.exceptions.ValidationError(
                "No file provided",
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
                    log.exception(e)
                    raise marshmallow.exceptions.ValidationError(
                        str(e),
                        field_name='file_password'
                    )

            else:
                file_storage.save(location)
                file_storage.close()
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


class ServerSettingsSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing ServerSettings objects.

    This schema defines the fields to include when serializing and deserializing ServerSettings objects.
    It includes fields for the HTTP proxy, HTTPS proxy, and whether to prevent post-modification repush.

    """
    http_proxy: Optional[str] = fields.String(required=False, allow_none=False)
    https_proxy: Optional[str] = fields.String(required=False, allow_none=False)
    prevent_post_mod_repush: Optional[bool] = fields.Boolean(required=False)

    class Meta:
        model = ServerSettings
        load_instance = True
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
            raise marshmallow.exceptions.ValidationError(
                "Case classification name already exists",
                field_name="name"
            )

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
            raise marshmallow.exceptions.ValidationError(
                "Evidence type already exists",
                field_name="name"
            )

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

        raise marshmallow.exceptions.ValidationError("Invalid client id",
                                                     field_name="case_customer")

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
            raise marshmallow.exceptions.ValidationError("Invalid user id for assignee",
                                                         field_name="task_assignees_id")

        assert_type_mml(input_var=data.get('task_status_id'),
                        field_name='task_status_id',
                        type=int)
        status = TaskStatus.query.filter(TaskStatus.id == data.get('task_status_id')).count()
        if not status:
            raise marshmallow.exceptions.ValidationError("Invalid task status ID",
                                                         field_name="task_status_id")

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


class CaseTaskSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing CaseTask objects.

    This schema defines the fields to include when serializing and deserializing CaseTask objects.
    It includes fields for the task title, task status ID, task assignees ID, task assignees, and CSRF token.

    """
    task_title: str = auto_field('task_title', required=True, validate=Length(min=2), allow_none=False)
    task_status_id: int = auto_field('task_status_id', required=True)
    task_assignees_id: Optional[List[int]] = fields.List(fields.Integer, required=False, allow_none=True)
    task_assignees: Optional[List[Dict[str, Any]]] = fields.List(fields.Dict, required=False, allow_none=True)

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
            raise marshmallow.exceptions.ValidationError("Invalid task status ID",
                                                         field_name="task_status_id")

        if data.get('task_tags'):
            for tag in data.get('task_tags').split(','):
                if not isinstance(tag, str):
                    raise marshmallow.exceptions.ValidationError("All items in list must be strings",
                                                                 field_name="task_tags")
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
                raise marshmallow.exceptions.ValidationError(
                    "Group already exists",
                    field_name="group_name"
                )

        return data

    @pre_load
    def parse_permissions(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """Parses the group permissions.

        This method parses the group permissions specified in the data and converts them to an access control mask.
        If no permissions are specified, it sets the mask to 0.

        Args:
            data: The data to load.
            kwargs: Additional keyword arguments.

        Returns:
            The loaded data with the access control mask.

        """
        permissions = data.get('group_permissions')
        if type(permissions) != list and not isinstance(permissions, type(None)):
            permissions = [permissions]

        if permissions is not None:
            data['group_permissions'] = ac_mask_from_val_list(permissions)

        else:
            data['group_permissions'] = 0

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
                raise marshmallow.exceptions.ValidationError(
                    "Organisation name already exists",
                    field_name="org_name"
                )

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
                   'id', 'name', 'email', 'user', 'uuid']
        unknown = EXCLUDE


def validate_ioc_type(type_id: int) -> None:
    """Validates the IOC type ID.

    This function validates the IOC type ID by checking if it exists in the database.
    If the ID is invalid, it raises a validation error.

    Args:
        type_id: The IOC type ID to validate.

    Raises:
        ValidationError: If the IOC type ID is invalid.

    """
    if not IocType.query.get(type_id):
        raise ValidationError("Invalid ioc_type ID")


def validate_ioc_tlp(tlp_id: int) -> None:
    """Validates the IOC TLP ID.

    This function validates the IOC TLP ID by checking if it exists in the database.
    If the ID is invalid, it raises a validation error.

    Args:
        tlp_id: The IOC TLP ID to validate.

    Raises:
        ValidationError: If the IOC TLP ID is invalid.

    """
    if not Tlp.query.get(tlp_id):
        raise ValidationError("Invalid ioc_tlp ID")


def validate_asset_type(asset_id: int) -> None:
    """Validates the asset type ID.

    This function validates the asset type ID by checking if it exists in the database.
    If the ID is invalid, it raises a validation error.

    Args:
        asset_id: The asset type ID to validate.

    Raises:
        ValidationError: If the asset type ID is invalid.

    """
    if not AssetsType.query.get(asset_id):
        raise ValidationError("Invalid asset_type ID")


def validate_asset_tlp(tlp_id: int) -> None:
    """Validates the asset TLP ID.

    This function validates the asset TLP ID by checking if it exists in the database.
    If the ID is invalid, it raises a validation error.

    Args:
        tlp_id: The asset TLP ID to validate.

    Raises:
        ValidationError: If the asset TLP ID is invalid.

    """
    if not Tlp.query.get(tlp_id):
        raise ValidationError("Invalid asset_tlp ID")


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


class AnalysisStatusSchema(ma.SQLAlchemyAutoSchema):
    """Schema for serializing and deserializing AnalysisStatus objects.

    This schema defines the fields to include when serializing and deserializing AnalysisStatus objects.
    It includes fields for the analysis status name and analysis status value.

    """

    class Meta:
        model = AnalysisStatus
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
    assets = ma.Nested(CaseAssetsSchema, many=True)
    resolution_status = ma.Nested(AlertResolutionSchema)

    class Meta:
        model = Alert
        include_relationships = True
        include_fk = True
        load_instance = True
        unknown = EXCLUDE

    @pre_load
    def verify_data(self, data: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
        """
        Verify that the alert tags are valid and save them if they don't exist
        """
        if data.get('alert_tags'):
            for tag in data.get('alert_tags').split(','):
                if not isinstance(tag, str):
                    raise marshmallow.exceptions.ValidationError("All items in list must be strings",
                                                                 field_name="alert_tags")
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

    status_name = ma.Method("get_status_name")
    protagonists = ma.Method("get_protagonists")

    class Meta:
        model = Cases
        include_fk = True
        load_instance = True
        include_relationships = True
        unknown = EXCLUDE
