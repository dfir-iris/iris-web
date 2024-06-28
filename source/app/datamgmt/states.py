#  IRIS Source Code
#  Copyright (C) 2021 - Airbus CyberSecurity (SAS)
#  ir@cyberactionlab.net
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

from datetime import datetime
from flask_login import current_user
from sqlalchemy import and_

from app import db
from app.models import ObjectState


def _update_object_state(object_name, caseid, userid=None) -> ObjectState:
    """
    Expects a db commit soon after
    
    Args:
        object_name: name of the object to update
        caseid: case id
        userid: user id
        
    Returns:
        ObjectState object
    """
    if not userid:
        userid = current_user.id

    os = ObjectState.query.filter(and_(
        ObjectState.object_name == object_name,
        ObjectState.object_case_id == caseid
    )).first()
    if os:
        os.object_last_update = datetime.utcnow()
        os.object_state = os.object_state + 1
        os.object_updated_by_id = userid
        os.object_case_id = caseid

    else:
        os = ObjectState()
        os.object_name = object_name
        os.object_state = 0
        os.object_last_update = datetime.utcnow()
        os.object_updated_by_id = userid
        os.object_case_id = caseid

        db.session.add(os)

    return os


def get_object_state(object_name, caseid):
    os = ObjectState.query.with_entities(
        ObjectState.object_state,
        ObjectState.object_last_update
    ).filter(and_(
        ObjectState.object_name == object_name,
        ObjectState.object_case_id == caseid
    )).first()

    if os:
        return os._asdict()
    else:
        return None


def delete_case_states(caseid):
    ObjectState.query.filter(
        ObjectState.object_case_id == caseid
    ).delete()


def update_timeline_state(caseid, userid=None):
    return _update_object_state('timeline', caseid=caseid, userid=userid)


def get_timeline_state(caseid):
    return get_object_state('timeline', caseid=caseid)


def update_tasks_state(caseid, userid=None):
    return _update_object_state('tasks', caseid=caseid, userid=userid)


def get_tasks_state(caseid):
    return get_object_state('tasks', caseid=caseid)


def update_evidences_state(caseid, userid=None):
    return _update_object_state('evidences', caseid=caseid, userid=userid)


def get_evidences_state(caseid):
    return get_object_state('evidences', caseid=caseid)


def update_ioc_state(caseid, userid=None):
    return _update_object_state('ioc', caseid, userid=userid)


def get_ioc_state(caseid):
    return get_object_state('ioc', caseid=caseid)


def update_assets_state(caseid, userid=None):
    return _update_object_state('assets', caseid=caseid, userid=userid)


def get_assets_state(caseid):
    return get_object_state('assets', caseid=caseid)


def update_notes_state(caseid, userid=None):
    return _update_object_state('notes', caseid=caseid, userid=userid)


def get_notes_state(caseid):
    return get_object_state('notes', caseid=caseid)
