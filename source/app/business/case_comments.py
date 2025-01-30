#  IRIS Source Code
#  Copyright (C) 2024 - DFIR-IRIS
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

from datetime import datetime

from flask_login import current_user

from app import db
from app.datamgmt.case.case_comments import get_case_comment
from app.iris_engine.module_handler.module_handler import call_modules_hook
from app.iris_engine.utils.tracker import track_activity
from app.business.errors import BusinessProcessingError


def case_comments_update(comment_text, comment_id, object_type, caseid):
    comment = get_case_comment(comment_id, caseid=caseid)
    if not comment:
        raise BusinessProcessingError('Invalid comment ID')

    if hasattr(current_user, 'id') and current_user.id is not None:
        if comment.comment_user_id != current_user.id:
            raise BusinessProcessingError('Permission denied')

    comment.comment_text = comment_text
    comment.comment_update_date = datetime.utcnow()

    db.session.commit()

    hook = object_type
    if hook.endswith('s'):
        hook = hook[:-1]

    call_modules_hook(f'on_postload_{hook}_comment_update', data=comment, caseid=caseid)

    track_activity(f"comment {comment.comment_id} on {object_type} edited", caseid=caseid)
    return comment
