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
from flask import session
from flask import request
from marshmallow.exceptions import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.models.authorization import Permissions
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.blueprints.access_controls import ac_api_return_access_denied
from app.schema.marshables import CommentSchema
from app.business.comments import comments_get_filtered_by_alert
from app.business.comments import comments_create_for_alert
from app.business.comments import comments_delete_for_alert
from app.business.comments import comments_get_for_alert
from app.blueprints.rest.case_comments import case_comment_update
from app.business.alerts import alerts_get
from app.business.alerts import alerts_exists
from app.blueprints.iris_user import iris_current_user
from app.models.errors import ObjectNotFoundError


class CommentsOperations:

    def __init__(self):
        self._schema = CommentSchema()

    def search(self, alert_identifier):
        pagination_parameters = parse_pagination_parameters(request)
        try:
            comments = comments_get_filtered_by_alert(
                iris_current_user,
                (session.get('permissions') or 0),
                alert_identifier,
                pagination_parameters,
                fallback_customer_access=ac_current_user_has_customer_access
            )
            return response_api_paginated(self._schema, comments)
        except ObjectNotFoundError:
            return response_api_not_found()

    def create(self, alert_identifier):
        try:
            comment = self._schema.load(request.get_json())
            comments_create_for_alert(
                iris_current_user,
                (session.get('permissions') or 0),
                comment,
                alert_identifier,
                fallback_customer_access=ac_current_user_has_customer_access
            )
            result = self._schema.dump(comment)
            return response_api_created(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def read(self, alert_identifier, identifier):
        try:
            alert = alerts_get(
                iris_current_user,
                (session.get('permissions') or 0),
                alert_identifier,
                fallback_customer_access=ac_current_user_has_customer_access
            )
            comment = comments_get_for_alert(alert, identifier)
            result = self._schema.dump(comment)
            return response_api_success(result)
        except ValidationError as e:
            return response_api_error('Data error', data=e.normalized_messages())
        except ObjectNotFoundError:
            return response_api_not_found()

    def update(self, alert_identifier, identifier):
        if not alerts_exists(iris_current_user, (session.get('permissions') or 0), alert_identifier):
            return response_api_not_found()
        return case_comment_update(identifier, 'alerts', None)

    def delete(self, alert_identifier, identifier):
        try:
            alert = alerts_get(
                iris_current_user,
                (session.get('permissions') or 0),
                alert_identifier,
                fallback_customer_access=ac_current_user_has_customer_access
            )
            comment = comments_get_for_alert(alert, identifier)
            if comment.comment_user_id != iris_current_user.id:
                return ac_api_return_access_denied()

            comments_delete_for_alert(comment)
            return response_api_deleted()
        except ObjectNotFoundError:
            return response_api_not_found()


alerts_comments_blueprint = Blueprint('alerts_comments', __name__, url_prefix='/<int:alert_identifier>/comments')
comments_operations = CommentsOperations()


@alerts_comments_blueprint.get('')
@ac_api_requires(Permissions.alerts_read)
def get_alerts_comments(alert_identifier):
    return comments_operations.search(alert_identifier)


@alerts_comments_blueprint.post('')
@ac_api_requires(Permissions.alerts_write)
def create_alerts_comment(alert_identifier):
    return comments_operations.create(alert_identifier)


@alerts_comments_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.alerts_read)
def read_alerts_comment(alert_identifier, identifier):
    return comments_operations.read(alert_identifier, identifier)


@alerts_comments_blueprint.put('/<int:identifier>')
@ac_api_requires(Permissions.alerts_write)
def update_alerts_comment(alert_identifier, identifier):
    return comments_operations.update(alert_identifier, identifier)


@alerts_comments_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.alerts_write)
def delete_alerts_comment(alert_identifier, identifier):
    return comments_operations.delete(alert_identifier, identifier)
