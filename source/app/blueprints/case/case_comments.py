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