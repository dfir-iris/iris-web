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
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.iris_user import iris_current_user
from app.business.comments import comments_get_filtered_by_event
from app.business.comments import comments_create_for_event
from app.business.comments import comments_get_for_event
from app.business.comments import comments_delete_for_event
from app.business.events import events_get
from app.models.errors import ObjectNotFoundError
from app.models.cases import CasesEvent
from app.schema.marshables import CommentSchema
from app.models.authorization import CaseAccessLevel
from app.blueprints.rest.case_comments import case_comment_update


class CommentsOperations:

    def __init__(self):
        self._schema = CommentSchema()

    @staticmethod
    def _get_event(event_identifier, possible_case_access_levels) -> CasesEvent:
        event = events_get(event_identifier)
        if not ac_fast_check_current_user_has_case_access(event.case_id, possible_case_access_levels):
            raise ObjectNotFoundError()
        return event

    def search(self, event_identifier):
        try:
            event = self._get_event(event_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access])

            pagination_parameters = parse_pagination_parameters(request)

            comments = comments_get_filtered_by_event(event, pagination_parameters)
            return response_api_paginated(self._schema, comments)
        except ObjectNotFoundError:
            return response_api_not_found()

    def create(self, event_identifier):
        try:
            event = self._get_event(event_identifier, [CaseAccessLevel.full_access])
            comment = self._schema.load(request.get_json())
            comments_create_for_event(iris_current_user, event, comment)

            result = self._schema.dump(comment)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def read(self, event_identifier, identifier):
        try:
            event = self._get_event(event_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access])
            comment = comments_get_for_event(event, identifier)
            result = self._schema.dump(comment)
            return response_api_success(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, event_identifier, identifier):
        try:
            event = self._get_event(event_identifier, [CaseAccessLevel.full_access])
            return case_comment_update(identifier, 'events', event.case_id)
        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, event_identifier, identifier):
        try:
            event = self._get_event(event_identifier, [CaseAccessLevel.full_access])
            comment = comments_get_for_event(event, identifier)
            if comment.comment_user_id != iris_current_user.id:
                return ac_api_return_access_denied()

            comments_delete_for_event(iris_current_user, event, comment)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()


events_comments_blueprint = Blueprint('events_comments', __name__, url_prefix='/<int:event_identifier>/comments')
comments_operations = CommentsOperations()


@events_comments_blueprint.get('')
@ac_api_requires()
def get_event_comments(event_identifier):
    return comments_operations.search(event_identifier)


@events_comments_blueprint.post('')
@ac_api_requires()
def create_event_comment(event_identifier):
    return comments_operations.create(event_identifier)


@events_comments_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_event_comment(event_identifier, identifier):
    return comments_operations.read(event_identifier, identifier)


@events_comments_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_assets_comment(event_identifier, identifier):
    return comments_operations.update(event_identifier, identifier)


@events_comments_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_task_comment(event_identifier, identifier):
    return comments_operations.delete(event_identifier, identifier)
