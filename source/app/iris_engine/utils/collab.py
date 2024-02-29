import json
from flask_socketio import join_room

import app
from app.models.authorization import CaseAccessLevel
from app.util import ac_socket_requires


def collab_notify(case_id: int, object_type: str, action_type: str, object_id, request_sid = None):
    room = f"case-{case_id}"
    app.socket_io.emit('case-obj-notif', json.dumps({
                'object_id': object_id,
                'action_type': action_type,
                'object_type': object_type
            }),
            room=room,
            to=room,
            skip_sid=request_sid)


@app.socket_io.on('join-case-obj-notif')
@ac_socket_requires(CaseAccessLevel.full_access)
def socket_join_case_obj_notif(data):

    room = data['channel']
    join_room(room=room)
