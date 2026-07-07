#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
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
from flask import session
from marshmallow.exceptions import ValidationError

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_current_user_has_customer_access
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_paginated
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.parsing import parse_pagination_parameters
from app.business.comments import comments_create_for_alert_cluster
from app.business.comments import comments_delete_for_alert_cluster
from app.business.comments import comments_get_filtered_by_alert_cluster
from app.business.comments import comments_get_for_alert_cluster
from app.models.authorization import Permissions
from app.models.errors import ObjectNotFoundError
from app.schema.marshables import CommentSchema


alert_clusters_comments_blueprint = Blueprint(
    'alert_clusters_comments', __name__, url_prefix='/<int:cluster_identifier>/comments'
)
_schema = CommentSchema()


@alert_clusters_comments_blueprint.get('')
@ac_api_requires(Permissions.alert_clusters_read)
def list_cluster_comments(cluster_identifier):
    pagination = parse_pagination_parameters(request)
    try:
        comments = comments_get_filtered_by_alert_cluster(
            iris_current_user,
            (session.get('permissions') or 0),
            cluster_identifier,
            pagination,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_paginated(_schema, comments)


@alert_clusters_comments_blueprint.post('')
@ac_api_requires(Permissions.alert_clusters_write)
def create_cluster_comment(cluster_identifier):
    try:
        comment = _schema.load(request.get_json() or {})
    except ValidationError as exc:
        return response_api_error('Data error', data=exc.normalized_messages())
    try:
        comments_create_for_alert_cluster(
            iris_current_user,
            (session.get('permissions') or 0),
            comment,
            cluster_identifier,
            fallback_customer_access=ac_current_user_has_customer_access,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_created(_schema.dump(comment))


@alert_clusters_comments_blueprint.get('/<int:identifier>')
@ac_api_requires(Permissions.alert_clusters_read)
def read_cluster_comment(cluster_identifier, identifier):
    # Verify caller can see the parent cluster before returning the
    # comment — otherwise an authorised-by-comment-id lookup would leak
    # comment text across tenants.
    try:
        comments_get_filtered_by_alert_cluster(
            iris_current_user,
            (session.get('permissions') or 0),
            cluster_identifier,
            parse_pagination_parameters(request),
            fallback_customer_access=ac_current_user_has_customer_access,
        )
        comment = comments_get_for_alert_cluster(cluster_identifier, identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_schema.dump(comment))


@alert_clusters_comments_blueprint.delete('/<int:identifier>')
@ac_api_requires(Permissions.alert_clusters_write)
def delete_cluster_comment(cluster_identifier, identifier):
    try:
        # Access check on the parent cluster.
        comments_get_filtered_by_alert_cluster(
            iris_current_user,
            (session.get('permissions') or 0),
            cluster_identifier,
            parse_pagination_parameters(request),
            fallback_customer_access=ac_current_user_has_customer_access,
        )
        comment = comments_get_for_alert_cluster(cluster_identifier, identifier)
    except ObjectNotFoundError:
        return response_api_not_found()
    if comment.comment_user_id != iris_current_user.id:
        return ac_api_return_access_denied()
    comments_delete_for_alert_cluster(comment)
    return response_api_deleted()
