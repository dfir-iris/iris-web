#!/usr/bin/env python3
#
#  IRIS Source Code
#  DFIR-IRIS Team
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

import marshmallow
from datetime import datetime

from flask import request

from app import db
from app.datamgmt.case.case_comments import get_case_comment
from app.iris_engine.utils.tracker import track_activity
from app.schema.marshables import CommentSchema
from app.util import response_error
from app.util import response_success


def case_comment_update(comment_id, object_type, caseid):
    comment = get_case_comment(comment_id, caseid=caseid)
    if not comment:
        return response_error("Invalid comment ID")

    try:
        rq_t = request.get_json()
        comment_text = rq_t.get('comment_text')
        comment.comment_text = comment_text
        comment.comment_update_date = datetime.utcnow()
        comment_schema = CommentSchema()
        # request_data = call_modules_hook('on_preload_event_commented', data=request.get_json(), caseid=caseid)

        db.session.commit()

        track_activity(f"comment {comment.comment_id} on {object_type} edited", caseid=caseid)
        return response_success("Comment edited", data=comment_schema.dump(comment))

    except marshmallow.exceptions.ValidationError as e:
        return response_error(msg="Data error", data=e.normalized_messages(), status=400)