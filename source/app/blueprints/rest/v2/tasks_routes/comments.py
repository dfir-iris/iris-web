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
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_deleted
from app.business.comments import comments_get_filtered_by_task
from app.business.comments import comments_create_for_task
from app.business.comments import comments_get_for_task
from app.business.comments import comments_delete_for_task
from app.business.tasks import tasks_get
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import CommentSchema
from app.models.authorization import CaseAccessLevel
from app.blueprints.rest.case_comments import case_comment_update


class CommentsOperations:

    def __init__(self):
        self._schema = CommentSchema()

    @staticmethod
    def _get_task(task_identifier, possible_case_access_levels):
        task = tasks_get(task_identifier)
        if not ac_fast_check_current_user_has_case_access(task.task_case_id, possible_case_access_levels):
            raise ObjectNotFoundError()
        return task

    def search(self, task_identifier):
        try:
            task = self._get_task(task_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access])

            pagination_parameters = parse_pagination_parameters(request)

            comments = comments_get_filtered_by_task(task, pagination_parameters)
            return response_api_paginated(self._schema, comments)
        except ObjectNotFoundError:
            return response_api_not_found()

    def create(self, task_identifier):
        try:
            task = self._get_task(task_identifier, [CaseAccessLevel.full_access])

            comment = self._schema.load(request.get_json())
            comments_create_for_task(iris_current_user, task, comment)

            result = self._schema.dump(comment)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def read(self, task_identifier, identifier):
        try:
            task = self._get_task(task_identifier, [CaseAccessLevel.read_only, CaseAccessLevel.full_access])
            comment = comments_get_for_task(task, identifier)
            result = self._schema.dump(comment)
            return response_api_success(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, task_identifier, identifier):
        try:
            task = self._get_task(task_identifier, [CaseAccessLevel.full_access])
            return case_comment_update(identifier, 'tasks', task.task_case_id)
        except ObjectNotFoundError:
            return response_api_not_found()

    def delete(self, task_identifier, identifier):
        try:
            task = self._get_task(task_identifier, [CaseAccessLevel.full_access])
            comment = comments_get_for_task(task, identifier)
            if comment.comment_user_id != iris_current_user.id:
                return ac_api_return_access_denied()

            comments_delete_for_task(iris_current_user, task, comment)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()


tasks_comments_blueprint = Blueprint('tasks_comments', __name__, url_prefix='/<int:task_identifier>/comments')
comments_operations = CommentsOperations()


@tasks_comments_blueprint.get('')
@ac_api_requires()
def get_tasks_comments(task_identifier):
    return comments_operations.search(task_identifier)


@tasks_comments_blueprint.post('')
@ac_api_requires()
def create_tasks_comment(task_identifier):
    return comments_operations.create(task_identifier)


@tasks_comments_blueprint.get('/<int:identifier>')
@ac_api_requires()
def get_task_comment(task_identifier, identifier):
    return comments_operations.read(task_identifier, identifier)


@tasks_comments_blueprint.put('/<int:identifier>')
@ac_api_requires()
def update_assets_comment(task_identifier, identifier):
    return comments_operations.update(task_identifier, identifier)


@tasks_comments_blueprint.delete('/<int:identifier>')
@ac_api_requires()
def delete_task_comment(task_identifier, identifier):
    return comments_operations.delete(task_identifier, identifier)
