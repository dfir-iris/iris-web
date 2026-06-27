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
from flask import request

from app.logger import logger
from app.db import db
from app.blueprints.iris_user import iris_current_user
from app.models.models import UserActivity


def track_activity(message, caseid=None, ctx_less=False, user_input=False, display_in_ui=True):
    """
    Register a user activity in DB.
    :param message: Message to save as activity
    :return: Nothing
    """
    ua = UserActivity()

    try:

        ua.user_id = iris_current_user.id

    except:
        pass

    try:
        ua.case_id = caseid if ctx_less is False else None
    except Exception:
        pass

    ua.activity_date = datetime.utcnow()
    ua.activity_desc = message.capitalize()

    if iris_current_user.is_authenticated:
        logger.info(f"{iris_current_user.user} [#{iris_current_user.id}] :: Case {caseid} :: {ua.activity_desc}")
    else:
        logger.info(f"Anonymous :: Case {caseid} :: {ua.activity_desc}")

    ua.user_input = user_input
    ua.display_in_ui = display_in_ui

    ua.is_from_api = (request.cookies.get('session') is None if request else False)

    db.session.add(ua)
    db.session.commit()

    # Mirror the activity into the chat stream of every war room the
    # case is attached to. Best-effort: if the table doesn't exist yet
    # (very old install pre-migration) or the import fails for any
    # reason, the original activity row still persisted — we don't want
    # this side-channel to ever break the primary tracker path.
    if caseid is not None and display_in_ui:
        try:
            from app.business.war_room_chat import ingest_case_activity
            ingest_case_activity(caseid, ua.activity_desc, ref_activity_id=ua.id)
        except Exception:
            pass

    return ua
