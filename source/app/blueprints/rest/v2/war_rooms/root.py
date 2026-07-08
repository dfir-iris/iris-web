#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""v2 REST routes for the War Room feature.

URL layout (mounted at `/api/v2/war-rooms`):

    GET    /                    list war rooms visible to the caller
    POST   /                    create a war room  [war_rooms_create]
    GET    /<id>                fetch a single war room
    PATCH  /<id>                update name/state/etc.   [war_rooms_write]
    DELETE /<id>                delete (cascade)         [war_rooms_create]

    GET    /<id>/members        list members
    POST   /<id>/members        add member (also grants ACL)
    DELETE /<id>/members/<uid>  remove member

    GET    /<id>/cases          list attached cases
    POST   /<id>/cases          attach a case
    DELETE /<id>/cases/<cid>    detach a case
"""

from flask import Blueprint
from flask import request

from app.blueprints.access_controls import ac_api_requires
from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_current_user_has_permission
from app.blueprints.access_controls import ac_fast_check_current_user_has_case_access
from app.blueprints.iris_user import iris_current_user
from app.blueprints.rest.endpoints import response_api_created
from app.blueprints.rest.endpoints import response_api_deleted
from app.blueprints.rest.endpoints import response_api_error
from app.blueprints.rest.endpoints import response_api_not_found
from app.blueprints.rest.endpoints import response_api_success
from app.blueprints.rest.v2.war_rooms.access import require_war_room_read
from app.blueprints.rest.v2.war_rooms.access import require_war_room_write
from app.business.war_room_chat import emit_system_event
from app.blueprints.rest.v2.war_rooms.serializers import serialize_case_attachment
from app.blueprints.rest.v2.war_rooms.serializers import serialize_member
from app.blueprints.rest.v2.war_rooms.serializers import serialize_war_room
from app.business.war_rooms import (
    war_room_add_member,
    war_room_archive,
    war_room_attach_case,
    war_room_cases_list,
    war_room_create,
    war_room_delete,
    war_room_detach_case,
    war_room_get,
    war_room_list_for_user,
    war_room_members_list,
    war_room_people,
    war_room_remove_member,
    war_room_unarchive,
    war_room_update,
)
from app.models.authorization import CaseAccessLevel
from app.models.authorization import Permissions
from app.models.errors import BusinessProcessingError
from app.models.errors import ObjectNotFoundError


from app.blueprints.rest.v2.war_rooms.chat import war_rooms_chat_blueprint
from app.blueprints.rest.v2.war_rooms.datastore import war_rooms_datastore_blueprint
from app.blueprints.rest.v2.war_rooms.notes import war_rooms_notes_blueprint
from app.blueprints.rest.v2.war_rooms.notes_folders import war_rooms_notes_folders_blueprint
from app.blueprints.rest.v2.war_rooms.sitreps import war_rooms_sitreps_blueprint
from app.blueprints.rest.v2.war_rooms.tasks import war_rooms_tasks_blueprint
from app.blueprints.rest.v2.war_rooms.timelines import war_rooms_timelines_blueprint


war_rooms_blueprint = Blueprint(
    'war_rooms_rest_v2', __name__, url_prefix='/war-rooms'
)
war_rooms_blueprint.register_blueprint(war_rooms_chat_blueprint)
war_rooms_blueprint.register_blueprint(war_rooms_tasks_blueprint)
war_rooms_blueprint.register_blueprint(war_rooms_notes_blueprint)
war_rooms_blueprint.register_blueprint(war_rooms_notes_folders_blueprint)
war_rooms_blueprint.register_blueprint(war_rooms_timelines_blueprint)
war_rooms_blueprint.register_blueprint(war_rooms_sitreps_blueprint)
war_rooms_blueprint.register_blueprint(war_rooms_datastore_blueprint)


def _is_admin():
    return ac_current_user_has_permission(Permissions.server_administrator)


@war_rooms_blueprint.get('')
@ac_api_requires()
def list_war_rooms():
    # The list endpoint is gated by `war_rooms_read` so non-permitted
    # users get a 403 rather than an empty list (an empty list would
    # falsely suggest the feature is enabled but they have no rooms).
    if not ac_current_user_has_permission(Permissions.war_rooms_read) \
            and not _is_admin():
        return ac_api_return_access_denied()

    state = request.args.get('state', type=str)
    search = request.args.get('search', type=str)
    # `archived` accepts a small controlled vocabulary:
    #   * absent / 'false' / '0' — live rooms only (default)
    #   * 'true' / '1'           — archived rooms only
    #   * 'any' / 'all'          — both
    archived_raw = (request.args.get('archived', type=str) or '').strip().lower()
    if archived_raw in ('true', '1'):
        archived = True
    elif archived_raw in ('any', 'all'):
        archived = 'any'
    else:
        archived = False

    rooms = war_room_list_for_user(
        iris_current_user.id, is_admin=_is_admin(),
        state=state, search=search, archived=archived,
    )
    return response_api_success(data=[serialize_war_room(r) for r in rooms])


@war_rooms_blueprint.post('')
@ac_api_requires()
def create_war_room():
    if not ac_current_user_has_permission(Permissions.war_rooms_create) \
            and not _is_admin():
        return ac_api_return_access_denied()

    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')

    try:
        war_room = war_room_create(
            name=raw.get('name'),
            description=raw.get('description'),
            state=raw.get('state'),
            severity_id=raw.get('severity_id'),
            color=raw.get('color'),
            created_by_id=iris_current_user.id,
            custom_attributes=raw.get('custom_attributes'),
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())

    return response_api_created(serialize_war_room(war_room))


@war_rooms_blueprint.get('/<int:war_room_id>')
@ac_api_requires()
def get_war_room(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    try:
        war_room = war_room_get(war_room_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_success(data=serialize_war_room(war_room))


@war_rooms_blueprint.patch('/<int:war_room_id>')
@ac_api_requires()
def update_war_room(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err

    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')

    try:
        war_room = war_room_update(
            war_room_id,
            name=raw.get('name'),
            description=raw.get('description'),
            state=raw.get('state'),
            severity_id=raw.get('severity_id'),
            color=raw.get('color'),
            custom_attributes=raw.get('custom_attributes'),
            closed_by_id=iris_current_user.id,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())

    # Surface state changes in the activity panel. Field-level edits
    # (rename, color, description) are intentionally not logged here —
    # they're low signal during a crisis. State transitions are.
    if 'state' in raw and raw['state']:
        emit_system_event(
            war_room_id, 'system',
            f'War room state changed to {raw["state"]}',
            author_id=iris_current_user.id,
        )

    return response_api_success(data=serialize_war_room(war_room))


@war_rooms_blueprint.delete('/<int:war_room_id>')
@ac_api_requires()
def delete_war_room(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    # Hard-delete is gated more tightly than a state flip — only
    # creators (or admins) can remove a room from the database.
    if not ac_current_user_has_permission(Permissions.war_rooms_create) \
            and not _is_admin():
        return ac_api_return_access_denied()
    try:
        war_room_delete(war_room_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    return response_api_deleted()


# --- Archive ---------------------------------------------------------------
#
# Archive is a filing decision independent from the operational state
# (`open` / `active` / `standby` / `closed`). A user with write access
# can archive or unarchive the room; state and every child row are
# preserved. `POST` archives, `DELETE` unarchives — matches the
# member/follower REST shape used elsewhere in this file.

@war_rooms_blueprint.post('/<int:war_room_id>/archive')
@ac_api_requires()
def archive_war_room(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room = war_room_archive(
            war_room_id, archived_by_id=iris_current_user.id,
        )
    except ObjectNotFoundError:
        return response_api_not_found()
    emit_system_event(
        war_room_id, 'system', 'War room archived',
        author_id=iris_current_user.id,
    )
    return response_api_success(data=serialize_war_room(war_room))


@war_rooms_blueprint.delete('/<int:war_room_id>/archive')
@ac_api_requires()
def unarchive_war_room(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room = war_room_unarchive(war_room_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    emit_system_event(
        war_room_id, 'system', 'War room unarchived',
        author_id=iris_current_user.id,
    )
    return response_api_success(data=serialize_war_room(war_room))


# --- Members ----------------------------------------------------------------

@war_rooms_blueprint.get('/<int:war_room_id>/members')
@ac_api_requires()
def list_members(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    rows = war_room_members_list(war_room_id)
    return response_api_success(data=[serialize_member(r) for r in rows])


@war_rooms_blueprint.post('/<int:war_room_id>/members')
@ac_api_requires()
def add_member(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err

    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')

    user_id = raw.get('user_id')
    if not isinstance(user_id, int):
        return response_api_error('user_id is required')

    try:
        war_room_add_member(
            war_room_id, user_id,
            role=raw.get('role'),
            added_by_id=iris_current_user.id,
            access_level=raw.get('access_level'),
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())

    rows = war_room_members_list(war_room_id)
    member_row = next((r for r in rows if r.user_id == user_id), None)
    if member_row is not None:
        emit_system_event(
            war_room_id, 'system',
            f'Added member {member_row.name or member_row.login} '
            f'as {member_row.role}',
            author_id=iris_current_user.id,
        )
    return response_api_created([serialize_member(r) for r in rows if r.user_id == user_id][0])


@war_rooms_blueprint.delete('/<int:war_room_id>/members/<int:user_id>')
@ac_api_requires()
def remove_member(war_room_id, user_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    war_room_remove_member(war_room_id, user_id)
    emit_system_event(
        war_room_id, 'system',
        f'Removed member #{user_id}',
        author_id=iris_current_user.id,
    )
    return response_api_deleted()


# --- People banner ----------------------------------------------------------

@war_rooms_blueprint.get('/<int:war_room_id>/people')
@ac_api_requires()
def list_people(war_room_id):
    """Return the union of war-room members and every user with
    effective access to any attached case.

    Surfaced as a banner above the war-room tabs so an operator can
    see at a glance who's on the war. Read-only — adding members
    still goes through the Members tab.
    """
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    return response_api_success(data=war_room_people(war_room_id))


# --- Case attachment --------------------------------------------------------

@war_rooms_blueprint.get('/<int:war_room_id>/cases')
@ac_api_requires()
def list_cases(war_room_id):
    err = require_war_room_read(war_room_id)
    if err is not None:
        return err
    rows = war_room_cases_list(war_room_id)
    return response_api_success(data=[serialize_case_attachment(r) for r in rows])


@war_rooms_blueprint.post('/<int:war_room_id>/cases')
@ac_api_requires()
def attach_case(war_room_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err

    raw = request.get_json()
    if not isinstance(raw, dict):
        return response_api_error('Invalid request')

    case_id = raw.get('case_id')
    if not isinstance(case_id, int):
        return response_api_error('case_id is required')

    # Cross-resource check: the actor must have full_access on the case
    # being attached. War-room write access alone is not enough — that
    # would let an operator with no case visibility quietly bring a
    # case into a war room and grant downstream visibility to the room's
    # ACL holders.
    if ac_fast_check_current_user_has_case_access(
        case_id, [CaseAccessLevel.full_access]
    ) is None:
        return ac_api_return_access_denied(caseid=case_id)

    try:
        link = war_room_attach_case(
            war_room_id, case_id,
            attached_by_id=iris_current_user.id,
            note=raw.get('note'),
        )
    except BusinessProcessingError as e:
        return response_api_error(e.get_message())

    # Reuse the case-attached chat kind so the activity panel shows the
    # event alongside chat-emitted `/attach` events. ref_case_id stamps
    # the case so a per-case filter on the chat surfaces it later.
    emit_system_event(
        war_room_id, 'case_attached',
        f'Attached case #{case_id}'
        + (f' — {raw.get("note")}' if raw.get('note') else ''),
        author_id=iris_current_user.id,
        ref_type='case', ref_id=case_id, ref_case_id=case_id,
        activity_type='case.attached',
    )

    return response_api_created({
        'war_room_id': link.war_room_id,
        'case_id': link.case_id,
        'attached_at': link.attached_at.isoformat() if link.attached_at else None,
        'note': link.note,
    })


@war_rooms_blueprint.delete('/<int:war_room_id>/cases/<int:case_id>')
@ac_api_requires()
def detach_case(war_room_id, case_id):
    err = require_war_room_write(war_room_id)
    if err is not None:
        return err
    try:
        war_room_detach_case(war_room_id, case_id)
    except ObjectNotFoundError:
        return response_api_not_found()
    emit_system_event(
        war_room_id, 'case_detached',
        f'Detached case #{case_id}',
        author_id=iris_current_user.id,
        ref_type='case', ref_id=case_id, ref_case_id=case_id,
        activity_type='case.detached',
    )
    return response_api_deleted()
