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
from typing import Optional

from flask_sqlalchemy.pagination import Pagination
from sqlalchemy import and_

from app.datamgmt.db_operations import db_delete
from app.models.cases import Cases
from app.models.comments import Comments
from app.models.comments import EventComments
from app.models.comments import TaskComments
from app.models.comments import IocComments
from app.models.comments import AssetComments
from app.models.comments import EvidencesComments
from app.models.comments import NotesComments
from app.models.pagination_parameters import PaginationParameters
from app.models.authorization import User
from app.models.customers import Client


def _get_filtered_comments(query, pagination_parameters: PaginationParameters) -> Pagination:
    query = query.order_by(
        Comments.comment_date.asc()
    )
    return query.paginate(page=pagination_parameters.get_page(), per_page=pagination_parameters.get_per_page())


def get_filtered_alert_comments(alert_identifier: int, pagination_parameters: PaginationParameters) -> Pagination:
    query = Comments.query.filter(Comments.comment_alert_id == alert_identifier)
    return query.paginate(page=pagination_parameters.get_page(), per_page=pagination_parameters.get_per_page())


def get_filtered_asset_comments(asset_identifier: int, pagination_parameters: PaginationParameters) -> Pagination:
    query = Comments.query.filter(
        AssetComments.comment_asset_id == asset_identifier
    ).join(
        AssetComments,
        Comments.comment_id == AssetComments.comment_id
    )
    return _get_filtered_comments(query, pagination_parameters)


def get_filtered_evidence_comments(evidence_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    query = Comments.query.filter(
        EvidencesComments.comment_evidence_id == evidence_identifier
    ).join(
        EvidencesComments,
        Comments.comment_id == EvidencesComments.comment_id
    )
    return _get_filtered_comments(query, pagination_parameters)


def get_filtered_ioc_comments(ioc_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    query = Comments.query.filter(
        IocComments.comment_ioc_id == ioc_identifier
    ).join(
        IocComments,
        Comments.comment_id == IocComments.comment_id
    )
    return _get_filtered_comments(query, pagination_parameters)


def get_filtered_note_comments(note_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    query = Comments.query.filter(
        NotesComments.comment_note_id == note_identifier
    ).join(
        NotesComments,
        Comments.comment_id == NotesComments.comment_id
    )
    return _get_filtered_comments(query, pagination_parameters)


def get_filtered_task_comments(task_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    query = Comments.query.filter(
        TaskComments.comment_task_id == task_identifier
    ).join(
        TaskComments,
        Comments.comment_id == TaskComments.comment_id
    )
    return _get_filtered_comments(query, pagination_parameters)


def get_filtered_event_comments(event_identifier, pagination_parameters: PaginationParameters) -> Pagination:
    query = Comments.query.filter(
        EventComments.comment_event_id == event_identifier
    ).join(
        EventComments,
        Comments.comment_id == EventComments.comment_id
    )
    return _get_filtered_comments(query, pagination_parameters)


def delete_comment(comment: Comments):
    db_delete(comment)


def user_has_comments(user: User):
    comment = Comments.query.filter(Comments.comment_user_id == user.id).first()
    return comment is not None


def search_comments(search_value):
    search_condition = and_()
    comments = Comments.query.filter(
        Comments.comment_text.like(f'%{search_value}%'),
        Cases.client_id == Client.client_id,
        search_condition
    ).with_entities(
        Comments.comment_id,
        Comments.comment_text,
        Cases.name.label('case_name'),
        Client.name.label('customer_name'),
        Cases.case_id
    ).join(
        Comments.case
    ).join(
        Cases.client
    ).order_by(
        Client.name
    ).all()

    return [row._asdict() for row in comments]


def get_comment(user, identifier) -> Optional[Comments]:
    return Comments.query.filter(
        Comments.comment_id == identifier,
        Comments.comment_user_id == user.id
    ).first()
