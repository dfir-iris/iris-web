#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public
#  License as published by the Free Software Foundation; either
#  version 3 of the License, or (at your option) any later version.

"""Per-endpoint access checks shared across war-room sub-blueprints."""

from app.blueprints.access_controls import ac_api_return_access_denied
from app.blueprints.access_controls import ac_current_user_has_permission
from app.blueprints.access_controls import ac_fast_check_current_user_has_war_room_access
from app.blueprints.rest.endpoints import response_api_not_found
from app.business.war_rooms import war_room_exists
from app.models.authorization import Permissions
from app.models.authorization import WarRoomAccessLevel


def require_war_room_read(war_room_id):
    if not war_room_exists(war_room_id):
        return response_api_not_found()
    if not ac_current_user_has_permission(Permissions.war_rooms_read) \
            and not ac_current_user_has_permission(Permissions.server_administrator):
        return ac_api_return_access_denied()
    if ac_fast_check_current_user_has_war_room_access(
        war_room_id,
        [WarRoomAccessLevel.read_only, WarRoomAccessLevel.full_access],
    ) is None:
        return ac_api_return_access_denied()
    return None


def require_war_room_write(war_room_id):
    if not war_room_exists(war_room_id):
        return response_api_not_found()
    if not ac_current_user_has_permission(Permissions.war_rooms_write) \
            and not ac_current_user_has_permission(Permissions.server_administrator):
        return ac_api_return_access_denied()
    if ac_fast_check_current_user_has_war_room_access(
        war_room_id,
        [WarRoomAccessLevel.full_access],
    ) is None:
        return ac_api_return_access_denied()
    return None
