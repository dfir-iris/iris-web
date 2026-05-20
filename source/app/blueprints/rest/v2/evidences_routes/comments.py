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

from app.blueprints.access_controls import ac_api_requires, ac_fast_check_current_user_has_case_access
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.business.comments import comments_get_filtered_by_evidence
from app.business.comments import comments_create_for_evidence
from app.business.comments import comments_get_for_evidence
from app.business.comments import comments_delete_for_evidence
from app.models.evidences import CaseReceivedFile
from app.business.evidences import evidences_get
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import CommentSchema
from app.models.authorization import CaseAccessLevel
from app.blueprints.rest.case_comments import case_comment_update


class CommentsOperations:

    def __init__(self):
        self._schema = CommentSchema()

    @staticmethod
    def _get_evidence(evidence_identifier, possible_case_access_levels) -> CaseReceivedFile:
        evidence = evidences_get(evidence_identifier)
        if not ac_fast_check_current_user_has_case_access(evidence.case_id, possible_case_access_levels):
            raise ObjectNotFoundError()
        return evidence

    def search(self, evidence_identifier):
        try:
            evidence = self._get_evidence(evidence_identifier,
                                          [CaseAccessLevel.read_only, CaseAccessLevel.full_access])

            pagination_parameters = parse_pagination_parameters(request)

            comments = comments_get_filtered_by_evidence(evidence, pagination_parameters)
            return response_api_paginated(self._schema, comments)
        except ObjectNotFoundError:
            return response_api_not_found()

    def create(self, evidence_identifier):
        try:
            evidence = self._get_evidence(evidence_identifier, [CaseAccessLevel.full_access])
            comment = self._schema.load(request.get_json())
            comments_create_for_evidence(iris_current_user, evidence, comment)

            result = self._schema.dump(comment)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, evidence_identifier, identifier):
        try:
            evidence = self._get_evidence(evidence_identifier, [CaseAccessLevel.full_access])
            return case_comment_update(identifier, 'evidence', evidence.case_id)
        except ObjectNotFoundError:
            return response_api_not_found()

    def read(self, event_identifier, identifier):
        try:
            evidence = self._get_evidence(event_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access])
            comment = comments_get_for_evidence(evidence, identifier)
            result = self._schema.dump(comment)
            return response_api_success(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, evidence_identifier, identifier):
        try:
            evidence = self._get_evidence(evidence_identifier, [CaseAccessLevel.full_access])
            comment = comments_get_for_evidence(evidence, identifier)
            if comment.comment_user_id != iris_current_user.id:
                return ac_api_return_access_denied()

            comments_delete_for_evidence(iris_current_user, evidence, comment)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()


evidences_comments_blueprint = Blueprint('evidences_comments', __name__, url_prefix='/<int:evidence_identifier>/comments')
comments_operations = CommentsOperations()


@evidences_comments_blueprint.get('')
@ac_api_requires()
def get_evidence_comments(evidence_identifier):
    return comments_operations.search(evidence_identifier)


@evidences_comments_blueprint.post('')
@ac_api_requires()
def create_evidence_comment(evidence_identifier):
    return comments_operations.create(evidence_identifier)


@evidences_comments_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_evidence_comment(evidence_identifier, identifier):
    return comments_operations.read(evidence_identifier, identifier)


@evidences_comments_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_assets_comment(evidence_identifier, identifier):
    return comments_operations.update(evidence_identifier, identifier)


@evidences_comments_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_evidence_comment(evidence_identifier, identifier):
    return comments_operations.delete(evidence_identifier, identifier)
