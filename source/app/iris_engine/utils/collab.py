import json

from app.wsgi import socket_io


def collab_notify(case_id: int, object_type: str, action_type: str, object_id,
                  object_data: json = None, request_sid: int = None):
    room = f'case-{case_id}'
    data = json.dumps({
        'object_id': object_id,
        'action_type': action_type,
        'object_type': object_type,
        'object_data': object_data
    })
    socket_io.emit('case-obj-notif', data, room=room, to=room, skip_sid=request_sid)


def notify(case_identifier: int, object_type: str, action_type: str, object_id, object_data: json = None):
    room = f'case-{case_identifier}'
    data = {
        'object_id': object_id,
        'action_type': action_type,
        'object_type': object_type,
        'object_data': object_data
    }
    socket_io.emit('case-obj-notif', data, room=room, to=room)
