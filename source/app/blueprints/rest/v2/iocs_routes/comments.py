#  IRIS Source Code
#  Copyright (C) 2025 - DFIR-IRIS
#  contact@dfir-iris.org
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

from flask import Blueprint
from flask import request
from marshmallow import ValidationError

from app.blueprints.iris_user import iris_current_user
from app.blueprints.access_controls import ac_api_requires, ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.business.comments import comments_get_filtered_by_ioc
from app.business.comments import comments_create_for_ioc
from app.business.comments import comments_get_for_ioc
from app.business.comments import comments_delete_for_ioc
from app.business.iocs import iocs_get
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import CommentSchema
from app.models.authorization import CaseAccessLevel
from app.blueprints.rest.case_comments import case_comment_update


class CommentsOperations:

    def __init__(self):
        self._schema = CommentSchema()

    @staticmethod
    def _get_ioc(ioc_identifier, possible_case_access_levels):
        ioc = iocs_get(ioc_identifier)
        if not ac_fast_check_current_user_has_case_access(ioc.case_id, possible_case_access_levels):
            raise ObjectNotFoundError()
        return ioc

    def search(self, ioc_identifier):
        try:
            ioc = self._get_ioc(ioc_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access])

            pagination_parameters = parse_pagination_parameters(request)
            comments = comments_get_filtered_by_ioc(ioc, pagination_parameters)
            return response_api_paginated(self._schema, comments)
        except ObjectNotFoundError:
            return response_api_not_found()

    def create(self, ioc_identifier):
        try:
            ioc = self._get_ioc(ioc_identifier, [CaseAccessLevel.full_access])

            comment = self._schema.load(request.get_json())
            comments_create_for_ioc(iris_current_user, ioc, comment)

            result = self._schema.dump(comment)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def read(self, ioc_identifier, identifier):
        try:
            ioc = self._get_ioc(ioc_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access])
            comment = comments_get_for_ioc(ioc, identifier)
            result = self._schema.dump(comment)
            return response_api_success(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, ioc_identifier, identifier):
        try:
            ioc = self._get_ioc(ioc_identifier, [CaseAccessLevel.full_access])
            return case_comment_update(identifier, 'ioc', ioc.case_id)
        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, ioc_identifier, identifier):
        try:
            ioc = self._get_ioc(ioc_identifier, [CaseAccessLevel.full_access])
            comment = comments_get_for_ioc(ioc, identifier)
            if comment.comment_user_id != iris_current_user.id:
                return ac_api_return_access_denied()

            comments_delete_for_ioc(iris_current_user, ioc, comment)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()


iocs_comments_blueprint = Blueprint('iocs_comments', __name__, url_prefix='/<int:ioc_identifier>/comments')
comments_operations = CommentsOperations()


@iocs_comments_blueprint.get('')
@ac_api_requires()
def get_iocs_comments(ioc_identifier):
    return comments_operations.search(ioc_identifier)


@iocs_comments_blueprint.post('')
@ac_api_requires()
def create_iocs_comment(ioc_identifier):
    return comments_operations.create(ioc_identifier)


@iocs_comments_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_ioc_comment(ioc_identifier, identifier):
    return comments_operations.read(ioc_identifier, identifier)


@iocs_comments_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_assets_comment(ioc_identifier, identifier):
    return comments_operations.update(ioc_identifier, identifier)


@iocs_comments_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_ioc_comment(ioc_identifier, identifier):
    return comments_operations.delete(ioc_identifier, identifier)
