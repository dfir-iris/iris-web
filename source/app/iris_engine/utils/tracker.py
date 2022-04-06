#!/usr/bin/env python3
#
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

from app.models import UserActivity

from app import db

import logging as log


# CONTENT ------------------------------------------------
def track_activity(message, caseid=None, ctx_less=False, user_input=False):
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
        if caseid is None:
            caseid = current_user.ctx_case
        ua.case_id = caseid
    except Exception as e:
        pass

    ua.activity_date = datetime.utcnow()
    ua.activity_desc = message.capitalize() if not ctx_less else "[Unbound] {}".format(message.capitalize())

    log.info(ua.activity_desc)

    ua.user_input = user_input

    ua.is_from_api = (request.cookies.get('session') is None if request else False)

    db.session.add(ua)
    db.session.commit()

    return ua