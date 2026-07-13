#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""v2 REST routes for war-room teams.

Teams are per-war-room groupings used as @-mention targets. The URL
layout mirrors members:

    GET    /<war_room_id>/teams                  list teams
    POST   /<war_room_id>/teams                  create a team
    GET    /<war_room_id>/teams/<tid>            get a team + its members
    PATCH  /<war_room_id>/teams/<tid>            rename / recolor
    DELETE /<war_room_id>/teams/<tid>            remove
    POST   /<war_room_id>/teams/<tid>/members    add a user
    DELETE /<war_room_id>/teams/<tid>/members/<uid>   remove
"""

from flask import Blueprint, request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.war_room_teams import war_room_team_create
from app.business.war_room_teams import war_room_team_delete
from app.business.war_room_teams import war_room_team_get
from app.business.war_room_teams import war_room_team_list
from app.business.war_room_teams import war_room_team_member_add
from app.business.war_room_teams import war_room_team_member_remove
from app.business.war_room_teams import war_room_team_members_list
from app.business.war_room_teams import war_room_team_update
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


war_rooms_teams_blueprint = Blueprint(
    'war_rooms_teams_rest_v2', __name__, url_prefix='/<int:war_room_id>/teams'
)


def _serialize_team(team, member_ids=None):
    return {
        'team_id': team.team_id,
        'war_room_id': team.war_room_id,
        'name': team.name,
        'description': team.description,
        'color': team.color,
        'created_at': team.created_at.isoformat() if team.created_at else None,
        'created_by_id': team.created_by_id,
        'member_ids': sorted(member_ids) if member_ids is not None else None,
    }


def _serialize_member(row):
    return {
        'team_id': row.team_id,
        'user_id': row.user_id,
        'added_at': row.added_at.isoformat() if row.added_at else None,
        'added_by_id': row.added_by_id,
    }


def _team_member_ids(team_id):
    """User IDs for a team — skips the war-room scope check because the
    caller has already resolved the team belongs to this war room."""
    from app.db import db
    from app.models.war_rooms import WarRoomTeamMember
    rows = (
        db.session.query(WarRoomTeamMember.user_id)
        .filter(WarRoomTeamMember.team_id == team_id)
        .all()
    )
    return {r.user_id for r in rows}


@war_rooms_teams_blueprint.get('')
@ac_api_requires()
def list_teams(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    teams = war_room_team_list(war_room_id)
    data = [
        _serialize_team(t, _team_member_ids(t.team_id))
        for t in teams
    ]
    return response_api_success(data=data)


@war_rooms_teams_blueprint.post('')
@ac_api_requires()
def create_team(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        team = war_room_team_create(
            war_room_id,
            name=raw.get('name'),
            description=raw.get('description'),
            color=raw.get('color'),
            created_by_id=iris_current_user.id,
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_created(_serialize_team(team, set()))


@war_rooms_teams_blueprint.get('/<int:team_id>')
@ac_api_requires()
def get_team(war_room_id, team_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        team = war_room_team_get(war_room_id, team_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(_serialize_team(team, _team_member_ids(team_id)))


@war_rooms_teams_blueprint.patch('/<int:team_id>')
@ac_api_requires()
def update_team(war_room_id, team_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        team = war_room_team_update(
            war_room_id, team_id,
            name=raw.get('name'),
            description=raw.get('description'),
            color=raw.get('color'),
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    return response_api_success(_serialize_team(team, _team_member_ids(team_id)))


@war_rooms_teams_blueprint.delete('/<int:team_id>')
@ac_api_requires()
def delete_team(war_room_id, team_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room_team_delete(war_room_id, team_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_deleted()


# --- Team members ----------------------------------------------------------

@war_rooms_teams_blueprint.get('/<int:team_id>/members')
@ac_api_requires()
def list_team_members(war_room_id, team_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        rows = war_room_team_members_list(war_room_id, team_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(data=[_serialize_member(r) for r in rows])


@war_rooms_teams_blueprint.post('/<int:team_id>/members')
@ac_api_requires()
def add_team_member(war_room_id, team_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')
    try:
        row, auto_added_room_member = war_room_team_member_add(
            war_room_id, team_id,
            user_id=raw.get('user_id'),
            added_by_id=iris_current_user.id,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())
    payload = _serialize_member(row)
    # Flag surfaced so the SPA can show "also added to the war room as
    # responder" without a follow-up GET on the members list.
    payload['auto_added_room_member'] = bool(auto_added_room_member)
    return response_api_created(payload)


@war_rooms_teams_blueprint.delete('/<int:team_id>/members/<int:user_id>')
@ac_api_requires()
def remove_team_member(war_room_id, team_id, user_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room_team_member_remove(war_room_id, team_id, user_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_deleted()
