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

# IMPORTS ------------------------------------------------
from datetime import datetime
from flask import request
from flask_login import current_user

import app
from app import db
from app.models import UserActivity

log = app.app.logger


# CONTENT ------------------------------------------------
def track_activity(message, caseid=None, ctx_less=False, user_input=False, display_in_ui=True):
    """
    Register a user activity in DB.
    :param message: Message to save as activity
    :return: Nothing
    """
    ua = UserActivity()

    try:

        ua.user_id = current_user.id

    except:
        pass

    try:
        ua.case_id = caseid if ctx_less is False else None
    except Exception:
        pass

    ua.activity_date = datetime.utcnow()
    ua.activity_desc = message.capitalize()

    if current_user.is_authenticated:
        log.info(f"{current_user.user} [#{current_user.id}] :: Case {caseid} :: {ua.activity_desc}")
    else:
        log.info(f"Anonymous :: Case {caseid} :: {ua.activity_desc}")

    ua.user_input = user_input
    ua.display_in_ui = display_in_ui

    ua.is_from_api = (request.cookies.get('session') is None if request else False)

    db.session.add(ua)
    db.session.commit()

    return ua
