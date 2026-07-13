#  IRIS Source Code
#  Copyright (C) 2026 - DFIR-IRIS
#  contact@dfir-iris.org

"""Notification core.

Public entry points live in `service`. Hook listeners in
`hook_listeners` bind to the existing IrisHook events at app-start
time (see post_init.register_notification_listeners).
"""

from app.iris_engine.notifications.service import notify
from app.iris_engine.notifications.service import notify_many
from app.iris_engine.notifications.service import list_for_user
from app.iris_engine.notifications.service import mark_read
from app.iris_engine.notifications.service import clear
from app.iris_engine.notifications.service import unread_count
from app.iris_engine.notifications.service import get_effective_settings
from app.iris_engine.notifications.service import upsert_user_settings
from app.iris_engine.notifications.service import upsert_admin_settings

__all__ = [
    'notify',
    'notify_many',
    'list_for_user',
    'mark_read',
    'clear',
    'unread_count',
    'get_effective_settings',
    'upsert_user_settings',
    'upsert_admin_settings',
]
